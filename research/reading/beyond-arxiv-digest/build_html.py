#!/usr/bin/env python3
"""Build the tabbed Beyond-arXiv digest from the six scout reports and sources.json.

Reads <src>/<server>.md for each tab, parses the numbered paper list (plus any
indented `- corroboration:` lines), and renders one self-contained page: no CDN
scripts and no target="_blank", because the hosted file viewer blocks both.
Everything else in a report (stats hunt, methodology, caveats, near-misses) goes
into each tab's collapsible "Scout notes". sources.json drives each tab's
"Check & explore" panel, the Methods & sources tab, and the generated SOURCES.md.

Usage:
  python3 build_html.py --daterange "October 18 – October 24, 2026"
  python3 build_html.py --check            # validate reports and sources.json, write nothing
  python3 build_html.py --check-links      # probe every paper and source URL
  python3 build_html.py --archive          # also snapshot this edition to editions/<date>/
"""
import argparse, datetime, html, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent

# Per-tab defaults. A report can override `stats`, `method`, and `ranking`
# with a front-matter block at the top of its .md file:
#   ---
#   ranking: editorial
#   stats: one paragraph
#   method: one paragraph
#   ---
# `ranking` is one of: measured | mixed | editorial.
TABS = [
    {
        "id": "psychology", "label": "Psychology", "source": "PsyArXiv",
        "file": "psyarxiv.md", "home": "https://psyarxiv.com", "ranking": "editorial",
        "stats": "No public download ranking exists. OSF's API exposes no view/download counters (verified in the raw JSON), the metrics endpoints 404, and Altmetric now needs an API key.",
        "method": "All 1,222 PsyArXiv preprints from Sep 18–Oct 18, 2026 were enumerated via the OSF API. The 20 below are an editorial ranking by estimated impact — landmark formats (consensus statements, megastudies, large meta-analyses, preregistered reports), data scale, novelty, and subfield diversity — not a measured leaderboard.",
    },
    {
        "id": "sociology", "label": "Sociology", "source": "SocArXiv",
        "file": "socarxiv.md", "home": "https://osf.io/preprints/socarxiv", "ranking": "measured",
        "stats": "Ranked by REAL per-paper download counts. Each OSF preprint page shows public view/download counters; 65 of the 100 papers in-window were measured (a 429 rate limit stopped the sweep). No public trending page or metrics API exists.",
        "method": "All 100 SocArXiv preprints from Sep 18–Oct 18, 2026 pulled via the OSF API; each page's counters read Oct 18. Sorted by downloads desc, ties by views. Partial ranking — 35 papers unmeasured, and earlier papers had more days to accumulate downloads.",
    },
    {
        "id": "economics", "label": "Economics", "source": "SSRN",
        "file": "ssrn.md", "home": "https://www.ssrn.com", "ranking": "mixed",
        "stats": "SSRN sunset its download rankings on July 15, 2026 — the Top Papers leaderboards are gone permanently. Per-paper download counts still show on individual abstract pages, but nothing aggregates them.",
        "method": "Candidates drawn from NBER weekly releases Sep 18–Oct 18, 2026 (nearly all cross-posted to SSRN). Only 5 could be verified with a live SSRN abstract page in-window — fresh SSRN pages aren't search-indexed yet. Ordered by per-page downloads where visible. A retry in a week or two should fill out the 20.",
    },
    {
        "id": "philosophy", "label": "Philosophy", "source": "PhilArchive",
        "file": "philarchive.md", "home": "https://philarchive.org", "ranking": "editorial",
        "stats": "No public stats source exists. Download counts are tracked but shown only to authors; no most-downloaded page, no public API, no per-item public counts.",
        "method": "Drawn from PhilArchive's “Selected recent additions” feed (the archive's own quality-filtered list). The public feed caps at 100 items, so coverage is Oct 12–18 only. Ranked by venue prestige, author prominence, novelty, and area diversity — editorial judgment, not metrics.",
    },
    {
        "id": "cryptography", "label": "Cryptography", "source": "IACR ePrint",
        "file": "iacr.md", "home": "https://eprint.iacr.org", "ranking": "editorial",
        "stats": "No current download ranking exists — IACR's last “Top 20 Downloads” reports were in 2010–2011 newsletters. The archive publishes submission counts per year only.",
        "method": "Every listing Sep 18–Oct 18, 2026 (ePrint 2026/2060–2522) was read; 24 nominated, ranked to 20 by: (1) breaks on deployed systems or standards-track PQC, (2) new primitives/models, (3) major efficiency gains, (4) notable teams/community pickup, (5) subfield diversity. ePrint is unrefereed — attack claims are as-claimed.",
    },
    {
        "id": "chemistry", "label": "Chemistry", "source": "ChemRxiv",
        "file": "chemrxiv.md", "home": "https://chemrxiv.org", "ranking": "editorial",
        "stats": "Article pages show public “N views / M downloads”, but pages are bot-blocked (403) and there is no sortable, date-filtered, or API-exposed ranking. The dashboard's Most read/Most cited are all-time only.",
        "method": "All 1,431 ChemRxiv preprints in-window enumerated via the Crossref API; every title scanned. Editorial ranking on novelty, potential impact, and subfield mix. 13 of 20 fully verified; 7 have titles/DOIs confirmed with authors approximate (rate-limited) — flagged inline.",
    },
]

RANKING_LABEL = {
    "measured": "Measured downloads",
    "mixed": "Partly measured",
    "editorial": "Editorial curation",
}
TARGET_PER_TAB = 20

# ---------------------------------------------------------------- parsing

ITEM_RE = re.compile(r"^(\d+)\.\s+\[(.*?)\]\((\S+?)\)\s+—\s+(.*)$")
NUMBERED_LINK_RE = re.compile(r"^\d+\.\s+\[")
MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE_RE = re.compile(
    rf"^(?:posted\s+)?(~?(?:{MON}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}\s+{MON}(?:\s+\d{{4}})?))"
    r"(\s*\(approx\.?\))?", re.I)
METRIC_RES = [
    re.compile(r"^(?P<views>[\d,]+)\s+views?\s*/\s*(?P<downloads>[\d,]+)\s+downloads?"),
    re.compile(r"^(?P<downloads>[\d,]+)\s+downloads?(?:,\s*(?P<views>[\d,]+)\s+(?:abstract\s+)?views?)?"),
]
VENUE_RE = re.compile(
    r"^((?:forthcoming\s+)?\*[^*]+\*(?:[^.]|(?<=\bvol)\.|(?<=\bno)\.|(?<=\bpp)\.)*?"
    r"|manuscript|forthcoming\s[^.*]{1,40}?)(?<!\bvol)(?<!\bno)(?<!\bpp)\.\s+(?=\S)",
    re.I)
EPRINT_RE =re.compile(r"\s*\((\d{4}/\d{3,5}),\s*([^)]*)\)\s*$")
# Indented sub-lines directly under a paper: evidence gathered after the scout pass.
SUBLINE_RE = re.compile(r"^\s+[-*]\s+(corroborat\w*|related|correction|flag)\s*:\s*(.+)$", re.I)
SUBLINE_KEY = {"related": "related", "correction": "correction", "flag": "flags"}
BEYOND_RE = re.compile(r"^[-*]\s+\[(.*?)\]\((\S+?)\)\s+\u2014\s+(.*)$")
UNVERIFIED_RE =re.compile(r"\bnot verified\b|\bunverified\b", re.I)


