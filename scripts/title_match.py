"""Fuzzy title matching for the Best-of master lists.

Variants of one work, inside one category, collapse to a single row:
case, punctuation, diacritics, curly quotes, "&" / "and", a leading
The/A/An, subtitles after ":" or " - ", parenthetical and bracketed
suffixes, season labels, creator text embedded in the title, creator
name variants, and small typos. Two works that share a title stay apart
when both creators are known and disagree.

The legacy key reproduces the previous exact normalizer so a match that
already merged still merges. Newer keys only add merges.
"""
import collections
import difflib
import re
import unicodedata

# Token-sort ratio (difflib) required before two titles can fuzzy-merge.
FUZZY_RATIO = 0.92
# A token that is not identical must still look like a typo, not a different word.
TOKEN_RATIO = 0.90
# One-edit typos on a long token can sit just under TOKEN_RATIO (accordion / accordian).
EDIT_RATIO = 0.84
# Joined title shorter than this is exact-match only. Short names collide too easily.
MIN_FUZZY_CHARS = 6

ROMAN = {
    'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10',
    'xi': '11', 'xii': '12', 'xiii': '13', 'xiv': '14', 'xv': '15', 'xvi': '16', 'xvii': '17',
    'xviii': '18', 'xix': '19', 'xx': '20',
}
WORDN = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}
ENUM_PREV = {'vol', 'volume', 'part', 'book', 'chapter'}
# Extra tokens that may appear on only one spelling of the same work.
EXTRA_OK = {'and', 'the', 'a', 'an', 'of', 'too', 'review', 'reviews'}
# Single-token stand-ins used in track titles ("U" for "you"). Applied only when the title has other words.
EQUIV = {'u': 'you', 'ur': 'your'}
ARTICLES = {'the', 'a', 'an'}
MUSIC = {'Albums', 'Songs'}

# Section labels that some lists store in the creator field.
LABELS = {
    'fiction', 'nonfiction', 'poetry', 'science', 'ideas', 'music', 'politics', 'history',
    'biography & memoir', 'memoir', 'novel', "sport & children's", 'sports', 'non-fiction',
}
STOP = {
    'a', 'an', 'the', 'of', 'and', 'or', 'to', 'in', 'on', 'for', 'with', 'from', 'into', 'about',
    'over', 'after', 'before', 'by', 'at', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those', 'it', 'its', 'will', 'would', 'can', 'may', 'not', 'no', 'nor',
    'but', 'if', 'than', 'then', 'so', 'such', 'upon', 'per', 'via', 'across', 'against', 'among',
    'through', 'during', 'without', 'within', 'just', 'your', 'you', 'my', 'our', 'their', 'his',
    'her', 'have', 'has', 'had', 'always', 'everyone', 'everything', 'something', 'here', 'there',
    'when', 'where', 'what', 'who', 'how', 'why', 'all', 'out', 'up', 'down', 'off', 'into',
}
NAME_OK = {'the', 'and', 'of', 'de', 'da', 'di', 'van', 'von', 'la', 'le', 'el', 'y', 'bin', 'st', 'du', 'del', 'della', 'jr', 'sr'}

