import re, sys, json, subprocess, pathlib
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent
cases = [
  ({"start": "2026-08", "months": 12, "sunday": False, "weekly": False, "tz": "America/New_York"}, []),
  ({"start": "2026-08", "months": 12, "sunday": True, "weekly": True, "tz": "America/New_York"}, ["--sunday", "--weekly"]),
  ({"start": "2027-01", "months": 6, "sunday": False, "weekly": False, "tz": "Europe/London"}, ["--start", "2027-01", "--months", "6", "--tz", "Europe/London"]),
]
def strip(h):  # links and visible text, ignoring markup differences
    links = re.findall(r"href=[\"']#([^\"']+)[\"']", h)
    text = re.sub(r"<[^>]+>", " ", h); text = re.sub(r"\s+", " ", text).strip()
    return links, text
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page()
    pg.goto((HERE / "docs/_harness.html").as_uri())
    for cfg, args in cases:
        cfg["courses"] = [{"name": "", "tab": ""} for _ in range(6)]
        r = pg.evaluate("cfg => { const o = Folio.render(cfg, document.getElementById('folio')); return {ids: o.ids, html: document.getElementById('folio').innerHTML}; }", cfg)
        subprocess.run([sys.executable, "reference/build_folio.py", "--html-only", "--out", "out/_ref.pdf"] + args, check=True, capture_output=True)
        ref = open("out/_ref.html").read()
        rids = re.findall(r"<section class=page id='([^']+)'", ref)
        jl, jt = strip(r["html"]); pl, pt = strip(re.sub(r"<style>.*?</style>", "", ref, flags=re.S))
        pt = pt.replace("The Folio ", "", 1) if False else pt
        same_ids = r["ids"] == rids
        same_links = jl == pl
        # moon text on day pages
        jm = re.findall(r"(new moon|first quarter|full moon|last quarter) at \d\d:\d\d", jt)
        pm = re.findall(r"(new moon|first quarter|full moon|last quarter) at \d\d:\d\d", pt)
        jtimes = re.findall(r"(?:new moon|first quarter|full moon|last quarter) at (\d\d:\d\d)", jt)
        ptimes = re.findall(r"(?:new moon|first quarter|full moon|last quarter) at (\d\d:\d\d)", pt)
        jw = re.findall(r"\d+ \w{3} – \d+ \w{3} \d{4}", jt); pw_ = re.findall(r"\d+ \w{3} – \d+ \w{3} \d{4}", pt)
        print(cfg["start"], "sun" if cfg["sunday"] else "mon", "weekly" if cfg["weekly"] else "daily", cfg["tz"])
        print("  pages", len(r["ids"]), len(rids), "ids", same_ids, "| links", len(jl), len(pl), same_links,
              "| moon events", jm == pm, len(jm), "times", jtimes == ptimes, "| week spans", jw == pw_)
        if not same_links:
            for i, (a, c) in enumerate(zip(jl, pl)):
                if a != c: print("   first link diff at", i, a, c); break
        if jtimes != ptimes:
            for a, c in zip(jtimes, ptimes):
                if a != c: print("   time diff", a, c); break
    b.close()