def read_report(path):
    """Return (front_matter dict, body text)."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            text = text[end + 4:].lstrip("\n")
    return meta, text


def take_date(s):
    """If s starts with a date, return (date, approx, remainder); else None."""
    m = DATE_RE.match(s)
    if not m:
        return None
    date = m.group(1)
    approx = date.startswith("~") or bool(m.group(2))
    rest = s[m.end():].lstrip(" .")
    return date.lstrip("~"), approx, rest


def parse_rest(rest):
    """Split the text after the title link into structured fields.

    Scouts don't all follow the documented `authors — date. note` shape, so this
    tolerates the variants seen so far and falls back to a plain note.
    """
    out = {"authors": "", "date": "", "approx": False, "venue": "", "eprint": "",
           "views": None, "downloads": None, "note": "", "unverified": False}
    segs = [s.strip() for s in rest.split(" — ")]

    # ChemRxiv style: "Authors. Posted Oct 5, 2026. Note" (no em dashes)
    head = segs[0]
    m = re.search(r"\.\s+Posted\s+", head)
    if m:
        out["authors"] = head[:m.start()]
        d = take_date(head[m.end():])
        if d:
            out["date"], out["approx"], tail = d
            segs = [tail] + segs[1:]
        else:
            segs = [head[m.end():]] + segs[1:]
    else:
        out["authors"] = head
        segs = segs[1:]
        # IACR style: "Authors (2026/2131, ~Sep 20)"
        em = EPRINT_RE.search(out["authors"])
        if em:
            out["authors"] = out["authors"][:em.start()]
            out["eprint"] = em.group(1)
            d = take_date(em.group(2))
            if d:
                out["date"], out["approx"], _ = d
        # "— date —" or "— posted 1 Oct 2026. note —"
        if segs and not out["date"]:
            d = take_date(segs[0])
            if d:
                out["date"], out["approx"], tail = d
                segs = ([tail] if tail else []) + segs[1:]

    note = " — ".join(s for s in segs if s)
    for rx in METRIC_RES:
        mm = rx.match(note)
        if mm:
            out["downloads"] = int(mm.group("downloads").replace(",", ""))
            if mm.group("views"):
                out["views"] = int(mm.group("views").replace(",", ""))
            note = note[mm.end():].lstrip(" .")
            break
    # PhilArchive style: "*Venue* vol. 17, forthcoming. Note" / "manuscript. Note"
    vm = VENUE_RE.match(note)
    if vm:
        out["venue"] = vm.group(1)
        note = note[vm.end():]
    if UNVERIFIED_RE.search(out["authors"]):
        out["unverified"] = True
        out["authors"] = ""
    out["note"] = note
    return out


def parse_report(text):
    items, extras, problems = [], [], []
    last = None  # paper that indented evidence sub-lines attach to
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        m = ITEM_RE.match(line)
        cm = SUBLINE_RE.match(raw)
        if m:
            num, title, url, rest = m.groups()
            item = {"num": int(num), "title": title.strip(), "url": url.strip(),
                    "corroboration": [], "related": [], "correction": [], "flags": []}
            item.update(parse_rest(rest.strip()))
            items.append(item)
            last = item
            if not re.match(r"^https?://", item["url"]):
                problems.append(f"line {lineno}: non-http URL {item['url']!r}")
        elif cm and last is not None:
            kind = cm.group(1).lower()
            last[SUBLINE_KEY.get(kind, "corroboration")].append(cm.group(2).strip())
        else:
            if line:
                last = None
            if cm:
                problems.append(f"line {lineno}: `{cm.group(1)}:` line not directly under a paper; kept in notes")
            if NUMBERED_LINK_RE.match(line):
                problems.append(f"line {lineno}: looks like a paper but doesn't match "
                                "`N. [Title](URL) — ...`; skipped")
            extras.append(raw)
    nums = [it["num"] for it in items]
    if nums and nums != list(range(1, len(nums) + 1)):
        problems.append(f"numbering is not 1..{len(nums)} in order: {nums}")
    return items, "\n".join(extras), problems


# ---------------------------------------------------------------- rendering

def esc(s):
    return html.escape(s, quote=True)


def math_html(expr):
    expr = re.sub(r"\^\{?([^{}\s$]+)\}?", r"<sup>\1</sup>", expr)
    expr = re.sub(r"_\{?([^{}\s$]+)\}?", r"<sub>\1</sub>", expr)
    return f'<span class="math">{expr}</span>'


def inline(s):
    """Escape, then render the small markdown subset scouts use."""
    s = esc(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"(?<![\"=>])(https?://[^\s<)]+[^\s<).,;])", r'<a href="\1">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\$([^$]+)\$", lambda m: math_html(m.group(1)), s)
    return s


def strip_md(s):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"[*`$]", "", s)


def blocks(md):
    """Render report prose (headings, lists, paragraphs) to HTML.

    Sections left empty once the paper list is removed are dropped, as is the
    report's top-level `# Title` line.
    """
    sections, cur = [], {"h": None, "lines": []}
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            sections.append(cur)
            cur = {"h": line[3:].strip(), "lines": []}
        else:
            cur["lines"].append(line)
    sections.append(cur)

    out = []
    for sec in sections:
        body, para, lst, kind = [], [], [], None

        def flush():
            nonlocal para, lst, kind
            if para:
                body.append(f"<p>{inline(' '.join(para))}</p>")
                para = []
            if lst:
                body.append(f"<{kind}>" + "".join(f"<li>{inline(x)}</li>" for x in lst) + f"</{kind}>")
                lst, kind = [], None

        for line in sec["lines"]:
            s = line.strip()
            bm = re.match(r"^[-*]\s+(.*)", s)
            om = re.match(r"^\d+\.\s+(.*)", s)
            if not s:
                flush()
            elif bm or om:
                k = "ul" if bm else "ol"
                if para or (kind and kind != k):
                    flush()
                kind = k
                lst.append((bm or om).group(1))
            elif lst and line.startswith(("  ", "\t")):
                lst[-1] += " " + s
            else:
                if lst:
                    flush()
                para.append(s)
        flush()
        if body:
            if sec["h"]:
                out.append(f"<h3>{inline(sec['h'])}</h3>")
            out.extend(body)
    return "\n".join(out)


def fmt_int(n):
    return f"{n:,}"


def render_card(it, measured):
    meta = []
    if it["authors"]:
        meta.append(f'<span class="authors">{inline(it["authors"])}</span>')
    if it["date"]:
        approx = ' title="Posting date estimated, not confirmed">~' if it["approx"] else ">"
        meta.append(f'<span class="date"{approx}{esc(it["date"])}</span>')
    if it["eprint"]:
        meta.append(f'<span class="venue">ePrint {esc(it["eprint"])}</span>')
    if it["venue"]:
        meta.append(f'<span class="venue">{inline(it["venue"])}</span>')
    chips = []
    if it["downloads"] is not None:
        chips.append(f'<span class="chip metric{" lead" if measured else ""}">'
                     f'{fmt_int(it["downloads"])} downloads</span>')
    if it["views"] is not None:
        chips.append(f'<span class="chip metric">{fmt_int(it["views"])} views</span>')
    if it["unverified"]:
        chips.append('<span class="chip warn" title="Title and DOI confirmed; authors not yet verified">authors unverified</span>')
    for f in it.get("flags", []):
        chips.append(f'<span class="chip warn">{inline(f)}</span>')
    if it.get("correction"):
        chips.append('<span class="chip fix">note corrected</span>')
    if it.get("corroboration"):
        chips.append('<span class="chip ok">corroborated</span>')
    corr, rel, fix = it.get("corroboration") or [], it.get("related") or [], it.get("correction") or []
    search = " ".join([it["title"], it["authors"], it["venue"], it["eprint"], it["note"], *corr, *rel])

    def evidence(cls, label, lines):
        return (f'<p class="ev {cls}"><span class="ev-label">{label}</span> '
                f'{" &middot; ".join(inline(c) for c in lines)}</p>') if lines else ""
    return (
        f'<article class="paper" data-q="{esc(strip_md(search).lower())}">'
        f'<div class="rank">{it["num"]}</div><div class="body">'
        f'<a class="title" href="{esc(it["url"])}">{inline(it["title"])}</a>'
        + (f'<div class="meta">{" <span class=sep>&middot;</span> ".join(meta)}</div>' if meta else "")
        + (f'<div class="chips">{"".join(chips)}</div>' if chips else "")
        + (f'<p class="note">{inline(it["note"])}</p>' if it["note"] else "")
        + evidence("fix", "Correction", fix)
        + evidence("corr", "Corroborated by", corr)
        + evidence("rel", "Related", rel)
        + "</div></article>"
    )


def link_list(entries):
    return "<ul class=\"links\">" + "".join(
        f'<li><a href="{esc(e["url"])}">{esc(e["name"])}</a> <span class="what">{inline(e["what"])}</span></li>'
        for e in entries) + "</ul>"


def render_beyond(entries):
    return '<ul class="beyond-list">' + "".join(
        f'<li><a href="{esc(e["url"])}">{inline(e["title"])}</a><span class="b-meta">{inline(e["rest"])}</span></li>'
        for e in entries) + "</ul>"


def render_explore(tab, src):
    """Per-tab panel: where this server sits in its field, notable work elsewhere, how to corroborate."""
    if not src and not tab.get("beyond"):
        return ""
    src = src or {"role": "", "coverage": ""}
    return (
        f'<section class="explore" id="explore-{tab["id"]}" aria-label="Check and explore">'
        f'<h2>Check &amp; explore' + (f' <span class="role">{esc(src["role"])}</span>' if src["role"] else "") + '</h2>'
        + (f'<p class="coverage">{inline(src["coverage"])}</p>' if src["coverage"] else "")
        + (f'<h3>Notable elsewhere, same window</h3>{render_beyond(tab["beyond"])}' if tab.get("beyond") else "")
        + (f'<div class="cols"><div><h3>Corroborate these picks</h3>{link_list(src.get("corroborate", []))}</div>'
           f'<div><h3>Look beyond {esc(tab["source"])}</h3>{link_list(src.get("explore", []))}</div></div>'
           if src.get("corroborate") or src.get("explore") else "")
        + "</section>"
    )


def render_pane(tab, items, notes_html, hidden, src=None):
    measured = tab["ranking"] == "measured"
    short = len(items) < TARGET_PER_TAB
    count = (f'<span class="n" data-total="{len(items)}">{len(items)} papers</span>'
             + (f" &middot; {TARGET_PER_TAB - len(items)} short of {TARGET_PER_TAB}" if short else ""))
    return (
        f'<section class="pane" id="pane-{tab["id"]}" role="tabpanel" aria-labelledby="tab-{tab["id"]}"'
        f'{" hidden" if hidden else ""}>'
        f'<div class="method">'
        f'<div class="method-head"><span class="badge {tab["ranking"]}">{RANKING_LABEL[tab["ranking"]]}</span>'
        f'<span class="links-head">'
        + (f'<a href="#explore-{tab["id"]}">How to check these &darr;</a>' if src else "")
        + f'<a class="home" href="{esc(tab["home"])}">{esc(tab["source"])} &rarr;</a></span></div>'
        f'<p><strong>Stats:</strong> {inline(tab["stats"])}</p>'
        f'<p><strong>Method:</strong> {inline(tab["method"])}</p>'
        + (f'<p class="checked"><strong>Corroboration pass:</strong> {inline(tab["checked"])}</p>' if tab.get("checked") else "")
        + '</div>'
        f'<div class="count{" short" if short else ""}">{count}</div>'
        + "\n".join(render_card(it, measured) for it in items)
        + '<p class="empty" hidden>No papers in this tab match.</p>'
        + render_explore(tab, src)
        + (f'<details class="notes"><summary>Scout notes &mdash; stats hunt, caveats, near-misses</summary>'
           f'<div class="notes-body">{notes_html}</div></details>' if notes_html else "")
        + "</section>"
    )


SIGNAL_CLASS = {"key required": "warn", "discontinued": "dead", "too early": "muted",
                "check per paper": "ok", "enumeration": "muted"}


def render_methods(tabs, sources, hidden):
    """The Methods & sources tab: how each list was ranked, what can corroborate it, what's next."""
    rows = "".join(
        f'<tr><td><a href="#{t["id"]}">{esc(t["label"])}</a><span class="sub">{esc(t["source"])}</span></td>'
        f'<td><span class="badge {t["ranking"]}">{RANKING_LABEL[t["ranking"]]}</span></td>'
        f'<td>{esc(sources["tabs"].get(t["id"], {}).get("role", ""))}</td>'
        f'<td class="num">{sum(1 for it in t["items"] if it.get("corroboration"))} / {len(t["items"])}</td></tr>'
        for t in tabs)
    why = "".join(
        f'<details class="why"><summary><strong>{esc(t["label"])}</strong> &mdash; {esc(t["source"])}'
        f' <span class="badge {t["ranking"]}">{RANKING_LABEL[t["ranking"]]}</span></summary>'
        f'<p><strong>Why:</strong> {inline(t["stats"])}</p><p><strong>How the list was picked:</strong> {inline(t["method"])}</p>'
        + (f'<p><strong>Where the field publishes:</strong> {inline(sources["tabs"][t["id"]]["coverage"])}</p>'
           if t["id"] in sources["tabs"] else "")
        + (f'<p><strong>Corroboration pass:</strong> {inline(t["checked"])}</p>' if t.get("checked") else "")
        + "</details>"
        for t in tabs)
    signals = "".join(
        f'<li><div class="sig-head"><a href="{esc(s["url"])}">{esc(s["name"])}</a>'
        f'<span class="chip {SIGNAL_CLASS.get(s["status"], "muted")}">{esc(s["status"])}</span></div>'
        f'<p>{inline(s["what"])} {inline(s["use"])}</p></li>'
        for s in sources.get("signals", []))
    beyond = "".join(
        f'<li><a href="#{t["id"]}">{esc(t["label"])}</a> &mdash; '
        + ", ".join(f'<a href="{esc(e["url"])}">{esc(e["name"])}</a>'
                    for e in sources["tabs"][t["id"]].get("explore", []))
        + "</li>"
        for t in tabs if t["id"] in sources["tabs"])
    roadmap = "".join(f'<li><strong>{esc(r["title"])}.</strong> {inline(r["detail"])}</li>'
                      for r in sources.get("roadmap", []))
    directories = link_list(sources.get("directories", [])) if sources.get("directories") else ""
    return (
        f'<section class="pane methods" id="pane-methods" role="tabpanel" aria-labelledby="tab-methods"'
        f'{" hidden" if hidden else ""}>'
        '<h2>How each list was ranked</h2>'
        '<p>Only SocArXiv\u2019s per-paper counts could be read systematically for this edition; SSRN\u2019s were visible on some pages. Where no public ranking '
        'exists, the list is an editorial pick and its tab says exactly how it was made. Open a field for the details.</p>'
        f'<table class="rank-table"><thead><tr><th>Field</th><th>Ranking</th><th>Server’s role in the field</th>'
        f'<th class="num">Corroborated</th></tr></thead><tbody>{rows}</tbody></table>'
        f'{why}'
        '<h2>Signals that can corroborate editorial picks</h2>'
        '<p>No outside service ranks these servers either, but these give independent evidence that a paper '
        'mattered. Status is as of the last review.</p>'
        f'<ul class="signals">{signals}</ul>'
        '<h2>Where else each field publishes</h2>'
        '<p>The six servers came from a chart of posting volume, which is not the same as where each field’s best '
        'work appears. Each tab ends with a <em>Check &amp; explore</em> panel; the short version:</p>'
        f'<ul class="beyond">{beyond}</ul>'
        + (f'<h2>Finding more servers</h2><p>To scout a new field, start from a directory of preprint servers '
           f'rather than a chart:</p>{directories}' if directories else "")
        + '<h2>Planned improvements</h2>'
        f'<ol class="roadmap">{roadmap}</ol>'
        f'<p class="reviewed">Source descriptions last reviewed {esc(sources.get("last_reviewed", ""))}. '
        'The annotated list, with which descriptions were verified, is <code>SOURCES.md</code> next to this page.</p>'
        "</section>"
    )