# Obvious category aliases. The value is the label already used in these directories.
CATEGORY_ALIASES = {
    'film': 'Movies', 'films': 'Movies', 'movie': 'Movies', 'movies': 'Movies',
    'cinema': 'Movies', 'motion picture': 'Movies', 'motion pictures': 'Movies',
    'tv': 'TV', 'television': 'TV', 'tv show': 'TV', 'tv shows': 'TV',
    'television show': 'TV', 'television shows': 'TV',
    'album': 'Albums', 'albums': 'Albums', 'record': 'Albums', 'records': 'Albums',
    'song': 'Songs', 'songs': 'Songs', 'single': 'Songs', 'singles': 'Songs',
    'book': 'Books', 'books': 'Books',
    'video game': 'Video Games', 'video games': 'Video Games',
    'videogame': 'Video Games', 'videogames': 'Video Games',
    'podcast': 'Podcasts', 'podcasts': 'Podcasts',
    'documentary': 'Documentaries', 'documentaries': 'Documentaries',
    'doc': 'Documentaries', 'docs': 'Documentaries',
    'restaurant': 'Restaurants & Food', 'restaurants': 'Restaurants & Food',
    'food': 'Restaurants & Food', 'restaurants and food': 'Restaurants & Food',
    'travel': 'Travel & Hotels', 'hotel': 'Travel & Hotels', 'hotels': 'Travel & Hotels',
    'travel and hotels': 'Travel & Hotels',
    'bar': 'Bars & Cocktails', 'bars': 'Bars & Cocktails',
    'cocktail': 'Bars & Cocktails', 'cocktails': 'Bars & Cocktails',
    'bars and cocktails': 'Bars & Cocktails',
    'tech': 'Tech & Gadgets', 'gadget': 'Tech & Gadgets', 'gadgets': 'Tech & Gadgets',
    'tech and gadgets': 'Tech & Gadgets',
    'comic': 'Comics & Graphic Novels', 'comics': 'Comics & Graphic Novels',
    'graphic novel': 'Comics & Graphic Novels', 'graphic novels': 'Comics & Graphic Novels',
    'comics and graphic novels': 'Comics & Graphic Novels',
    'kids and ya books': 'Kids & YA Books', 'kids and ya': 'Kids & YA Books',
    'ya books': 'Kids & YA Books', 'young adult': 'Kids & YA Books', 'young adult books': 'Kids & YA Books',
    'cookbook': 'Cookbooks', 'cookbooks': 'Cookbooks',
    'board game': 'Board Games', 'board games': 'Board Games',
    'theater': 'Theater', 'theatre': 'Theater', 'broadway': 'Theater',
    'wine': 'Wine & Spirits', 'spirits': 'Wine & Spirits', 'wine and spirits': 'Wine & Spirits',
    'beauty': 'Beauty',
    'photography': 'Photography', 'photo': 'Photography', 'photos': 'Photography',
    'science': 'Science',
    'sport': 'Sports', 'sports': 'Sports',
    'anime': 'Anime',
    'app': 'Apps', 'apps': 'Apps', 'application': 'Apps', 'applications': 'Apps',
}

_SEASON = re.compile(
    r'(?:[:\-–—,]\s*|\s+)\b(?:season|series)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|[ivx]{1,4})\b',
    re.I)
_QUOTES = (
    ('\u2018', "'"), ('\u2019', "'"), ('\u201a', "'"), ('\u201b', "'"),
    ('\u201c', '"'), ('\u201d', '"'), ('\u201e', '"'), ('\u201f', '"'),
)


def fold_chars(s):
    """Straighten quotes and drop diacritics. Case is preserved."""
    for src, dst in _QUOTES:
        s = s.replace(src, dst)
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c))


def canon_topic(topic):
    """Map an obvious category alias onto the label these lists already use."""
    folded = fold_chars(topic or '').lower().replace('&', ' and ')
    folded = re.sub(r'[^a-z0-9]+', ' ', folded).strip()
    return CATEGORY_ALIASES.get(folded, (topic or '').strip())


def _legacy_norm(title):
    """Previous exact key: case, punctuation, leading article, parens, season/part labels."""
    t = fold_chars(title)
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', t)
    t = re.sub(r'[:,]?\s*(a novel|a memoir|a cookbook|stories)$', '', t.strip(), flags=re.I)
    t = re.sub(
        r"[:\s,\-–]*(season|series|part)\s+(\w+)\b",
        lambda m: ' s' + WORDN.get(m.group(2).lower(), m.group(2).lower()),
        t, flags=re.I)
    t = re.sub(r'[:\s]*limited series$', '', t, flags=re.I)
    w = re.sub(r"['’]", '', t)
    w = re.sub(r'&', ' and ', w)
    w = re.split(r'\W+', w.lower())
    w = [ROMAN.get(x, x) if i == len(w) - 1 or (i > 0 and w[i - 1] in ('vol', 'volume')) else x for i, x in enumerate(w) if x]
    if w and w[0] in ARTICLES and len(w) > 1:
        w = w[1:]
    return ''.join(w)


