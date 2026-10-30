"""Build Folio PDFs from the same generator the web builder uses (docs/folio.js).

    python3 build.py                                  # daily, Monday weeks, Aug 2026
    python3 build.py --weekly --sunday
    python3 build.py --start 2027-01 --months 6 --courses "Quantum Mechanics:QM,Real Analysis:Analysis"

Chromium renders the pages and prints them; postprocess.py then stores the
template images as grayscale and turns every link into an explicit page
destination.
"""
import argparse, json, os, pathlib, subprocess, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--sunday", action="store_true")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--left", type=int, default=56)
    ap.add_argument("--owner", default="")
    ap.add_argument("--courses", default="", help='"Full name:TAB,Full name:TAB" (default: six unnamed courses)')
    ap.add_argument("--no-courses", action="store_true", help="no courses at all: no course tabs or sections, no term map")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    courses = [{"name": "", "tab": ""} for _ in range(6)]
    if a.no_courses:
        courses = []
    elif a.courses:
        courses = []
        for part in a.courses.split(","):
            name, _, tab = part.partition(":")
            courses.append({"name": name.strip(), "tab": (tab or name).strip()[:8]})
    cfg = dict(start=a.start, months=a.months, sunday=a.sunday, weekly=a.weekly, tz=a.tz, left=a.left, owner=a.owner, courses=courses)
    out = pathlib.Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name(out.stem + ".raw.pdf")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1404, "height": 1872})
        pg.goto((HERE / "docs/_harness.html").as_uri())
        res = pg.evaluate("cfg => { const r = Folio.render(cfg, document.getElementById('folio')); return {n: r.pages, ids: r.ids}; }", cfg)
        n = res["n"]
        pg.evaluate("document.fonts.ready")
        pg.wait_for_function("[...document.images].every(i => i.complete)")
        pg.evaluate("Folio.paper(document.getElementById('folio'))")
        pg.pdf(path=str(raw), width="1404px", height="1872px", print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        b.close()
    subprocess.run([sys.executable, str(HERE / "postprocess.py"), str(raw), str(out)], check=True, capture_output=True)
    if not os.environ.get("FOLIO_KEEP_RAW"): raw.unlink()
    (out.parent / (out.stem + ".ids.json")).write_text(json.dumps(res["ids"]))
    print(f"{n} pages -> {out} ({out.stat().st_size / 1e6:.1f} MB)")

if __name__ == "__main__":
    main()