def render_sources_md(tabs, sources, daterange):
    """SOURCES.md: the long-form, annotated version of the Methods tab, generated from sources.json."""
    def entry(e):
        mark = "" if e.get("verified") else " *(description not yet re-checked)*"
        return f"- [{e['name']}]({e['url']}) — {e['what']}{mark}"

    out = [
        "# Beyond-arXiv digest — sources and methods",
        "",
        "<!-- Generated by build_html.py from sources.json and the scout reports. Edit those, not this file. -->",
        "",
        f"Edition: {daterange}. Source descriptions last reviewed {sources.get('last_reviewed', '')}.",
        "Entries marked *not yet re-checked* come from general knowledge rather than a fresh web check;",
        "run `python3 build_html.py --check-links` to confirm every URL still resolves.",
        "",
        "## How each list was ranked",
        "",
        "| Field | Server | Ranking | Server's role in the field | Papers |",
        "|---|---|---|---|---|",
    ]
    for t in tabs:
        role = sources["tabs"].get(t["id"], {}).get("role", "")
        out.append(f"| {t['label']} | [{t['source']}]({t['home']}) | {RANKING_LABEL[t['ranking']]} | {role} | {len(t['items'])} |")
    out += ["", "Only SocArXiv had readable per-paper counts (65 of 100 papers measured). SSRN is partly measured. "
            "The other four had no public ranking at all, so their lists are editorial picks — the order is the "
            "scout's judgment of impact, not a measured count.", ""]

    out += ["## Signals that can corroborate editorial picks", "",
            "| Signal | Status | What it is | How to use it |", "|---|---|---|---|"]
    for s in sources.get("signals", []):
        out.append(f"| [{s['name']}]({s['url']}) | {s['status']} | {s['what']} | {s['use']} |")
    out.append("")

    if sources.get("directories"):
        out += ["## Finding more servers", "",
                "To scout a new field, start from a directory of preprint servers rather than a chart of posting volume.", "",
                *map(entry, sources["directories"]), ""]

    out += ["## By field", ""]
    for t in tabs:
        src = sources["tabs"].get(t["id"])
        out += [f"### {t['label']} — {t['source']}", "",
                f"**Ranking:** {RANKING_LABEL[t['ranking']]}" + (f" · **Role in the field:** {src['role']}" if src else ""),
                "", f"**Why:** {t['stats']}", "", f"**How the list was picked:** {t['method']}", ""]
        if src:
            out += [f"**Where the field publishes:** {src['coverage']}", "",
                    "**Corroborate these picks**", "", *map(entry, src.get("corroborate", [])), "",
                    f"**Look beyond {t['source']}**", "", *map(entry, src.get("explore", [])), ""]

    out += ["## Using these on a weekly run", "",
            "1. Enumerate the window from the primary server (OSF API, Crossref, ePrint RSS, PhilArchive feed, NBER/RePEc).",
            "2. Where a measured ranking exists (SocArXiv counters, SSRN page counts, LogEc), use it and say so.",
            "3. Otherwise pick editorially and write the criteria into the report's `method:` front matter.",
            "4. For each pick, look for at least one corroborating signal from the lists above and add it under the paper:",
            "", "   ```", "   3. [Title](https://...) — Authors — Oct 12 — Note.",
            "      - corroboration: [C&EN story](https://...) · PREreview · Altmetric 140", "   ```", "",
            "5. Run `python3 build_html.py --check` and `--check-links`, then build.", ""]

    out += ["## Planned improvements", ""]
    out += [f"{i}. **{r['title']}.** {r['detail']}" for i, r in enumerate(sources.get("roadmap", []), 1)]
    out.append("")
    return "\n".join(out)