def _legacy_base(title):
    if ':' not in title:
        return None
    return _legacy_norm(title.split(':', 1)[0])


def is_non_creator(creator):
    """Award slots, section labels, and blurbs are not a person, artist, or place."""
    t = (creator or '').strip().lower()
    if not t:
        return True
    if t in LABELS or 'section labels' in t:
        return True
    if re.search(r'\b(best|winner|winners|nominee|nominees|outstanding|award|awards)\b', t):
        return True
    if re.search(r'\bof the year\b', t) or t.startswith(('pick for', 'game awards', 'destination')):
        return True
    if len(t) >= 60:
        return True
    return False


def known_creator(creator):
    return bool(creator and creator.strip()) and not is_non_creator(creator)


def _people(creator):
    """Name tuples for one creator string. Order and feat. credits do not matter."""
    s = fold_chars(creator or '')
    # A translator or illustrator credit is not a second author.
    s = re.split(r'(?:,|;|\s)+(?:trans\.|tr\.|translated by|translation by|illus\.|illustrated by|edited by)\b', s, maxsplit=1, flags=re.I)[0]
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = s.lower().replace('&', ' and ').replace('.', '')
    s = re.sub(r'\b(?:feat|ft|featuring)\b', ',', s)
    # "e l u c i d" and "j r r tolkien" share a key with the unspaced form.
    s = re.sub(r'\b(?:[a-z]\s+){1,}[a-z]\b', lambda m: m.group(0).replace(' ', ''), s)
    people = []
    for part in re.split(r'\s+and\s+|,|;|/', s):
        toks = [t for t in re.findall(r"[a-z0-9']+", part) if t not in ARTICLES and len(t) > 1]
        if toks:
            people.append(tuple(toks))
    return people


def _person_close(a, b):
    if a == b or set(a) <= set(b) or set(b) <= set(a):
        return True
    # A one-token name only matches a one-letter typo in a long name.
    # "Drake" / "Drakeo" is a different artist, not a typo.
    if len(a) == 1 and len(b) == 1:
        if min(len(a[0]), len(b[0])) >= 6 and not _plural_variant(a[0], b[0]) and _one_edit(a[0], b[0]):
            return True
        return False
    return difflib.SequenceMatcher(None, ' '.join(a), ' '.join(b)).ratio() >= TOKEN_RATIO


def creators_compatible(a, b):
    """True when one side is unknown, or the names are the same person or band."""
    if not known_creator(a) or not known_creator(b):
        return True
    pa, pb = _people(a), _people(b)
    if not pa or not pb:
        return True
    small, large = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    used = set()
    for person in small:
        found = False
        for i, other in enumerate(large):
            if i in used:
                continue
            if _person_close(person, other):
                used.add(i)
                found = True
                break
        if not found:
            return False
    return True


