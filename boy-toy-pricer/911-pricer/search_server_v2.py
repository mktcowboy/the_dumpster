#!/usr/bin/env python3
"""Local server for the Porsche 911 report.

Serves report.html at http://127.0.0.1:8911. The page shows saved
listings immediately. POST /api/refresh scrapes one search in the background
when its saved data is older than the freshness window. POST /api/update
forces every search (the UPDATE button).

Usage:
    python3 search_server_v2.py            # then open http://127.0.0.1:8911
    python3 search_server_v2.py --port 9000
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import porsche_911
from generate_report_v2 import load_rows, normalize_rows
from refresh_911 import REPORT, ScrapeError, refresh_search, searches, write_report
from saved_store_v2 import fresh_days, load_meta, source_path

HERE = Path(__file__).resolve().parent
SCRAPER = HERE / "autotempest_scraper_v2.py"
REFRESH = HERE / "refresh_911.py"
UPDATE_LOG = HERE / "update.log"
AT_RESULTS = "https://www.autotempest.com/results"
DEFAULT_ZIP = "73102"
CACHE_TTL_S = 600
SCRAPE_TIMEOUT_S = 120

STOP_WORDS = {"for", "sale", "the", "a", "an", "in", "near", "me", "with", "and", "or"}

# alias -> AutoTempest make slug
MAKES = {
    "porsche": "porsche", "ferrari": "ferrari", "lamborghini": "lamborghini", "lambo": "lamborghini",
    "audi": "audi", "bmw": "bmw", "mercedes": "mercedesbenz", "mercedesbenz": "mercedesbenz",
    "benz": "mercedesbenz", "ford": "ford", "chevrolet": "chevrolet", "chevy": "chevrolet",
    "dodge": "dodge", "toyota": "toyota", "honda": "honda", "nissan": "nissan", "mclaren": "mclaren",
    "bentley": "bentley", "maserati": "maserati", "jaguar": "jaguar", "lexus": "lexus",
    "tesla": "tesla", "gmc": "gmc", "ram": "ram", "jeep": "jeep", "subaru": "subaru",
    "mazda": "mazda", "volkswagen": "volkswagen", "vw": "volkswagen", "volvo": "volvo",
    "lotus": "lotus", "acura": "acura", "infiniti": "infiniti", "cadillac": "cadillac",
    "lincoln": "lincoln",
}

# alias -> exterior_color value accepted by AutoTempest
COLORS = {
    "white": "white", "black": "black", "silver": "silver", "gray": "gray", "grey": "gray",
    "red": "red", "blue": "blue", "green": "green", "yellow": "yellow", "orange": "orange",
    "brown": "brown", "gold": "gold", "beige": "beige", "purple": "purple",
}

# Porsche 911 generation codes: most listings say "1987 Porsche 911 Turbo", not "930",
# so search the model + year window instead of relying on the literal code.
GENERATIONS = {
    "930": {"years": (1976, 1989), "variants": ["turbo", "930"], "note": "930 = 911 Turbo, 1976-1989"},
    "964": {"years": (1989, 1994), "variants": [None], "note": "964 = 911, 1989-1994"},
    "993": {"years": (1995, 1998), "variants": [None], "note": "993 = 911, 1995-1998"},
    "996": {"years": (1999, 2004), "variants": [None], "note": "996 = 911, 1999-2004"},
    "997": {"years": (2005, 2012), "variants": [None], "note": "997 = 911, 2005-2012"},
    "991": {"years": (2012, 2019), "variants": [None], "note": "991 = 911, 2012-2019"},
    "992": {"years": (2019, None), "variants": [None], "note": "992 = 911, 2019+"},
}

TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
YEAR_RANGE_RE = re.compile(r"^((?:19|20)\d{2})-((?:19|20)\d{2})$")


def fuzzy_lookup(token, table):
    if token in table:
        return table[token]
    if len(token) >= 4:
        close = difflib.get_close_matches(token, table.keys(), n=1, cutoff=0.82)
        if close:
            return table[close[0]]
    return None


def build_plan(query, zip_code):
    """Return the AutoTempest URLs to scrape plus how the query was interpreted."""
    tokens = [t for t in TOKEN_RE.findall(query.lower()) if t not in STOP_WORDS]

    make = color = generation = None
    years = []
    keywords = []
    score_tokens = []

    for t in tokens:
        m = YEAR_RANGE_RE.match(t)
        if m:
            years.extend(int(g) for g in m.groups())
        elif YEAR_RE.match(t):
            years.append(int(t))
        elif t in GENERATIONS and generation is None:
            generation = t
            score_tokens.append(t)
        elif color is None and fuzzy_lookup(t, COLORS):
            color = fuzzy_lookup(t, COLORS)
        elif make is None and fuzzy_lookup(t, MAKES):
            make = fuzzy_lookup(t, MAKES)
            score_tokens.append(t)
        else:
            keywords.append(t)
            score_tokens.append(t)

    model = None
    gen = GENERATIONS.get(generation) if generation else None
    if gen and make in (None, "porsche"):
        make, model = "porsche", "911"
    else:
        gen = None
        if generation:
            keywords.insert(0, generation)

    if not make and not keywords:
        raise ValueError('Add a make or model, e.g. "930 porsche white" or "g wagon black".')

    year_lo = year_hi = None
    if years:
        year_lo, year_hi = min(years), max(years)
    elif gen:
        year_lo, year_hi = gen["years"]

    base = {"localization": "country", "zip": zip_code}
    if make:
        base["make"] = make
    if model:
        base["model"] = model
    if year_lo:
        base["minyear"] = year_lo
    if year_hi:
        base["maxyear"] = year_hi
    if color:
        base["exterior_color"] = color

    extra = " ".join(keywords)
    variant_keywords = gen["variants"] if gen else [None]
    urls, kw_used = [], []
    for v in variant_keywords:
        kw = " ".join(x for x in (v, extra) if x)
        params = dict(base)
        if kw:
            params["keywords"] = kw
            kw_used.append(kw)
        urls.append(AT_RESULTS + "?" + urlencode(params))

    alts = {}
    if generation == "930" and gen:
        alts["930"] = ["930", "911 turbo"]

    years_label = None
    if year_lo or year_hi:
        years_label = f"{year_lo or ''}-{year_hi or ''}" if year_lo != year_hi else str(year_lo)

    return {
        "urls": urls,
        "tokens": score_tokens,
        "token_alternatives": alts,
        "interpreted": {
            "make": make, "model": model, "years": years_label, "color": color,
            "keywords": kw_used, "note": gen["note"] if gen else None,
        },
    }


_cache = {}
_scrape_lock = threading.Lock()


def scrape(url):
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1], True
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "results.json"
        proc = subprocess.run(
            [sys.executable, str(SCRAPER), url, "-o", str(out), "--timeout", "60", "--no-msrp"],
            capture_output=True, text=True, timeout=SCRAPE_TIMEOUT_S,
        )
        if proc.returncode != 0 or not out.exists():
            lines = proc.stderr.strip().splitlines()
            raise RuntimeError(lines[-1] if lines else "scraper failed")
        rows = json.loads(out.read_text(encoding="utf-8"))
    _cache[url] = (time.time(), rows)
    return rows, False


def run_search(query, zip_code):
    plan = build_plan(query, zip_code)
    t0 = time.time()
    seen, raw, all_cached = set(), [], True
    with _scrape_lock:
        for url in plan["urls"]:
            rows, cached = scrape(url)
            all_cached = all_cached and cached
            for r in rows:
                key = r.get("listing_id") or r.get("link")
                if key not in seen:
                    seen.add(key)
                    raw.append(r)
    return {
        "rows": normalize_rows(raw),
        "at_urls": plan["urls"],
        "tokens": plan["tokens"],
        "token_alternatives": plan["token_alternatives"],
        "interpreted": plan["interpreted"],
        "cached": all_cached,
        "elapsed_s": round(time.time() - t0, 1),
    }


# ---------- full refresh (UPDATE button) ----------
_update = {"running": False, "started": None, "finished": None, "ok": None,
           "done": 0, "total": 0, "current": "", "last": ""}
_update_lock = threading.Lock()


def _count_searches():
    return len(searches())


def _watch_update(proc, log):
    """Follow the weekly script's output so the page can show which search it is on."""
    for line in proc.stdout:
        log.write(line)
        log.flush()
        line = line.strip()
        if not line:
            continue
        with _update_lock:
            _update["last"] = line[-200:]
            m = re.search(r"\] scraping: (.+)$", line)
            if m:
                _update["done"] += 1
                _update["current"] = m.group(1)
            elif "building report" in line:
                _update["current"] = "Building report"
    code = proc.wait()
    log.close()
    with _update_lock:
        _update.update(running=False, finished=time.time(), ok=code == 0,
                       current="Done" if code == 0 else f"Failed (exit {code}); see 911s/update.log")