CSS = """
:root { --ink:#1a1a1a; --muted:#6b6b6b; --soft:#3d3d3d; --line:#e3e3e3; --accent:#1f4e79;
        --bg:#fafafa; --card:#fff; --chip:#eef2f6; --warn:#8a4b00; --warn-bg:#fdf1e2;
        --good:#1d5e3a; --good-bg:#e5f3ea; --mark:#fff2a8; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --ink:#e8e6e3; --muted:#9a9894; --soft:#c4c1bc; --line:#33363b;
        --accent:#8ab4e0; --bg:#16181b; --card:#1e2125; --chip:#2a3038; --warn:#f0b56a;
        --warn-bg:#3a2a15; --good:#7fd1a0; --good-bg:#1b3326; --mark:#5a4d10; }
}
:root[data-theme="dark"] { --ink:#e8e6e3; --muted:#9a9894; --soft:#c4c1bc; --line:#33363b;
      --accent:#8ab4e0; --bg:#16181b; --card:#1e2125; --chip:#2a3038; --warn:#f0b56a;
      --warn-bg:#3a2a15; --good:#7fd1a0; --good-bg:#1b3326; --mark:#5a4d10; }
* { box-sizing:border-box; }
body { font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:var(--bg);
       margin:0; line-height:1.55; }
a { color:var(--accent); }
.wrap { max-width:880px; margin:0 auto; padding:0 1rem; }
.hero { padding-top:2.4rem; padding-bottom:1.4rem; }
.kicker { font-family:system-ui, sans-serif; font-size:.72rem; text-transform:uppercase; letter-spacing:.12em;
          color:var(--accent); margin:0 0 .5rem; font-weight:600; }
.hero h1 { font-size:clamp(2.1rem, 7vw, 3.2rem); line-height:1.02; margin:0 0 .6rem; letter-spacing:-.025em; }
.dek { font-size:clamp(1rem, 2.4vw, 1.15rem); color:var(--soft); margin:0 0 1.2rem; max-width:44rem; }
.stats { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:1px; margin:0 0 1.1rem;
         background:var(--line); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.stats > div { background:var(--card); padding:.6rem .8rem; min-width:0; }
.stats dt { font-family:system-ui, sans-serif; font-size:.66rem; text-transform:uppercase; letter-spacing:.08em;
            color:var(--muted); margin-bottom:.15rem; }
.stats dd { margin:0; font-size:1.05rem; font-weight:bold; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.stats dd .of { font-weight:normal; color:var(--muted); font-size:.85rem; }
@media (max-width:640px) { .stats { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
.legend { display:flex; flex-direction:column; gap:.45rem; margin:0 0 1rem; }
.lg-row { display:flex; flex-wrap:wrap; align-items:center; gap:.35rem .5rem; }
.lg-row .badge { min-width:10.5rem; text-align:center; }
.lg-tab { font-size:.88rem; text-decoration:none; color:var(--ink); border:1px solid var(--line);
          background:var(--card); border-radius:999px; padding:.12rem .7rem; }
.lg-tab:hover { border-color:var(--accent); color:var(--accent); }
@media (max-width:520px) { .lg-row .badge { min-width:0; } }
.honesty { font-size:.9rem; color:var(--muted); margin:0; max-width:44rem; }
.honesty a { white-space:nowrap; }
nav.tabs { position:sticky; top:0; z-index:10; background:var(--card); border-top:1px solid var(--line);
           border-bottom:1px solid var(--line); }
nav.tabs .wrap { display:flex; flex-wrap:wrap; }
.tab { flex:0 0 auto; min-width:0; font-family:inherit; background:none; border:none;
       border-bottom:3px solid transparent; padding:.7rem .4rem .5rem; cursor:pointer; font-size:.95rem;
       color:var(--muted); text-align:center; }
nav.tabs .wrap { flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none; -webkit-overflow-scrolling:touch; }
nav.tabs .wrap::-webkit-scrollbar { display:none; }
.tab { padding-left:.75rem; padding-right:.75rem; white-space:nowrap; }
@media (min-width:720px) { nav.tabs .wrap { flex-wrap:wrap; overflow:visible; } .tab { flex:1 1 auto; } }
.tab .src { display:block; font-size:.7rem; letter-spacing:.04em; text-transform:uppercase; }
.tab .hits { display:none; font-size:.7rem; margin-left:.3rem; padding:0 .4rem; border-radius:9px;
             background:var(--chip); color:var(--ink); font-weight:normal; }
body.searching .tab .hits { display:inline-block; }
.tab .hits.zero { opacity:.45; }
.tab[aria-selected="true"] { color:var(--ink); border-bottom-color:var(--accent); font-weight:bold; }
.tab:hover { color:var(--ink); }
.tab:focus-visible { outline:2px solid var(--accent); outline-offset:-2px; }
.toolbar { display:flex; gap:.6rem; align-items:center; padding-top:1rem; }
.toolbar input { flex:1; min-width:0; font:inherit; font-size:.95rem; padding:.5rem .8rem; color:var(--ink);
                 background:var(--card); border:1px solid var(--line); border-radius:6px; }
.toolbar input:focus { outline:2px solid var(--accent); outline-offset:-1px; }
.toolbar .hint { color:var(--muted); font-size:.8rem; white-space:nowrap; }
main { padding-top:1rem; padding-bottom:4rem; }
.pane[hidden], .paper[hidden], .empty[hidden] { display:none; }
.method { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:.8rem 1.1rem;
          font-size:.88rem; color:var(--soft); margin-bottom:1.2rem; }
.method p { margin:.35rem 0; }
.method-head { display:flex; justify-content:space-between; align-items:center; gap:.5rem; margin-bottom:.2rem; }
.method-head .home { font-size:.82rem; text-decoration:none; }
.badge { white-space:nowrap; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; padding:.15rem .55rem;
         border-radius:4px; font-family:system-ui, sans-serif; }
.badge.measured { background:var(--good-bg); color:var(--good); }
.badge.mixed { background:var(--chip); color:var(--accent); }
.badge.editorial { background:var(--warn-bg); color:var(--warn); }
.count { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:.8rem; }
.count.short { color:var(--warn); }
.paper { display:flex; gap:.9rem; background:var(--card); border:1px solid var(--line); border-radius:6px;
         padding:.9rem 1.1rem; margin-bottom:.7rem; }
.rank { font-size:1.4rem; color:var(--accent); min-width:1.8rem; text-align:right; font-variant-numeric:tabular-nums; line-height:1.2; }
.body { min-width:0; flex:1; }
.paper .title { font-size:1.02rem; font-weight:bold; color:var(--ink); text-decoration:none; overflow-wrap:anywhere; }
.paper .title:hover { color:var(--accent); text-decoration:underline; }
.meta { margin-top:.25rem; font-size:.86rem; color:var(--muted); }
.meta .sep { margin:0 .25rem; }
.chips { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.4rem; }
.chip { font-family:system-ui, sans-serif; font-size:.72rem; padding:.1rem .5rem; border-radius:4px;
        background:var(--chip); color:var(--soft); font-variant-numeric:tabular-nums; }
.chip.lead { background:var(--good-bg); color:var(--good); font-weight:600; }
.chip.warn { background:var(--warn-bg); color:var(--warn); }
.note { margin:.4rem 0 0; font-size:.92rem; color:var(--soft); }
.math { font-style:italic; }
.date[title] { cursor:help; border-bottom:1px dotted var(--muted); }
kbd { font-family:system-ui, sans-serif; font-size:.75rem; padding:0 .3rem; border:1px solid var(--line); border-radius:3px; }
mark { background:var(--mark); color:inherit; padding:0 1px; border-radius:2px; }
.empty { color:var(--muted); font-style:italic; padding:1rem 0; }
details.notes { margin-top:1.5rem; background:var(--card); border:1px solid var(--line); border-radius:6px; }
details.notes summary { cursor:pointer; padding:.7rem 1.1rem; font-size:.9rem; color:var(--soft); }
details.notes[open] summary { border-bottom:1px solid var(--line); }
.notes-body { padding:.2rem 1.1rem 1rem; font-size:.88rem; color:var(--soft); overflow-wrap:anywhere; }
.notes-body h3 { font-size:.95rem; margin:1rem 0 .3rem; color:var(--ink); }
.notes-body ul, .notes-body ol { padding-left:1.3rem; margin:.3rem 0; }
.notes-body li { margin:.2rem 0; }
.method-head { flex-wrap:wrap; }
.links-head { display:flex; flex-wrap:wrap; gap:.3rem 1rem; font-size:.82rem; }
.links-head a { text-decoration:none; white-space:nowrap; }
.ev { margin:.35rem 0 0; font-size:.85rem; color:var(--soft); overflow-wrap:anywhere; }
.ev-label { font-family:system-ui, sans-serif; font-size:.66rem; text-transform:uppercase; letter-spacing:.06em;
            margin-right:.3rem; font-weight:600; }
.ev.corr .ev-label { color:var(--good); }
.ev.rel .ev-label { color:var(--muted); }
.ev.fix { background:var(--warn-bg); border-radius:4px; padding:.35rem .55rem; }
.ev.fix .ev-label { color:var(--warn); }
.chip.fix { background:var(--warn-bg); color:var(--warn); font-weight:600; }
.checked { border-top:1px dashed var(--line); padding-top:.45rem; margin-top:.5rem !important; }
.beyond-list { list-style:none; padding:0; margin:.2rem 0 1rem; }
.beyond-list li { padding:.5rem 0; border-bottom:1px solid var(--line); font-size:.88rem; }
.beyond-list li:last-child { border-bottom:none; }
.beyond-list a { font-weight:bold; text-decoration:none; }
.beyond-list a:hover { text-decoration:underline; }
.beyond-list .b-meta { display:block; color:var(--soft); font-size:.84rem; margin-top:.1rem; }
.explore { margin-top:1.8rem; border-top:2px solid var(--accent); padding-top:1rem; scroll-margin-top:7rem; }
.explore h2, .methods h2 { font-size:1.15rem; margin:0 0 .4rem; }
.explore .role { font-family:system-ui, sans-serif; font-size:.7rem; text-transform:uppercase; letter-spacing:.06em;
                 font-weight:normal; color:var(--accent); background:var(--chip); padding:.15rem .5rem;
                 border-radius:4px; margin-left:.4rem; vertical-align:middle; }
.explore .coverage { font-size:.9rem; color:var(--soft); margin:.2rem 0 .8rem; }
.explore .cols { display:grid; grid-template-columns:1fr 1fr; gap:1.2rem; }
@media (max-width:640px) { .explore .cols { grid-template-columns:1fr; gap:.4rem; } }
.explore h3 { font-size:.78rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted);
              font-family:system-ui, sans-serif; margin:.4rem 0 .3rem; }
ul.links { list-style:none; padding:0; margin:0; }
ul.links li { padding:.45rem 0; border-bottom:1px solid var(--line); font-size:.88rem; }
ul.links li:last-child { border-bottom:none; }
ul.links a { font-weight:bold; text-decoration:none; }
ul.links a:hover { text-decoration:underline; }
ul.links .what { display:block; color:var(--soft); font-size:.84rem; }
.methods h2 { margin-top:2rem; }
.methods h2:first-child { margin-top:0; }
.methods > p { font-size:.92rem; color:var(--soft); }
.rank-table { width:100%; border-collapse:collapse; font-size:.88rem; background:var(--card);
              border:1px solid var(--line); border-radius:6px; margin:.6rem 0 1rem; }
.rank-table th, .rank-table td { text-align:left; padding:.5rem .7rem; border-bottom:1px solid var(--line); vertical-align:top; }
.rank-table th { font-family:system-ui, sans-serif; font-size:.7rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
.rank-table .num { text-align:right; font-variant-numeric:tabular-nums; }
.rank-table .sub { display:block; font-size:.75rem; color:var(--muted); }
.rank-table a { font-weight:bold; text-decoration:none; }
@media (max-width:520px) { .rank-table th:nth-child(3), .rank-table td:nth-child(3) { display:none; } }
details.why { background:var(--card); border:1px solid var(--line); border-radius:6px; margin:.5rem 0; }
details.why summary { cursor:pointer; padding:.6rem .9rem; font-size:.92rem; }
details.why summary .badge { margin-left:.3rem; }
details.why p { margin:.2rem .9rem .7rem; font-size:.88rem; color:var(--soft); }
ul.signals { list-style:none; padding:0; margin:.6rem 0; }
ul.signals li { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:.6rem .9rem; margin-bottom:.5rem; }
.sig-head { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; }
.sig-head a { font-weight:bold; text-decoration:none; }
ul.signals p { margin:.25rem 0 0; font-size:.86rem; color:var(--soft); }
.chip.ok { background:var(--good-bg); color:var(--good); }
.chip.dead { background:var(--chip); color:var(--muted); text-decoration:line-through; }
.chip.muted { background:var(--chip); color:var(--muted); }
ul.beyond, ol.roadmap { font-size:.9rem; color:var(--soft); padding-left:1.2rem; }
ul.beyond li, ol.roadmap li { margin:.35rem 0; }
.reviewed { font-size:.8rem !important; color:var(--muted) !important; margin-top:1.5rem; }
.tab.about .hits { display:none !important; }
footer { padding-bottom:3rem; color:var(--muted); font-size:.82rem; }
@media (max-width:520px) {
  .paper { padding:.8rem .8rem; gap:.6rem; }
  .rank { font-size:1.1rem; min-width:1.4rem; }
  .toolbar .hint { display:none; }
}
@media print {
  nav.tabs, .toolbar { display:none; }
  .pane[hidden] { display:block; }
  .pane { break-before:page; }
  details.notes { display:none; }
  .paper { break-inside:avoid; }
}
"""