def _strip_decorations(title):
    """Drop edition, year, label, and network suffixes. Keep a book or part number."""
    def repl(match):
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        if re.search(r'\b(book|part|vol|volume|chapter)\b', inner or '', re.I):
            return ' ' + inner + ' '
        return ' '
    s = re.sub(r'\(([^)]*)\)|\[([^\]]*)\]', repl, title)
    s = _SEASON.sub(' ', s)
    s = re.sub(r'\blimited series\b', ' ', s, flags=re.I)
    s = re.sub(r'(?<=[A-Za-z])\$(?=[A-Za-z])', 's', s)
    s = s.replace('+', ' and ')
    s = s.replace('&', ' and ')
    prev = None
    while prev != s:
        prev = s
        s = re.sub(
            r'[\s:,\-–—]+(?:deluxe|remastered|remaster|expanded edition|anniversary edition|special edition)\b\.?\s*$',
            ' ', s, flags=re.I)
    s = re.sub(r'[\s:,\-–—]+\b(?:19|20)\d{2}\b\s*$', ' ', s)
    s = re.sub(r'[:,]?\s*\b(?:a novel|a memoir|a cookbook|stories|poems|essays)\b\s*$', ' ', s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip(' -–—:,')


def _tokens(title):
    s = fold_chars(_strip_decorations(title)).lower()
    s = s.replace("'", '')
    raw = re.findall(r'[a-z0-9]+', s)
    out = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in ENUM_PREV and i + 1 < len(raw):
            nxt = raw[i + 1]
            nxt = WORDN.get(nxt, ROMAN.get(nxt, nxt))
            out.append(t)
            out.append(nxt)
            i += 2
            continue
        # "Diablo IV" and a trailing "Part V" are the same number. A title that is
        # only "VI" stays a word: converting a one-token title would glue it to "6".
        spell_out = t in ROMAN and (
            (len(t) >= 2 and len(raw) > 1)
            or (i == len(raw) - 1 and len(raw) > 1)
            or (out and out[-1] in ENUM_PREV))
        if spell_out:
            out.append(ROMAN[t])
        else:
            out.append(t)
        i += 1
    buf = []
    squashed = []
    for t in out:
        if len(t) == 1:
            buf.append(t)
        else:
            if buf:
                squashed.append(''.join(buf))
                buf = []
            squashed.append(t)
    if buf:
        squashed.append(''.join(buf))
    if squashed and squashed[0] in ARTICLES and len(squashed) > 1:
        squashed = squashed[1:]
    return tuple(squashed)


def _joined(tokens):
    return ''.join(tokens)


def _looks_like_name(text):
    s = re.sub(r'\([^)]*\)', ' ', fold_chars(text or '')).strip()
    if not s or len(s) > 55 or re.search(r'\d', s):
        return False
    parts = [p.strip() for p in re.split(r'\s+(?:and|&|feat\.?|featuring|ft\.?|with)\s+|,(?=\s)', s, flags=re.I) if p.strip()]
    if not parts or len(parts) > 5:
        return False
    for part in parts:
        words = [w for w in re.split(r'\s+', part) if w]
        if not 1 <= len(words) <= 5:
            return False
        for word in words:
            core = re.sub(r"[^A-Za-z'’.\-]", '', word).lower().strip('.')
            if not core:
                return False
            if core in STOP and core not in NAME_OK:
                return False
    return True


def _word_count(text):
    return len(re.findall(r"[A-Za-z0-9']+", fold_chars(text or '')))


def _split_embedded(title, creator, category):
    """Pull a creator out of 'Artist, "Title"', 'Artist - Album (Label)', or 'Title, Author'.

    Returns (display title, display creator, alt titles). Alt titles are extra
    match keys. Display falls back to the original title when the split is only
    a guess.
    """
    # Straighten quotes but keep accents, so the display title is not stripped.
    raw = title or ''
    for src, dst in _QUOTES:
        raw = raw.replace(src, dst)
    raw = raw.strip().rstrip(',').strip()
    alts = []
    show_t, show_c = title, creator
    field_empty = not known_creator(creator)

    quoted = re.match(r"^(?P<who>.+?)\s*[,:\-–—]\s*['\"](?P<title>.+?)['\"]?\s*$", raw)
    if quoted and _looks_like_name(quoted.group('who')) and quoted.group('title').strip():
        who, work = quoted.group('who').strip(), quoted.group('title').strip()
        alts.append(work)
        if field_empty:
            show_t, show_c = work, who
        return show_t, show_c, alts

    # "Title by Author" only. "Death by Lightning" and "Nourished By Time - Album" stay intact.
    by = re.match(r'^(?P<title>.+?)\s+by\s+(?P<who>[^()\-–—]+)$', raw, flags=re.I) if field_empty else None
    if by and _looks_like_name(by.group('who')) and 2 <= _word_count(by.group('who')) <= 4 and _word_count(by.group('title')) >= 2:
        who, work = by.group('who').strip(), by.group('title').strip()
        if not re.search(r'\bby\b', work, re.I):
            alts.append(work)
            show_t, show_c = work, who
            return show_t, show_c, alts

    if category in MUSIC and field_empty:
        dashed = re.match(r'^(?P<who>.+?)\s+[-–—]\s+(?P<title>.+)$', raw)
        if dashed and _looks_like_name(dashed.group('who')) and _word_count(dashed.group('title')) >= 1:
            who, work = dashed.group('who').strip(), dashed.group('title').strip()
            labeled = bool(re.search(r'\([^)]+\)\s*$', work))
            work_core = re.sub(r'\s*\([^)]*\)\s*$', '', work).strip() or work
            if _word_count(who) <= 8 and _word_count(work_core) <= 12:
                alts.append(work_core)
                if labeled:
                    show_t, show_c = work_core, who
        colon = re.match(r'^(?P<who>.+?)\s*:\s*(?P<title>.+)$', raw)
        if colon and _looks_like_name(colon.group('who')) and 1 <= _word_count(colon.group('who')) <= 4:
            who, work = colon.group('who').strip(), colon.group('title').strip()
            if _word_count(work) >= 1 and not re.match(r'^(season|part|volume|vol|book)\b', work, re.I):
                alts.append(work)
                if show_t == title and _word_count(work) >= _word_count(who):
                    show_t, show_c = work, who

    # A comma-quote ("Artist, 'Title") was handled above. Apostrophes in
    # "Don't" or "Man's" are part of the words.
    if field_empty and not re.search(r",\s*['\"]", raw):
        # Last comma only, so "Luna, Phoenix, Queen" is not treated as a credit.
        parts = re.match(r'^(?P<left>.+),\s+(?P<right>[^,]+)$', raw)
        if parts:
            left, right = parts.group('left').strip(), parts.group('right').strip()
            left_name, right_name = _looks_like_name(left), _looks_like_name(right)
            right_orig = ''
            tail_orig = re.search(r',\s*([^,]+)$', title or '')
            if tail_orig:
                right_orig = tail_orig.group(1)
            # A space before the comma, or an accented surname, marks "Title, Author".
            # "Babylon, South Dakota" has neither: the comma is part of the title.
            credit = bool(re.search(r'\s,\s', title or '')) or bool(re.search(r'[^\x00-\x7f]', right_orig))
            # "Artist, Album": the left side is the name and the right side is longer.
            if (category in MUSIC and left_name and _word_count(right) >= 3
                    and _word_count(left) < _word_count(right)):
                alts.append(right)
                show_t, show_c = right, left
            elif right_name and credit and 1 <= _word_count(right) <= 6 and _word_count(left) >= 1:
                # "Title , Author" or "Album , Artist". The work is the left side.
                # Skip when the right side is the longer album title caught above.
                if not (category in MUSIC and left_name and _word_count(right) > _word_count(left)):
                    alts.append(left)
                    if _word_count(right) >= 2 or category in MUSIC:
                        show_t, show_c = left, right
    # De-dupe alts while keeping order.
    seen = set()
    clean_alts = []
    for alt in alts:
        key = _joined(_tokens(alt))
        full = _joined(_tokens(raw))
        if key and key != full and key not in seen:
            seen.add(key)
            clean_alts.append(alt)
    if show_t != title and _joined(_tokens(show_t)) == _joined(_tokens(title)):
        show_t, show_c = title, creator
    return show_t, show_c or creator, clean_alts


def _subtitle_bases(title, category):
    """Left-hand side of a ':' or ' - ' subtitle, when that side is not an artist credit."""
    raw = fold_chars(title or '').strip()
    bases = []
    pieces = re.split(r'\s*:\s*|\s+[-–—]\s+', raw, maxsplit=1)
    if len(pieces) != 2:
        return bases
    left, right = pieces[0].strip(), pieces[1].strip()
    if not left or not right or _word_count(left) < 1:
        return bases
    if category in MUSIC and _looks_like_name(left) and _word_count(left) <= 8:
        return bases
    key = _joined(_tokens(left))
    full = _joined(_tokens(raw))
    if key and key != full and len(key) >= 2:
        bases.append(left)
    return bases


def _equiv_tokens(tokens):
    if len(tokens) < 2:
        return tokens
    return tuple(EQUIV.get(t, t) for t in tokens)


def _numeric_conflict(a, b):
    def nums(tokens):
        return sorted(t for t in tokens if any(ch.isdigit() for ch in t))
    return nums(a) != nums(b)


def _plural_variant(a, b):
    """'sin' / 'sins' is a different word, not a one-letter typo."""
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return long == short + 's' or long == short + 'es'


def _one_edit(a, b):
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = j = skipped = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            skipped += 1
            j += 1
            if skipped > 1:
                return False
    return skipped + (len(b) - j) <= 1


def _token_typo(a, b, overall):
    if a == b:
        return True
    if _plural_variant(a, b):
        return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio >= TOKEN_RATIO:
        return True
    # accordion/accordian is one substitution and lands just under the ratio.
    if min(len(a), len(b)) >= 6 and _one_edit(a, b):
        return True
    # blacknws/blknws is two edits inside an otherwise identical title.
    if (min(len(a), len(b)) >= 6 and ratio >= EDIT_RATIO and overall >= 0.94
            and abs(len(a) - len(b)) <= 2):
        return True
    return False


def fuzzy_title(a, b):
    """Conservative token-sort match. Different numbers never match."""
    if not a or not b:
        return False
    a, b = _equiv_tokens(a), _equiv_tokens(b)
    if a == b:
        return True
    sa, sb = ' '.join(sorted(a)), ' '.join(sorted(b))
    if min(len(sa.replace(' ', '')), len(sb.replace(' ', ''))) < MIN_FUZZY_CHARS:
        return False
    if abs(len(sa) - len(sb)) > max(8, int(0.45 * max(len(sa), len(sb)))):
        return False
    if _numeric_conflict(a, b):
        return False
    overall = difflib.SequenceMatcher(None, sa, sb).ratio()
    if overall < FUZZY_RATIO:
        return False
    used = set()
    stray_a = []
    paired = []
    for tok in a:
        best_j, best_r = None, 0.0
        for j, other in enumerate(b):
            if j in used:
                continue
            ratio = 1.0 if tok == other else difflib.SequenceMatcher(None, tok, other).ratio()
            if ratio > best_r:
                best_r, best_j = ratio, j
        if best_j is not None and (best_r >= TOKEN_RATIO or _token_typo(tok, b[best_j], overall)):
            used.add(best_j)
            paired.append((tok, b[best_j]))
        else:
            stray_a.append(tok)
    stray_b = [tok for j, tok in enumerate(b) if j not in used]
    stray_a = [tok for tok in stray_a if tok not in EXTRA_OK]
    stray_b = [tok for tok in stray_b if tok not in EXTRA_OK]
    if stray_a or stray_b:
        if len(stray_a) == 1 and len(stray_b) == 1 and _token_typo(stray_a[0], stray_b[0], overall):
            return True
        return False
    # Every token paired. Reject a pure plural that squeaked through the ratio.
    for left, right in paired:
        if left != right and _plural_variant(left, right):
            return False
    return True


class _Rec:
    __slots__ = ('list_name', 'show_title', 'show_creator', 'creator', 'legacy', 'primary', 'tokens', 'alts', 'bases')

    def __init__(self, list_name, title, creator, category):
        show_t, show_c, alt_titles = _split_embedded(title, creator, category)
        self.list_name = list_name
        self.show_title = show_t or title
        # Compatibility uses the extracted creator field only. A creator guessed
        # from the title must not block the same spelling that already names one.
        self.creator = creator if known_creator(creator) else ''
        if known_creator(creator):
            self.show_creator = creator
        elif known_creator(show_c):
            self.show_creator = show_c
        else:
            self.show_creator = ''
        self.legacy = _legacy_norm(title)
        # Primary key is the full title, so a split cannot pull in a different work.
        self.tokens = _tokens(title)
        self.primary = _joined(self.tokens)
        if len(self.primary) < 2:
            self.primary = self.legacy
        self.alts = []
        for alt in alt_titles:
            key = _joined(_tokens(alt))
            if key and len(key) >= 2 and key != self.primary and key not in self.alts:
                self.alts.append(key)
        legacy_base = _legacy_base(title)
        self.bases = []
        for base in _subtitle_bases(title, category):
            key = _joined(_tokens(base))
            if key and len(key) >= 2 and key != self.primary and key not in self.bases:
                self.bases.append(key)
        if legacy_base and legacy_base != self.legacy and legacy_base not in self.bases and legacy_base != self.primary:
            # "Artist: Album" is a credit, not a subtitle. The bare artist name is a different row.
            head = fold_chars(title).split(':', 1)[0]
            artist_credit = category in MUSIC and _looks_like_name(head) and _word_count(head) <= 8
            if not artist_credit:
                self.bases.append(legacy_base)


class _UF:
    def __init__(self, creators):
        n = len(creators)
        self.p = list(range(n))
        self.known = [[] for _ in range(n)]
        for i, creator in enumerate(creators):
            if known_creator(creator):
                self.known[i].append(creator)

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def _ok(self, a, b):
        left, right = self.known[a], self.known[b]
        if not left or not right:
            return True
        return all(creators_compatible(x, y) for x in left for y in right)

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        if not self._ok(ra, rb):
            return False
        self.p[rb] = ra
        self.known[ra].extend(self.known[rb])
        return True


def _split_exact(records, indexes):
    """Group one exact key. Unknown creators join only when the known names agree."""
    known_groups = []  # list of (creator, [indexes])
    unknown = []
    for i in indexes:
        creator = records[i].creator
        if not known_creator(creator):
            unknown.append(i)
            continue
        placed = False
        for group in known_groups:
            if creators_compatible(creator, group[0]):
                group[1].append(i)
                placed = True
                break
        if not placed:
            known_groups.append((creator, [i]))
    groups = [g[1] for g in known_groups]
    if len(groups) <= 1:
        if groups:
            groups[0].extend(unknown)
        elif unknown:
            groups.append(unknown)
    elif unknown:
        groups.append(unknown)
    return groups


def _index_fuzzy(records):
    """Block fuzzy comparisons. Typos share a prefix or a first-letter length band."""
    buckets = collections.defaultdict(set)
    for i, rec in enumerate(records):
        seen = set()
        for tok in rec.tokens:
            sigs = []
            if len(tok) >= 4:
                sigs.append('t:' + tok)
            if len(tok) >= 5:
                sigs.append('p:' + tok[:4])
            if len(tok) >= 6:
                # Off-by-one and off-by-two lengths catch a missing or extra letter.
                for delta in range(-2, 3):
                    sigs.append('b:%s%d' % (tok[0], len(tok) + delta))
            for sig in sigs:
                if sig in seen:
                    continue
                seen.add(sig)
                buckets[sig].add(i)
    return buckets


def cluster_topic(lists, category):
    """Merge items from one category.

    lists: [{'list': name, 'items': [(title, creator), ...]}, ...]
    Returns {key: {list name: (display title, creator)}} in first-seen order.
    One list contributes at most one row per work.
    """
    records = []
    for entry in lists:
        name = entry['list']
        for item in entry.get('items') or []:
            if not item:
                continue
            title = item[0] if len(item) > 0 else ''
            creator = item[1] if len(item) > 1 else ''
            if not title or not str(title).strip():
                continue
            records.append(_Rec(name, str(title), str(creator or ''), category))
    if not records:
        return {}
    uf = _UF([rec.creator for rec in records])
    by_primary = collections.defaultdict(list)
    by_legacy = collections.defaultdict(list)
    for i, rec in enumerate(records):
        if rec.primary:
            by_primary[rec.primary].append(i)
        if rec.legacy and len(rec.legacy) >= 2:
            by_legacy[rec.legacy].append(i)
    for indexes in by_primary.values():
        for group in _split_exact(records, indexes):
            for i in group[1:]:
                uf.union(group[0], i)
    for indexes in by_legacy.values():
        for group in _split_exact(records, indexes):
            for i in group[1:]:
                uf.union(group[0], i)

    ambiguous = set()
    for key, indexes in by_primary.items():
        people = []
        conflict = False
        for i in indexes:
            creator = records[i].creator
            if not known_creator(creator):
                continue
            if any(not creators_compatible(creator, other) for other in people):
                conflict = True
                break
            people.append(creator)
        if conflict:
            ambiguous.add(key)

    def blocked(i, j):
        """Don't attach a bare title to one creator when another creator has it too."""
        for rec, other in ((records[i], records[j]), (records[j], records[i])):
            if not known_creator(rec.creator) and rec.primary in ambiguous and known_creator(other.creator):
                return True
        return False

    def link(i, j):
        if i == j or blocked(i, j):
            return
        uf.union(i, j)

    for i, rec in enumerate(records):
        for key in rec.alts:
            for j in by_primary.get(key, ()):
                link(i, j)
            for j in by_legacy.get(key, ()):
                link(i, j)
        for key in rec.bases:
            for j in by_primary.get(key, ()):
                link(i, j)
            for j in by_legacy.get(key, ()):
                link(i, j)
    # Wrappers that share an extracted title but no clean primary.
    by_alt = collections.defaultdict(list)
    for i, rec in enumerate(records):
        for key in rec.alts:
            by_alt[key].append(i)
    for indexes in by_alt.values():
        for group in _split_exact(records, indexes):
            for i in group[1:]:
                link(group[0], i)

    buckets = _index_fuzzy(records)
    seen_pairs = set()
    for indexes in buckets.values():
        group = [i for i in indexes]
        if len(group) < 2 or len(group) > 250:
            continue
        for a_i in range(len(group)):
            for b_i in range(a_i + 1, len(group)):
                i, j = group[a_i], group[b_i]
                if i > j:
                    i, j = j, i
                if (i, j) in seen_pairs or uf.find(i) == uf.find(j):
                    continue
                seen_pairs.add((i, j))
                if fuzzy_title(records[i].tokens, records[j].tokens):
                    link(i, j)

    clusters = collections.OrderedDict()
    for i, rec in enumerate(records):
        root = uf.find(i)
        bucket = clusters.get(root)
        if bucket is None:
            bucket = collections.OrderedDict()
            clusters[root] = bucket
        # First spelling from a list wins the slot. The count is unique lists.
        bucket.setdefault(rec.list_name, (rec.show_title, rec.show_creator))
    return clusters


def title_penalty(title):
    """Lower is cleaner. Used only to break a tie between equally common spellings."""
    penalty = 0
    if title.isupper() and len(title) > 3:
        penalty += 3
    if re.search(u'[\u2018\u2019\u201c\u201d]', title):
        penalty += 2
    if title.rstrip().endswith((',', ':', ';', "'", '"', '\u2018', '\u201c')):
        penalty += 3
    if re.search(r'\s[-–—]\s', title):
        penalty += 1
    if re.search(r'\([^)]*(?:deluxe|remaster|19\d\d|20\d\d)[^)]*\)', title, re.I):
        penalty += 2
    return penalty
