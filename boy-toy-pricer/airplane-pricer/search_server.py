#!/usr/bin/env python3
"""Local report server for the SR22 scanner.

Open http://127.0.0.1:8766. The page shows the saved snapshot immediately.
When that snapshot is older than the freshness window, the server refreshes
it in the background. UPDATE forces every source, including fresh ones.

Usage:
    python3 search_server.py
    python3 search_server.py --port 8766
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from generate_report import client_rows
from refresh_searches import SEARCHES, refresh_search, write_report
from saved_store import HERE, format_as_of, fresh_days, load_meta, read_csv, source_path

REPORT = HERE / "output" / "report.html"
WEEKLY = HERE / "run_sr22_weekly.sh"
UPDATE_LOG = HERE / "output" / "update.log"

_update = {"running": False, "started": None, "finished": None, "ok": None, "current": "", "last": ""}
_update_lock = threading.Lock()
_jobs = {}
_queue = []
_worker_on = False


def _watch_update(proc, log):
    for line in proc.stdout:
        log.write(line)
        log.flush()
        text = line.strip()
        if not text:
            continue
        with _update_lock:
            _update["last"] = text[-200:]
            if "scraping:" in text:
                _update["current"] = "Scraping sources"
            elif text.startswith("[ok]") or text.startswith("[warn]"):
                _update["current"] = text[-120:]
            elif "building report" in text:
                _update["current"] = "Building report"
    code = proc.wait()
    log.close()
    with _update_lock:
        _update.update(
            running=False,
            finished=time.time(),
            ok=code == 0,
            current="Done" if code == 0 else f"Failed (exit {code}); see output/update.log",
        )


def start_update():
    with _update_lock:
        if _update["running"]:
            return False
        UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)
        log = open(UPDATE_LOG, "w", encoding="utf-8")
        proc = subprocess.Popen(
            ["/bin/bash", str(WEEKLY), "--force"],
            cwd=str(HERE),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _update.update(running=True, started=time.time(), finished=None, ok=None, current="Starting", last="")
    threading.Thread(target=_watch_update, args=(proc, log), daemon=True).start()
    return True


def update_status():
    with _update_lock:
        state = dict(_update)
    if state["started"]:
        state["elapsed_s"] = round((state["finished"] or time.time()) - state["started"])
    return state


def _refresh_busy():
    return bool(_queue) or any(job.get("running") for job in _jobs.values())


def _search(slug):
    for item in SEARCHES:
        if item["slug"] == slug:
            return item
    return None


def _payload(slug, job):
    meta = load_meta(slug) or {}
    merged = source_path(slug, "merged")
    running = bool(job and job.get("running"))
    search = _search(slug) or {}
    body = {
        "slug": slug,
        "running": running,
        "ok": True if running else bool(job.get("ok")) if job else True,
        "scraped_at": meta.get("scraped_at") or "",
        "as_of": format_as_of(meta.get("scraped_at")),
        "warnings": [] if running else ((job or {}).get("warnings") or meta.get("warnings") or []),
        "meta": {
            "slug": SLUG,
            "title": meta.get("title") or search.get("title") or slug,
            "scraped_at": meta.get("scraped_at") or "",
            "as_of": format_as_of(meta.get("scraped_at")),
            "warnings": meta.get("warnings") or [],
            "sources": meta.get("sources") or {},
        },
    }
    if not running:
        body["rows"] = client_rows(read_csv(merged)) if merged.exists() else []
    return body


def _worker():
    global _worker_on
    while True:
        with _update_lock:
            if not _queue:
                _worker_on = False
                return
            slug, force = _queue.pop(0)
        try:
            result = refresh_search(_search(slug), force=force)
            if result.get("changed"):
                write_report()
            with _update_lock:
                _jobs[slug].update(running=False, ok=result.get("ok"), warnings=result.get("warnings") or [], finished=time.time())
        except Exception as exc:
            with _update_lock:
                job = _jobs.setdefault(slug, {})
                job.update(running=False, ok=False, finished=time.time(), warnings=[f"Refresh failed ({exc}). Showing saved data."])


def start_refresh(slug, force):
    global _worker_on
    if _search(slug) is None:
        return "missing"
    with _update_lock:
        if _update["running"]:
            return "busy"
        job = _jobs.get(slug)
        if job and job.get("running"):
            return "running"
        _jobs[slug] = {"running": True, "force": force, "started": time.time(), "ok": None, "warnings": []}
        _queue.append((slug, force))
        if not _worker_on:
            _worker_on = True
            threading.Thread(target=_worker, daemon=True).start()
    return "started"


class Handler(BaseHTTPRequestHandler):
    server_version = "SR22Scan/1.0"

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
        if self.headers.get("Host") not in self.server.allowed_hosts:
            return self._json(403, {"error": "forbidden host"})
        url = urlparse(self.path)
        if url.path in ("/", "/report.html"):
            if not REPORT.exists():
                return self._json(404, {"error": "report.html not found — run run_sr22_weekly.sh first"})
            body = REPORT.read_bytes()
            self._headers(200, "text/html; charset=utf-8", len(body))
            self.wfile.write(body)
        elif url.path == "/api/health":
            self._json(200, {"ok": True, "fresh_days": fresh_days(), "slugs": [item["slug"] for item in SEARCHES]})
        elif url.path == "/api/refresh":
            qs = parse_qs(url.query)
            slug = qs.get("slug", ["sr22"])[0].strip() or "sr22"
            if _search(slug) is None:
                return self._json(404, {"error": f"unknown search {slug}"})
            self._json(200, _payload(slug, _jobs.get(slug)))
        elif url.path == "/api/update":
            self._json(200, update_status())
        else:
            self._json(404, {"error": "not found"})

    def do_OPTIONS(self):
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
        if self.headers.get("Host") not in self.server.allowed_hosts:
            return self._json(403, {"error": "forbidden host"})
        if self.headers.get("Origin") not in self.server.allowed_origins:
            return self._json(403, {"error": "forbidden origin"})
        path = urlparse(self.path).path
        if path == "/api/refresh":
            qs = parse_qs(urlparse(self.path).query)
            slug = qs.get("slug", ["sr22"])[0].strip() or "sr22"
            force = qs.get("force", ["0"])[0] in {"1", "true", "yes"}
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    httpd.allowed_hosts = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
    httpd.allowed_origins = {"null"} | {f"http://{host}" for host in httpd.allowed_hosts}
    print(f"SR22 report server running. Open http://127.0.0.1:{args.port}  (Ctrl+C to stop)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)


if __name__ == "__main__":
    main()