JS = r"""
(function(){
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  var panes = tabs.map(function(t){ return document.getElementById(t.getAttribute('aria-controls')); });
  var input = document.getElementById('q');

  function select(i, focus, scroll){
    tabs.forEach(function(t, j){
      var on = j === i;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      panes[j].hidden = !on;
    });
    if (focus) tabs[i].focus();
    if (tabs[i].scrollIntoView && tabs[i].parentNode.scrollWidth > tabs[i].parentNode.clientWidth)
      tabs[i].scrollIntoView({block: 'nearest', inline: 'nearest'});
    try { if (location.hash.slice(1) !== tabs[i].dataset.id) history.replaceState(null, '', '#' + tabs[i].dataset.id); } catch (e) {}
    if (scroll) window.scrollTo({top: 0, behavior: 'smooth'});
  }
  function fromHash(){
    var id = (location.hash || '').slice(1);
    for (var i = 0; i < tabs.length; i++) if (tabs[i].dataset.id === id) return i;
    return -1;
  }
  // In-page anchors (#explore-*) aren't tabs: scroll to them without switching panes.
  function onHash(){
    var i = fromHash();
    if (i >= 0) { select(i, false, true); return; }
    var el = document.getElementById((location.hash || '').slice(1));
    if (el) el.scrollIntoView({behavior: 'smooth'});
  }

  tabs.forEach(function(t, i){
    t.addEventListener('click', function(){ select(i, false, true); });
    t.addEventListener('keydown', function(e){
      var n = tabs.length, k = e.key, j = null;
      if (k === 'ArrowRight') j = (i + 1) % n;
      else if (k === 'ArrowLeft') j = (i - 1 + n) % n;
      else if (k === 'Home') j = 0;
      else if (k === 'End') j = n - 1;
      if (j !== null) { e.preventDefault(); select(j, true, false); }
    });
  });
  window.addEventListener('hashchange', onHash);
  // Handle in-page links in script: some viewers (data: URLs, sandboxed frames) can't navigate to #fragments.
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var id = a.getAttribute('href').slice(1);
    var i = tabs.findIndex(function(t){ return t.dataset.id === id; });
    var el = i < 0 && document.getElementById(id);
    if (i < 0 && !el) return;
    e.preventDefault();
    if (i >= 0) { select(i, false, true); return; }
    el.scrollIntoView({behavior: 'smooth'});
  });

  // --- search: filters every tab at once, counts hits per tab, highlights matches
  var originals = new Map();
  function highlight(el, terms){
    if (!originals.has(el)) originals.set(el, el.innerHTML);
    el.innerHTML = originals.get(el);
    if (!terms.length) return;
    var rx = new RegExp('(' + terms.map(function(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')', 'gi');
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function(node){
      if (!rx.test(node.nodeValue)) return;
      rx.lastIndex = 0;
      var span = document.createElement('span');
      span.innerHTML = node.nodeValue.replace(/[&<>]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]; }).replace(rx, '<mark>$1</mark>');
      node.parentNode.replaceChild(span, node);
    });
  }
  function run(){
    var q = input.value.trim().toLowerCase();
    var terms = q ? q.split(/\s+/) : [];
    document.body.classList.toggle('searching', terms.length > 0);
    var firstHit = -1;
    panes.forEach(function(p, i){
      if (!p.querySelector('.paper')) return;
      var hits = 0;
      p.querySelectorAll('.paper').forEach(function(card){
        var ok = terms.every(function(t){ return card.dataset.q.indexOf(t) !== -1; });
        card.hidden = !ok;
        if (ok) hits++;
        card.querySelectorAll('.title, .meta, .note').forEach(function(el){ highlight(el, ok ? terms : []); });
      });
      p.querySelector('.empty').hidden = hits > 0;
      var n = p.querySelector('.count .n'), total = n.dataset.total;
      n.textContent = terms.length ? hits + ' of ' + total + ' papers' : total + ' papers';
      var badge = tabs[i].querySelector('.hits');
      badge.textContent = hits;
      badge.classList.toggle('zero', hits === 0);
      if (hits && firstHit < 0) firstHit = i;
    });
    var cur = tabs.findIndex(function(t){ return t.getAttribute('aria-selected') === 'true'; });
    var curBadge = tabs[cur].querySelector('.hits');
    var curHits = panes[cur].querySelector('.paper') ? +curBadge.textContent : 0;
    if (terms.length && !curHits && firstHit >= 0) select(firstHit, false, false);
  }
  var timer;
  input.addEventListener('input', function(){ clearTimeout(timer); timer = setTimeout(run, 80); });
  input.addEventListener('keydown', function(e){ if (e.key === 'Escape') { input.value = ''; run(); input.blur(); } });
  document.addEventListener('keydown', function(e){
    if (e.key === '/' && document.activeElement !== input && !e.metaKey && !e.ctrlKey) { e.preventDefault(); input.focus(); }
  });

  select(Math.max(fromHash(), 0), false, false);
})();
"""