def start_update():
    with _update_lock:
        if _update["running"]:
            return False
        UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)
        log = open(UPDATE_LOG, "w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, "-u", str(REFRESH), "--force"], cwd=str(HERE), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        _update.update(running=True, started=time.time(), finished=None, ok=None,
                       done=0, total=_count_searches(), current="Starting", last="")
    threading.Thread(target=_watch_update, args=(proc, log), daemon=True).start()
    return True


def update_status():
    with _update_lock:
        st = dict(_update)
    if st["started"]:
        st["elapsed_s"] = round((st["finished"] or time.time()) - st["started"])
    return st


# ---------- one-search background refresh ----------
_jobs = {}
_queue = []
_worker_on = False


def _refresh_busy():
    return bool(_queue) or any(job.get("running") for job in _jobs.values())


def _payload(slug, job):
    meta = load_meta(slug) or {}
    merged = source_path(slug, "merged")
    bat = source_path(slug, "bat")
    running = bool(job and job.get("running"))
    body = {
        "slug": slug,
        "running": running,
        "ok": True if running else bool(job.get("ok")) if job else True,
        "scraped_at": meta.get("scraped_at") or "",
        "warnings": [] if running else ((job or {}).get("warnings") or meta.get("warnings") or []),
    }
    if job:
        body["stage"] = job.get("stage") or ""
        body["skipped"] = bool(job.get("skipped"))
        body["elapsed_s"] = round((job.get("finished") or time.time()) - job["started"]) if job.get("started") else 0
    if not running:
        body["rows"] = load_rows(merged) if merged.exists() else []
        body["bat"] = [row for row in load_rows(bat) if row["price"] is not None] if bat.exists() else []
        if searches(slug)[0].get("classifier") == "911":
            porsche_911.add_tags(body["rows"])
            porsche_911.add_tags(body["bat"])
    return body


