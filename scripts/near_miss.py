#!/usr/bin/env python3
"""List rows of master_rank.json that did not merge but look close, for review.

Usage: python3 scripts/near_miss.py [--check] best-of-2026 [best-of-2025 ...]

Per category it prints three kinds of pair:
  ratio    the normalized keys are a few letters apart
  prefix   one title is the other plus a few trailing words
  creator  the same title under two or more creators, one line per title
Pairs whose creators disagree are left out of ratio and prefix: that split is
already the rule. Pairs named in the "split" section of bestof_merges.json are
left out of all three. A real duplicate goes in "merge", a real pair of works in
"split", and the next refresh is quieter.

--check also re-clusters each year's items.json and reports whether every
override in bestof_merges.json fired. It exits 1 when a merge never fired in
any year given, which means its titles no longer match the data.
"""
import collections
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import title_match as tm  # noqa: E402
try:
    from item_cleanup import clean_items  # noqa: E402
except ImportError:
    clean_items = None

# Key similarity worth a look. Merges need far more (see title_match.FUZZY_RATIO).
NEAR_RATIO = 0.80
# Shorter key below this many letters is too generic to report.
MIN_CHARS = 5
# A prefix pair with more extra words than this is a different work.
MAX_EXTRA = 4
# Model suffixes that make a different product, not a variant spelling.
MODEL_WORDS = {'pro', 'max', 'plus', 'mini', 'ultra', 'fold', 'flip', 'a', 'se', 'lite', 'air', 'xl', 'fe', 's'}


def _split_pairs(category):
    """Split overrides for a category as (side, side) pairs."""
    return tm.OVERRIDES['split'].get(category) or []


def _side_match(row, side, category):
    title, who = (side, None) if isinstance(side, str) else (side[0], side[1])
    if tm._key(title, category) != row['key']:
        return False
    return who is None or (bool(row['creator']) and tm.compat_for(category)(row['creator'], who))


def _silenced(a, b, category):
    for left, right in _split_pairs(category):
        if (_side_match(a, left, category) and _side_match(b, right, category)) or \
                (_side_match(a, right, category) and _side_match(b, left, category)):
            return True
    return False


def _candidates(rows):
    """Pairs that share a long token or a key prefix. Near misses almost always do."""
    buckets = collections.defaultdict(set)
    for i, row in enumerate(rows):
        buckets['k:' + row['key'][:3]].add(i)
        for tok in row['tokens']:
            if len(tok) >= 4:
                buckets['t:' + tok].add(i)
    pairs = set()
    for members in buckets.values():
        if len(members) > 300:
            continue
        members = sorted(members)
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                pairs.add((members[x], members[y]))
    return sorted(pairs)


def near_misses(rank_path):
    """{category: [(kind, score, row a, row b)]} for one master_rank.json."""
    data = json.load(open(rank_path))
    out = collections.OrderedDict()
    for topic in data['topics']:
        category = topic['topic']
        compat = tm.compat_for(category)
        rows = []
        for item in topic['items']:
            toks = tm._title_tokens(item['title'], category)
            rows.append({'title': item['title'], 'creator': item.get('creator') or '',
                         'count': item['count'], 'tokens': toks, 'key': tm._joined(toks)})
        found = []
        for i, j in _candidates(rows):
            a, b = rows[i], rows[j]
            if not a['key'] or not b['key']:
                continue
            short, long_ = (a, b) if len(a['tokens']) <= len(b['tokens']) else (b, a)
            known = bool(a['creator']) and bool(b['creator'])
            agree = not known or compat(a['creator'], b['creator'])
            kind = score = None
            if a['key'] == b['key']:
                if known and not agree:
                    kind, score = 'creator', 1.0
            elif agree and min(len(a['key']), len(b['key'])) >= MIN_CHARS:
                extra = long_['tokens'][len(short['tokens']):]
                # A one-word title is a prefix of everything ("The Women" / "Women and the Piano").
                limit = MAX_EXTRA if len(short['tokens']) > 1 else 2
                if long_['tokens'][:len(short['tokens'])] == short['tokens'] and 1 <= len(extra) <= limit:
                    numbers = tm._numeric_conflict(short['tokens'], long_['tokens'])
                    model = category == 'Tech & Gadgets' and set(extra) <= MODEL_WORDS
                    if not numbers and not model:
                        kind, score = 'prefix', len(short['key']) / len(long_['key'])
                model_only = category == 'Tech & Gadgets' and set(a['tokens']) ^ set(b['tokens']) <= MODEL_WORDS
                if kind is None and not model_only:
                    sm = difflib.SequenceMatcher(None, a['key'], b['key'])
                    if sm.real_quick_ratio() >= NEAR_RATIO and sm.quick_ratio() >= NEAR_RATIO:
                        ratio = sm.ratio()
                        if ratio >= NEAR_RATIO and not tm._numeric_conflict(a['tokens'], b['tokens']):
                            kind, score = 'ratio', ratio
            if kind and not _silenced(a, b, category):
                found.append((kind, score, a, b))
        if found:
            out[category] = _collapse(found)
    return out