def build(args):
    src = pathlib.Path(args.src)
    tabs_out, problems, data = [], [], []
    for tab in TABS:
        t = dict(tab)
        path = src / t["file"]
        if not path.exists():
            problems.append(f"{t['file']}: missing")
            items, notes_md = [], ""
        else:
            meta, text = read_report(path)
            for k in ("stats", "method", "ranking", "checked"):
                if meta.get(k):
                    t[k] = meta[k]
            if t["ranking"] not in RANKING_LABEL:
                problems.append(f"{t['file']}: unknown ranking {t['ranking']!r}")
                t["ranking"] = "editorial"
            items, notes_md, probs = parse_report(text)
            problems += [f"{t['file']}: {p}" for p in probs]
            if not items:
                problems.append(f"{t['file']}: no papers parsed")
            elif len(items) != TARGET_PER_TAB:
                problems.append(f"{t['file']}: {len(items)} papers (target {TARGET_PER_TAB})")
        t["items"], t["notes_html"] = items, blocks(notes_md)
        tabs_out.append(t)
        data.append({k: t[k] for k in ("id", "label", "source", "ranking", "stats", "method")}
                    | {"papers": items})

    beyond_path = src / "beyond.md"
    if beyond_path.exists():
        current, ids = None, {t["id"] for t in tabs_out}
        by_tab = {}
        for lineno, raw in enumerate(beyond_path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if line.startswith("## "):
                current = line[3:].strip().lower()
                if current not in ids:
                    problems.append(f"beyond.md line {lineno}: unknown tab {current!r}")
                continue
            m = BEYOND_RE.match(line)
            if m and current:
                by_tab.setdefault(current, []).append({"title": m.group(1), "url": m.group(2), "rest": m.group(3)})
            elif line.startswith(("-", "*")) and "](" in line:
                problems.append(f"beyond.md line {lineno}: expected `- [Title](URL) \u2014 ...`")
        for t in tabs_out:
            t["beyond"] = by_tab.get(t["id"], [])

    seen = {}
    for t in tabs_out:
        for it in t["items"]:
            if it["url"] in seen:
                problems.append(f"{t['file']}: duplicate URL also in {seen[it['url']]}: {it['url']}")
            seen.setdefault(it["url"], t["file"])
    return tabs_out, problems, data


def load_sources(path, tabs):
    """Read sources.json and sanity-check it against the tabs. Missing file -> no panels."""
    problems = []
    if not path.exists():
        return {"tabs": {}, "signals": [], "roadmap": []}, [f"{path.name}: missing (no Check & explore panels)"]
    try:
        sources = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"tabs": {}, "signals": [], "roadmap": []}, [f"{path.name}: invalid JSON ({e})"]
    for k, default in (("tabs", {}), ("signals", []), ("directories", []), ("roadmap", [])):
        sources.setdefault(k, default)
    ids = {t["id"] for t in tabs}
    for tid, entry in sources["tabs"].items():
        if tid not in ids:
            problems.append(f"{path.name}: tab {tid!r} has no matching tab")
        for k in ("role", "coverage"):
            if not entry.get(k):
                problems.append(f"{path.name}: {tid} is missing {k!r}")
        for group in ("corroborate", "explore"):
            for e in entry.get(group, []):
                if not all(e.get(k) for k in ("name", "url", "what")):
                    problems.append(f"{path.name}: {tid}.{group} entry needs name, url and what: {e}")
    for tid in ids - set(sources["tabs"]):
        problems.append(f"{path.name}: no entry for tab {tid!r}")
    return sources, problems


