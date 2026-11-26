#!/usr/bin/env python3
"""Pull every Wine Spectator Top 100 list (1988 to the current year).

The list site (top100-list.winespectator.com) is a React app. Each year's 100
wines ship inside its webpack bundle as `JSON.parse('...')` modules: the
current year sits in main.js, older years in lazy-loaded chunks. This script
downloads the bundle and every chunk, decodes those modules, and also pulls the
editorial site's per-year pages (2013 onward) to collect the Top 10 story links.

Raw downloads go to .cache/ (git-ignored, because the records include
Wine Spectator's tasting-note text). build.py turns them into the report.

Usage: python3 fetch.py
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
LIST_SITE = "https://top100-list.winespectator.com"
EDIT_SITE = "https://top100.winespectator.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130 Safari/537.36")


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, ""
            err = e
        except Exception as e:  # noqa: BLE001 - retry on any network error
            err = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"failed {url}: {err}")


def js_string(src, start):
    """Decode a single-quoted JS string literal beginning at src[start] == "'"."""
    assert src[start] == "'"
    out, i = [], start + 1
    simple = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    while True:
        c = src[i]
        if c == "'":
            return "".join(out), i + 1
        if c != "\\":
            out.append(c)
            i += 1
            continue
        n = src[i + 1]
        if n == "x":
            out.append(chr(int(src[i + 2:i + 4], 16)))
            i += 4
        elif n == "u":
            if src[i + 2] == "{":
                j = src.index("}", i)
                out.append(chr(int(src[i + 3:j], 16)))
                i = j + 1
            else:
                out.append(chr(int(src[i + 2:i + 6], 16)))
                i += 6
        elif n in simple:
            out.append(simple[n])
            i += 2
        elif n == "\n":  # line continuation
            i += 2
        else:
            out.append(n)
            i += 2


def json_modules(src, wanted):
    """Return {module_id: parsed JSON} for wanted ids found in a bundle file."""
    found = {}
    for m in re.finditer(r"(\d+):(?:e|function\(e\))=>?\{?(?:\"use strict\";)?"
                         r"e\.exports=JSON\.parse\(", src):
        mid = m.group(1)
        if mid in wanted:
            text, _ = js_string(src, m.end())
            found[mid] = json.loads(text)
    return found


def main():
    CACHE.mkdir(exist_ok=True)
    (CACHE / "years").mkdir(exist_ok=True)
    (CACHE / "editorial").mkdir(exist_ok=True)

    status, index = get(LIST_SITE + "/")
    main_js = re.search(r'src="(/static/js/main\.[0-9a-f]+\.js)"', index).group(1)
    _, bundle = get(LIST_SITE + main_js)
    print("bundle", main_js, len(bundle))

    year_by_module = {mid: y for y, mid in
                      re.findall(r'"\./wines-(\d{4})\.json":\[(\d+)', bundle)}
    hashes = re.search(r'n\.u=e=>"static/js/"\+e\+"\."\+(\{[^}]*\})', bundle).group(1)
    chunks = re.findall(r'(\d+):"([0-9a-f]+)"', hashes)

    data = json_modules(bundle, year_by_module)
    for cid, h in chunks:
        _, src = get(f"{LIST_SITE}/static/js/{cid}.{h}.chunk.js")
        data.update(json_modules(src, year_by_module))
    missing = sorted(set(year_by_module.values()) -
                     {year_by_module[m] for m in data})
    if missing:
        sys.exit(f"missing years: {missing}")
    for mid, wines in data.items():
        y = year_by_module[mid]
        (CACHE / "years" / f"wines-{y}.json").write_text(
            json.dumps(wines, ensure_ascii=False, indent=1))
    years = sorted(int(y) for y in year_by_module.values())
    print(f"years {years[0]}-{years[-1]}: {sum(len(v) for v in data.values())} wines")

    # Editorial site: per-year landing page links to the Top 10 stories.
    stories = {}
    for y in years:
        st, html = get(f"{EDIT_SITE}/{y}/")
        if st != 200:
            continue
        links = sorted(set(re.findall(
            r'href="(https://top100\.winespectator\.com/%d/wine/[^"#]+)"' % y, html)))
        has_video = f"{EDIT_SITE}/{y}/video" in html
        entries = []
        for url in links:
            slug = url.split(f"/{y}/wine/")[1].strip("/")
            rank = int(re.search(r"\d+", slug).group())
            _, page = get(url)
            title = re.search(r"<title>\s*(.*?)\s*(?:\||</title>)", page, re.S)
            title = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
            entries.append({"rank": rank, "url": url, "title": title})
            time.sleep(0.2)
        stories[y] = {"page": f"{EDIT_SITE}/{y}/", "video": has_video,
                      "top10": sorted(entries, key=lambda e: e["rank"])}
        print("editorial", y, len(entries))
    (CACHE / "editorial" / "stories.json").write_text(
        json.dumps(stories, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
