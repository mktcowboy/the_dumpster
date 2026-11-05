"""Headless check: load every view + sample profiles, collect JS errors, save screenshots."""
import asyncio, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: m.type == 'error' and errs.append('console: ' + m.text))
        await pg.goto('file:///workspace/f500/f500_explorer.html#/overview', wait_until='networkidle')
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path='screens/01_overview.png', full_page=False)
        for h, wait, shot in [('#/companies', 800, '02_companies.png'), ('#/map', 3500, '03_map.png'), ('#/industries', 1500, '04_industries.png'),
                              ('#/industries/Technology', 1200, None), ('#/network', 6000, '05_network.png'), ('#/network/16-nvidia', 2500, None),
                              ('#/company/16-nvidia', 3000, '06_profile_nvidia.png'), ('#/company/1', 1500, None), ('#/company/500', 1500, None), ('#/about', 800, None), ('#/map/Texas', 2000, None)]:
            await pg.evaluate(f"location.hash = '{h}'"); await pg.wait_for_timeout(wait)
            if shot: await pg.screenshot(path='screens/' + shot)
        # click a sunburst toggle + dark theme profile
        await pg.evaluate("location.hash = '#/industries'"); await pg.wait_for_timeout(600)
        await pg.click('#i-chart button[data-v=sunburst]'); await pg.wait_for_timeout(1000)
        await pg.click('#theme'); await pg.evaluate("location.hash = '#/company/7'"); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='screens/07_profile_dark.png')
        # every profile renders
        bad = await pg.evaluate("""async () => { const bad=[]; for (let i=1;i<=500;i++){ location.hash='#/company/'+i; await new Promise(r=>setTimeout(r,5)); if(!document.querySelector('#v-company .prank')) bad.push(i);} return bad; }""")
        print('profiles failing:', bad)
        await b.close()
        print('ERRORS:', len(errs)); [print(' ', e[:300]) for e in errs[:30]]
asyncio.run(main())