def check_links(tabs, sources, workers=8, timeout=15):
    """HEAD (then GET) every paper and source URL. Bot-blocked pages count as reachable-but-unverified."""
    import concurrent.futures, urllib.parse, urllib.request, urllib.error
    urls = {}
    md_link = re.compile(r"\]\((https?://[^)\s]+)\)")
    for t in tabs:
        for it in t["items"]:
            urls.setdefault(it["url"], f"{t['file']} #{it['num']}")
            for line in it.get("corroboration", []) + it.get("related", []) + it.get("correction", []):
                for u in md_link.findall(line):
                    urls.setdefault(u, f"{t['file']} #{it['num']} evidence")
        for e in t.get("beyond", []):
            urls.setdefault(e["url"], f"beyond.md: {t['id']}")
        urls.setdefault(t["home"], f"{t['id']} home")
    for s in sources.get("signals", []) + sources.get("directories", []):
        urls.setdefault(s["url"], f"source: {s['name']}")
    for tid, entry in sources.get("tabs", {}).items():
        for group in ("corroborate", "explore"):
            for e in entry.get(group, []):
                urls.setdefault(e["url"], f"{tid}.{group}: {e['name']}")

    def probe(url):
        headers = {"User-Agent": "Mozilla/5.0 (beyond-arxiv-digest link check)"}
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                if method == "HEAD" and e.code in (400, 403, 405, 501):
                    continue
                return e.code
            except urllib.error.URLError as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
                    return "TLS"  # server sends an incomplete chain; browsers and curl usually cope
                return type(e.reason).__name__
            except Exception as e:  # timeout, connection reset
                return type(e).__name__
        return "?"

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        results = dict(zip(urls, pool.map(probe, urls)))
    ok, blocked, broken = [], [], []
    for url, code in results.items():
        if isinstance(code, int) and code < 400:
            ok.append(url)
        elif code in (401, 403, 429, 999, "TLS"):
            blocked.append((url, code))
        else:
            broken.append((url, code))
    print(f"links: {len(ok)} ok, {len(blocked)} blocked to scripts (likely fine in a browser), {len(broken)} broken")
    by_host = {}
    for url, code in blocked:
        by_host.setdefault((urllib.parse.urlsplit(url).netloc, code), []).append(url)
    for (host, code), group in sorted(by_host.items()):
        print(f"  blocked {code}: {host} ({len(group)} link{'s' if len(group) > 1 else ''})")
    for url, code in broken:
        print(f"  BROKEN  {code}: {url}  ({urls[url]})", file=sys.stderr)
    return len(broken)