def _worker():
    global _worker_on
    while True:
        with _update_lock:
            if not _queue:
                _worker_on = False
                return
            slug, force = _queue.pop(0)
        def progress(stage, slug=slug):
            with _update_lock:
                _jobs[slug]["stage"] = stage
        try:
            progress("Starting")
            search = searches(slug)[0]
            result = refresh_search(search, force=force, progress=progress)
            if result.get("changed"):
                progress("Rebuilding the report")
                write_report()
            with _update_lock:
                _jobs[slug].update(running=False, ok=result.get("ok"), warnings=result.get("warnings") or [],
                                   skipped=bool(result.get("skipped")), finished=time.time())
        except Exception as exc:
            with _update_lock:
                job = _jobs.setdefault(slug, {})
                job.update(running=False, ok=False, finished=time.time(),
                           warnings=[f"Refresh failed ({exc}). Showing saved data."])


def start_refresh(slug, force):
    global _worker_on
    try:
        searches(slug)
    except ScrapeError:
        return "missing"
    with _update_lock:
        if _update["running"]:
            return "busy"
        job = _jobs.get(slug)
        if job and job.get("running"):
            return "running"
        _jobs[slug] = {"running": True, "force": force, "started": time.time(), "ok": None, "warnings": [],
                       "stage": "Waiting for another search to finish" if _refresh_busy() else "Starting"}
        # A click on REFRESH THIS CAR (force) goes ahead of background refreshes.
        _queue.insert(0, (slug, force)) if force else _queue.append((slug, force))
        if not _worker_on:
            _worker_on = True
            threading.Thread(target=_worker, daemon=True).start()
    return "started"