def _collapse(found):
    """One line per shared title in the creator kind: ten "Greatest Hits" are one finding."""
    kept, by_key = [], collections.OrderedDict()
    for kind, score, a, b in found:
        if kind == 'creator':
            group = by_key.setdefault(a['key'], [])
            for row in (a, b):
                if row not in group:
                    group.append(row)
        else:
            kept.append((kind, score, a, b))
    order = {'ratio': 0, 'prefix': 1}
    kept.sort(key=lambda f: (order[f[0]], -f[1], f[2]['title'].lower()))
    for group in by_key.values():
        kept.append(('creator', float(len(group)), group[0], group[1:]))
    return kept


def _show(row):
    if isinstance(row, list):
        return '  ~  '.join(_show(r) for r in row)
    who = ' (%s)' % row['creator'] if row['creator'] else ''
    return '"%s"%s [%d]' % (row['title'], who, row['count'])


def check_overrides(dirs):
    """Re-cluster items.json for each year and report which overrides fired."""
    fired = collections.defaultdict(list)
    for d in dirs:
        items = Path(d) / 'items.json'
        if not items.exists():
            print('%s: no items.json, skipped' % d)
            continue
        tm.override_hits.clear()
        records = json.load(open(items))
        # Cluster what build_master.py clusters: the items after the source fixes.
        year = re.search(r'(\d{4})', Path(d).resolve().name)
        if clean_items and year:
            records = clean_items(records, int(year.group(1)))
        topics = collections.OrderedDict()
        for x in records:
            topics.setdefault(tm.canon_topic(x['topic']), []).append(x)
        for category, lists in topics.items():
            tm.cluster_topic(lists, category)
        for key, n in tm.override_hits.items():
            fired[key].append('%s:%d' % (Path(d).name, n))
    print('\n== overrides ==')
    missing = []
    for n, group in enumerate(tm.OVERRIDES['alias_groups']):
        hits = fired.get(('alias', '', n))
        print('  alias  %-50s %s' % (' = '.join(group)[:50], ', '.join(hits) if hits else 'no rows'))
    for category, pairs in sorted(tm.OVERRIDES['merge'].items()):
        for n, pair in enumerate(pairs):
            hits = fired.get(('merge', category, n))
            label = '%s: %s = %s' % (category, json.dumps(pair[0], ensure_ascii=False), json.dumps(pair[1], ensure_ascii=False))
            print('  merge  %-70s %s' % (label, ', '.join(hits) if hits else 'NOT FIRED'))
            if not hits:
                missing.append(label)
    for category, pairs in sorted(tm.OVERRIDES['split'].items()):
        for n, pair in enumerate(pairs):
            hits = fired.get(('split', category, n))
            label = '%s: %s / %s' % (category, json.dumps(pair[0], ensure_ascii=False), json.dumps(pair[1], ensure_ascii=False))
            # An idle split is fine: the rules already keep the pair apart.
            print('  split  %-70s %s' % (label, 'blocked ' + ', '.join(hits) if hits else 'idle'))
    return missing


def main(argv):
    check = '--check' in argv
    dirs = [a for a in argv if not a.startswith('--')]
    if not dirs:
        print(__doc__)
        return 2
    for d in dirs:
        rank = Path(d) / 'master_rank.json'
        print('== %s ==' % d)
        found = near_misses(rank)
        total = 0
        for category, pairs in found.items():
            print('\n## %s (%d)' % (category, len(pairs)))
            for kind, score, a, b in pairs:
                # The creator kind's score is how many rows share the title.
                shown = '%4d' % score if kind == 'creator' else '%.2f' % score
                print('  %-7s %s  %s  ~  %s' % (kind, shown, _show(a), _show(b)))
            total += len(pairs)
        print('\n%s: %d pairs\n' % (d, total))
    if check:
        missing = check_overrides(dirs)
        if missing:
            print('\n%d merge override(s) never fired.' % len(missing))
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