def archive(args, tabs, out_path, slug):
    """Snapshot this edition (reports, sources, page) under editions/<slug>/ and refresh the index."""
    import shutil
    root = HERE / "editions"
    dest = root / slug
    dest.mkdir(parents=True, exist_ok=True)
    src = pathlib.Path(args.src)
    for t in tabs:
        if (src / t["file"]).exists():
            shutil.copy2(src / t["file"], dest / t["file"])
    for extra in (HERE / "sources.json", src / "beyond.md"):
        if extra.exists():
            shutil.copy2(extra, dest / extra.name)
    shutil.copy2(out_path, dest / out_path.name)
    (dest / "edition.json").write_text(json.dumps({
        "daterange": args.daterange, "compiled": args.compiled,
        "papers": {t["id"]: len(t["items"]) for t in tabs}}, indent=1) + "\n", encoding="utf-8")
    lines = ["# Past editions", "", "<!-- Generated by build_html.py --archive -->", "",
             "| Edition | Window | Papers | Page |", "|---|---|---|---|"]
    for d in sorted((p for p in root.iterdir() if (p / "edition.json").exists()), reverse=True):
        meta = json.loads((d / "edition.json").read_text(encoding="utf-8"))
        pages = sorted(d.glob("*.html"))
        page = f"[{pages[0].name}]({d.name}/{pages[0].name})" if pages else ""
        lines.append(f"| {d.name} | {meta['daterange']} | {sum(meta['papers'].values())} | {page} |")
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"archived edition to editions/{slug}/")


def render_legend(tabs):
    """Tab chips grouped by ranking type: doubles as navigation."""
    out = []
    for kind in ("measured", "mixed", "editorial"):
        group = [t for t in tabs if t["ranking"] == kind]
        if group:
            chips = "".join(f'<a class="lg-tab" href="#{t["id"]}">{esc(t["label"])}</a>' for t in group)
            out.append(f'<div class="lg-row"><span class="badge {kind}">{RANKING_LABEL[kind]}</span>{chips}</div>')
    return "".join(out)


def render_page(tabs, sources, daterange, compiled):
    total = sum(len(t["items"]) for t in tabs)
    corroborated = sum(1 for t in tabs for it in t["items"] if it.get("corroboration"))
    corrected = sum(1 for t in tabs for it in t["items"] if it.get("correction"))
    legend = render_legend(tabs)
    buttons = "\n".join(
        f'<button class="tab" id="tab-{t["id"]}" data-id="{t["id"]}" role="tab" aria-controls="pane-{t["id"]}" '
        f'aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">'
        f'{esc(t["label"])}<span class="hits">0</span><span class="src">{esc(t["source"])}</span></button>'
        for i, t in enumerate(tabs)
    )
    panes = "\n".join(render_pane(t, t["items"], t["notes_html"], i > 0, sources["tabs"].get(t["id"]))
                      for i, t in enumerate(tabs))
    if sources["tabs"] or sources["signals"]:
        buttons += ('\n<button class="tab about" id="tab-methods" data-id="methods" role="tab" aria-controls="pane-methods" '
                    'aria-selected="false" tabindex="-1">Methods<span class="hits">0</span>'
                    '<span class="src">&amp; sources</span></button>')
        panes += "\n" + render_methods(tabs, sources, True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Top papers from six preprint servers beyond arXiv, {esc(daterange)}.">
<title>Beyond arXiv &mdash; Top Papers</title>
<style>{CSS}</style>
</head>
<body>
<header class="wrap hero">
  <p class="kicker">Beyond-arXiv Digest &middot; {esc(compiled)}</p>
  <h1>Beyond arXiv</h1>
  <p class="dek">The month&rsquo;s top papers from six preprint servers outside arXiv &mdash; psychology, sociology,
  economics, philosophy, cryptography and chemistry &mdash; then checked against outside evidence, with corrections where the
  scouts got it wrong.</p>
  <dl class="stats">
    <div><dt>Window</dt><dd>{esc(daterange)}</dd></div>
    <div><dt>Papers</dt><dd>{total}</dd></div>
    <div><dt>Corroborated</dt><dd>{corroborated}<span class="of"> of {total}</span></dd></div>
    <div><dt>Notes corrected</dt><dd>{corrected}</dd></div>
  </dl>
  <div class="legend" aria-label="How each tab was ranked">{legend}</div>
  <p class="honesty">Where a real download ranking exists, the list uses it; where none does, the tab says exactly how its
  papers were picked, then shows what outside evidence backs each one.
  <a href="#methods">How the rankings work&nbsp;&rarr;</a></p>
</header>
<nav class="tabs"><div class="wrap" role="tablist" aria-label="Preprint servers">
{buttons}
</div></nav>
<div class="wrap toolbar">
  <input id="q" type="search" placeholder="Search all {total} papers &mdash; title, author, venue, note" aria-label="Search papers" autocomplete="off">
  <span class="hint">press <kbd>/</kbd></span>
</div>
<main class="wrap">
{panes}
</main>
<footer class="wrap">
  Compiled {esc(compiled)}. Rankings mix measured downloads with editorial curation where no public metrics
  exist &mdash; each tab documents its method, ends with ways to check its picks, and keeps the scout&rsquo;s full notes.
  Preprint servers are unrefereed; treat claims accordingly.
</footer>
<script>{JS}</script>
</body>
</html>
"""


def main():
    today = datetime.date.today()
    ap = argparse.ArgumentParser(description="Build the tabbed Beyond-arXiv digest HTML.")
    ap.add_argument("--daterange", default="September 18 – October 18, 2026",
                    help='Window shown in the header, e.g. "October 18 – October 24, 2026"')
    ap.add_argument("--compiled", default=f"{today:%b} {today.day}, {today.year}",
                    help="Compilation date shown in the footer (default: today)")
    ap.add_argument("--src", default=str(HERE), help="Folder holding the six scout reports (default: this folder)")
    ap.add_argument("--out", default=str(HERE / "beyond-arxiv-top-papers.html"), help="Output HTML path")
    ap.add_argument("--sources", default=str(HERE / "sources.json"), help="Links file for panels, Methods tab and SOURCES.md")
    ap.add_argument("--json", metavar="PATH", help="Also write the parsed papers as JSON")
    ap.add_argument("--check", action="store_true", help="Validate the reports and exit without writing")
    ap.add_argument("--check-links", action="store_true", help="Probe every paper and source URL, then exit")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero if validation finds problems")
    ap.add_argument("--archive", nargs="?", const=f"{today:%Y-%m-%d}", metavar="SLUG",
                    help="After building, snapshot this edition to editions/SLUG/ (default: today's date)")
    args = ap.parse_args()

    tabs, problems, data = build(args)
    sources_path = pathlib.Path(args.sources)
    sources, sproblems = load_sources(sources_path, tabs)
    problems += sproblems
    for p in problems:
        print(f"warning: {p}", file=sys.stderr)
    for t in tabs:
        n = lambda k: sum(1 for it in t["items"] if it.get(k))
        extra = ", ".join(f"{n(k)} {label}" for k, label in
                          (("corroboration", "corroborated"), ("related", "related"),
                           ("correction", "corrected"), ("flags", "flagged")) if n(k))
        print(f"  {t['label']:<13} {len(t['items']):>3} papers  [{t['ranking']}]"
              + (f"  {extra}" if extra else "")
              + (f"  +{len(t.get('beyond', []))} elsewhere" if t.get("beyond") else ""))
    if args.check_links:
        return 1 if check_links(tabs, sources) else 0
    if args.check:
        return 1 if (problems and args.strict) else 0

    page = render_page(tabs, sources, args.daterange, args.compiled)
    out = pathlib.Path(args.out)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out.name} ({len(page) // 1024} KB, {sum(len(t['items']) for t in tabs)} papers)")
    if sources["tabs"]:
        md_path = sources_path.parent / "SOURCES.md"
        md_path.write_text(render_sources_md(tabs, sources, args.daterange), encoding="utf-8")
        print(f"wrote {md_path.name}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"daterange": args.daterange, "compiled": args.compiled, "tabs": data},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {pathlib.Path(args.json).name}")
    if args.archive:
        archive(args, tabs, out, args.archive)
    return 1 if (problems and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