class Handler(BaseHTTPRequestHandler):
    server_version = "ATSearch/2.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[server] " + (fmt % args) + "\n")

    def _headers(self, status, ctype, length):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin")
        if origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def do_GET(self):
        # Reject foreign Host headers (DNS-rebinding protection for a localhost server).
        if self.headers.get("Host") not in self.server.allowed_hosts:
            return self._json(403, {"error": "forbidden host"})

        url = urlparse(self.path)
        if url.path in ("/", "/report.html"):
            if not REPORT.exists():
                return self._json(404, {"error": "report.html not found - run refresh_911.py first"})
            body = REPORT.read_bytes()
            self._headers(200, "text/html; charset=utf-8", len(body))
            self.wfile.write(body)
        elif url.path == "/api/health":
            self._json(200, {"ok": True, "fresh_days": fresh_days(), "version": 2})
        elif url.path == "/api/refresh":
            qs = parse_qs(url.query)
            slug = qs.get("slug", [""])[0].strip()
            if not slug:
                return self._json(400, {"error": "slug is required"})
            try:
                searches(slug)
            except ScrapeError:
                return self._json(404, {"error": f"unknown search {slug}"})
            self._json(200, _payload(slug, _jobs.get(slug)))
        elif url.path == "/api/search":
            qs = parse_qs(url.query)
            query = qs.get("q", [""])[0].strip()
            zip_code = qs.get("zip", [DEFAULT_ZIP])[0].strip() or DEFAULT_ZIP
            if not query or len(query) > 120:
                return self._json(400, {"error": "query must be 1-120 characters"})
            if not re.fullmatch(r"\d{5}", zip_code):
                return self._json(400, {"error": "zip must be 5 digits"})
            try:
                self._json(200, run_search(query, zip_code))
            except ValueError as e:
                self._json(400, {"error": str(e)})
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                self._json(502, {"error": f"AutoTempest scrape failed: {e}"})
        elif url.path == "/api/update":
            self._json(200, update_status())
        else:
            self._json(404, {"error": "not found"})

    def do_OPTIONS(self):
        # CORS preflight for the report's POST when it is opened as a file.
        if self.headers.get("Host") not in self.server.allowed_hosts:
            return self._json(403, {"error": "forbidden host"})
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Vary", "Origin")
        self.end_headers()

    def do_POST(self):
        # Starting a scrape changes state, so only this report may ask: same host, and an
        # Origin of this server or a local file. Other websites get 403.
        if self.headers.get("Host") not in self.server.allowed_hosts:
            return self._json(403, {"error": "forbidden host"})
        if self.headers.get("Origin") not in self.server.allowed_origins:
            return self._json(403, {"error": "forbidden origin"})
        path = urlparse(self.path).path
        if path == "/api/refresh":
            qs = parse_qs(urlparse(self.path).query)
            slug = qs.get("slug", [""])[0].strip()
            force = qs.get("force", ["0"])[0] in {"1", "true", "yes"}
            if not slug:
                return self._json(400, {"error": "slug is required"})
            state = start_refresh(slug, force)
            if state == "missing":
                return self._json(404, {"error": f"unknown search {slug}"})
            if state == "busy":
                return self._json(409, {"error": "A full update is already running"})
            return self._json(202, {"started": state == "started", **_payload(slug, _jobs.get(slug))})
        if path != "/api/update":
            return self._json(404, {"error": "not found"})
        with _update_lock:
            busy = _refresh_busy()
        if busy:
            return self._json(409, {"error": "A background refresh is already running"})
        started = start_update()
        self._json(202 if started else 200, {"started": started, **update_status()})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8911)
    args = ap.parse_args()

    os.environ["AUTOTEMPEST_SEARCH_API"] = f"http://127.0.0.1:{args.port}"

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    httpd.allowed_hosts = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
    httpd.allowed_origins = {"null"} | {f"http://{h}" for h in httpd.allowed_hosts}
    print(f"911 server running. Open http://127.0.0.1:{args.port}  (Ctrl+C to stop)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)


if __name__ == "__main__":
    main()
