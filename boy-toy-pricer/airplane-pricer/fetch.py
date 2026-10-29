#!/usr/bin/env python3
"""Page and JSON fetch for the SR22 scrapers.

HTML listings load in Playwright (headless Chromium, or the installed Chrome
when Chromium is not present). A plain HTTP GET is used only when the browser
is challenged and the same URL still returns the listing page. JSON APIs are
read with Playwright's request client, then with HTTP if that client is refused.
"""
import json
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class ScrapeError(RuntimeError):
    pass


def challenge_reason(title, status, html):
    """Why a response is not a listing page, or '' when it looks usable."""
    blob = f"{title or ''}\n{(html or '')[:4000]}".lower()
    status = int(status or 0)
    if "just a moment" in blob or ("cloudflare" in blob and "challenge" in blob):
        return "Cloudflare challenge"
    if "request could not be satisfied" in blob or "captcha" in blob:
        return "bot check"
    if "robot" in blob and status >= 400:
        return "blocked automated access"
    if status in {401, 403, 429, 503}:
        return f"HTTP {status}"
    return ""


def _urllib(url, accept, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, headers, body
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:500] if exc.fp else b""
        raise ScrapeError(challenge_reason(exc.reason, exc.code, detail.decode("utf-8", "replace")) or f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ScrapeError(f"request failed ({exc.reason})") from exc


class Fetcher:
    """One browser for a refresh. Use as a context manager."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._page = None
        self._request = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        errors = []
        for kwargs in ({}, {"channel": "chrome"}):
            try:
                self._browser = self._pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                    **kwargs,
                )
                break
            except Exception as exc:  # noqa: BLE001 - try the other channel
                errors.append(str(exc))
        if self._browser is None:
            self._pw.stop()
            raise ScrapeError("could not launch a browser: " + "; ".join(errors))
        self._page = self._browser.new_page(user_agent=UA)
        self._request = self._pw.request.new_context(
            user_agent=UA,
            extra_http_headers={"Accept": "application/json, text/plain, */*"},
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        try:
            if self._request is not None:
                self._request.dispose()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._request = None
        self._browser = None
        self._page = None
        self._pw = None

    def _browser_html(self, url, timeout):
        if self._page is None:
            raise ScrapeError("browser is not open")
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception as exc:
            raise ScrapeError(f"browser navigation failed ({exc})") from exc
        status = response.status if response is not None else 0
        title = self._page.title()
        html = self._page.content()
        reason = challenge_reason(title, status, html)
        if reason:
            raise ScrapeError(reason)
        if status >= 400:
            raise ScrapeError(f"HTTP {status}")
        return html

    def html(self, url, timeout=45000):
        """Listing HTML. Playwright first; HTTP only if the browser is blocked."""
        browser_error = None
        try:
            return self._browser_html(url, timeout)
        except ScrapeError as exc:
            browser_error = exc
        try:
            status, _headers, body = _urllib(url, "text/html,application/xhtml+xml", max(5, timeout / 1000))
        except ScrapeError:
            raise browser_error
        text = body.decode("utf-8", "replace")
        reason = challenge_reason("", status, text)
        if reason:
            raise browser_error
        return text

    def json(self, url, timeout=45000):
        """JSON API body plus response headers."""
        if self._request is not None:
            try:
                response = self._request.get(url, timeout=timeout)
                if response.ok:
                    headers = {key.lower(): value for key, value in response.headers.items()}
                    return response.json(), headers
            except Exception:
                pass
        status, headers, body = _urllib(url, "application/json", max(5, timeout / 1000))
        if status >= 400:
            raise ScrapeError(f"HTTP {status}")
        try:
            return json.loads(body.decode("utf-8")), headers
        except ValueError as exc:
            raise ScrapeError(f"invalid JSON from {url}") from exc
