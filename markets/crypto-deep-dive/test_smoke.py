#!/usr/bin/env python3
import re
import sys
import traceback
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed.")
    print("Install test dependencies with:")
    print("  python3 -m pip install playwright")
    print("  python3 -m playwright install chromium")
    sys.exit(2)

PAGE = Path(__file__).resolve().parent / "index.html"
INSTALL_HINT = (
    "Install test dependencies with:\n"
    "  python3 -m pip install playwright\n"
    "  python3 -m playwright install chromium"
)


def launch_browser(playwright):
    try:
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Exception:
        try:
            return playwright.chromium.launch(headless=True)
        except Exception:
            print("No Chrome or bundled Chromium is available for Playwright.")
            print(INSTALL_HINT)
            raise SystemExit(2)


def record_console(message, errors):
    if message.type != "error":
        return
    text = message.text or ""
    location = (message.location or {}).get("url", "")
    if any(host in text or host in location for host in ("fonts.googleapis.com", "fonts.gstatic.com")):
        return
    errors.append(f"console: {text}")


def coin_rows(page):
    return page.locator("#coinTableBody tr").count()


def source_rows(page):
    for selector in ("#sourceFreshness tbody tr", "#sourceFreshness tr", "#sourceFreshness > *"):
        count = page.locator(selector).count()
        if count:
            return count
    return 0


def check_width(page, width):
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"{width}px: horizontal overflow of {overflow}px"
    print(f"[{width}] no horizontal overflow")

    sections = page.locator("section.sec").count()
    assert sections == 15, f"{width}px: expected 15 sections, found {sections}"
    print(f"[{width}] 15 sections")

    body_text = page.locator("body").inner_text()
    placeholders = re.findall(r"__[A-Z0-9_]+__", body_text)
    assert not placeholders, f"{width}px: unresolved placeholders: {sorted(set(placeholders))}"
    print(f"[{width}] no unresolved placeholders")

    rows = coin_rows(page)
    assert rows == 100, f"{width}px: expected 100 coin rows, found {rows}"
    print(f"[{width}] coin table has 100 rows")

    for label, selector in (
        ("stablecoin", "#stableTable tr"),
        ("yield", "#yieldTable tr"),
        ("Hyperliquid", "#hlTable tr"),
        ("hack", "#hackTable tr"),
    ):
        count = page.locator(selector).count()
        assert count > 0, f"{width}px: {label} table has no rows"
    print(f"[{width}] stablecoin, yield, Hyperliquid, and hack tables are populated")

    paths = page.locator("#cycleChart path").count()
    assert paths >= 5, f"{width}px: expected at least 5 chart paths, found {paths}"
    tiles = page.locator("#treemap .tm-tile").count()
    assert tiles >= 20, f"{width}px: expected at least 20 treemap tiles, found {tiles}"
    print(f"[{width}] cycle chart has {paths} paths and treemap has {tiles} tiles")

    assert page.locator("#sourceFreshness").count() == 1, f"{width}px: #sourceFreshness is missing"
    freshness = source_rows(page)
    assert freshness >= 4, f"{width}px: expected at least 4 source rows, found {freshness}"
    print(f"[{width}] source freshness has {freshness} rows")

    delta = page.locator("#snapshotDelta")
    assert delta.count() == 1, f"{width}px: #snapshotDelta is missing"
    delta_text = (delta.text_content() or "").strip()
    assert delta_text, f"{width}px: #snapshotDelta is empty"
    print(f"[{width}] snapshot delta has text")


def check_interactions(page):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(150)

    sort_header = page.locator('#coinTable thead th[data-sort="market_cap"]')
    sort_header.click()
    classes = sort_header.get_attribute("class") or ""
    assert "sort-asc" in classes or "sort-desc" in classes, "sorting class was not applied"
    print("[1440] sorting toggles a sort class")

    page.locator('#tagChips button[data-tag="Stablecoin"]').click()
    page.wait_for_timeout(100)
    rows = coin_rows(page)
    assert 1 <= rows <= 99, f"Stablecoin filter returned {rows} rows"
    page.locator('#tagChips button[data-tag="All"]').click()
    page.wait_for_timeout(100)
    rows = coin_rows(page)
    assert rows == 100, f"All filter returned {rows} rows"
    print("[1440] Stablecoin filter and All reset work")

    search = page.locator("#coinSearch")
    search.fill("eth")
    page.wait_for_timeout(100)
    rows = coin_rows(page)
    assert 1 <= rows <= 99, f"search returned {rows} rows"
    search.fill("")
    page.wait_for_timeout(100)
    rows = coin_rows(page)
    assert rows == 100, f"search clear returned {rows} rows"
    print("[1440] search filters and clears")

    page.locator("#sWin").fill("50")
    page.wait_for_timeout(100)
    expectancy = page.locator("#sExpect").inner_text().strip()
    verdict = page.locator("#sVerdict").inner_text().strip()
    assert expectancy, "calculator expectancy is empty"
    assert verdict, "calculator verdict is empty"
    print("[1440] calculator updates expectancy and verdict")

    page.locator("#watchDemo").click()
    page.wait_for_timeout(100)
    watch_count = page.locator("#watchCount").inner_text().strip()
    assert watch_count and not watch_count.startswith("0"), f"watch count is {watch_count!r}"
    print("[1440] watchlist demo adds an address")

    page.locator('#hlChips button[data-hl="accounts"]').click()
    page.wait_for_timeout(100)
    note = page.locator("#hlNote").inner_text().strip().lower()
    assert "account value" in note, f"Hyperliquid note is {note!r}"
    print("[1440] Hyperliquid accounts toggle updates the note")

    theme = page.evaluate("() => document.documentElement.dataset.theme || 'dark'")
    if theme == "light":
        page.locator("#themeToggle").click()
        page.wait_for_timeout(50)
    page.locator("#themeToggle").click()
    page.wait_for_timeout(50)
    theme = page.evaluate("() => document.documentElement.dataset.theme")
    assert theme == "light", f"theme after first toggle is {theme!r}"
    page.locator("#themeToggle").click()
    page.wait_for_timeout(50)
    theme = page.evaluate("() => document.documentElement.dataset.theme")
    assert theme == "dark", f"theme after second toggle is {theme!r}"
    print("[1440] theme toggles to light and back")

    chart = page.locator("#cycleChart")
    chart.evaluate("el => el.scrollIntoView({block: 'center'})")
    page.wait_for_timeout(150)
    box = chart.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0, "cycle chart has no bounding box"
    page.mouse.move(box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.55)
    page.wait_for_timeout(200)
    tooltip_text = page.locator("#cycleTooltip").inner_text().strip()
    opacity = page.eval_on_selector("#cycleTooltip", "el => getComputedStyle(el).opacity")
    assert tooltip_text, "cycle chart tooltip is empty"
    assert float(opacity) == 1.0, f"cycle chart tooltip opacity is {opacity}"
    print("[1440] cycle chart hover shows the tooltip")


def main():
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.on("console", lambda message: record_console(message, errors))

            page.goto(PAGE.as_uri(), wait_until="domcontentloaded")
            page.wait_for_selector("#coinTableBody tr", state="attached")

            for width in (390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                page.wait_for_timeout(150)
                check_width(page, width)

            check_interactions(page)

            assert not errors, "JavaScript errors: " + " | ".join(errors)
            print("no uncaught JavaScript or console errors")
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        print("SMOKE TEST FAILED")
        sys.exit(1)
    print("SMOKE TEST PASSED")
