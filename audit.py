"""Check that every internal link in the Folio lands on the page that
carries the matching id in the source HTML."""
import re, sys, collections
from pypdf import PdfReader
pdf, html = sys.argv[1], sys.argv[2]
import json
ids = json.load(open(html)) if html.endswith(".json") else re.findall(r"<section class=page id='([^']+)'", open(html).read())
page_of = {pid: i for i, pid in enumerate(ids)}
r = PdfReader(pdf)
named = r.named_destinations
pages = {p.indirect_reference.idnum: i for i, p in enumerate(r.pages)}
total = ok = 0
bad = collections.Counter()
missing_tabs = []
for i, p in enumerate(r.pages):
    n_here = 0
    for a in p.get("/Annots", []) or []:
        a = a.get_object()
        if a.get("/Subtype") != "/Link":
            continue
        total += 1; n_here += 1
        d = a.get("/Dest")
        if d is not None and not isinstance(d, str) and hasattr(d, "__getitem__") and len(d) and hasattr(d[0], "idnum"):
            ok += 1 if d[0].idnum in pages else 0
            if d[0].idnum not in pages: bad["explicit dest to missing page"] += 1
            continue
        if d is None and "/A" in a:
            act = a["/A"]
            d = act.get("/D") if act.get("/S") == "/GoTo" else None
            if d is None:
                bad["external:" + str(act.get("/URI"))[:40]] += 1
                continue
        if isinstance(d, str) or hasattr(d, "startswith"):
            name = str(d)
            if name not in named:
                bad["unknown name " + name] += 1; continue
            target = pages.get(named[name].page.idnum) if hasattr(named[name].page, "idnum") else r.get_destination_page_number(named[name])
            if name in page_of and target != page_of[name]:
                bad[f"wrong page {name}: {target} vs {page_of[name]}"] += 1; continue
            ok += 1
        else:
            bad["array dest"] += 1
    if n_here < 20:
        missing_tabs.append((i + 1, n_here))
print(f"pages {len(r.pages)}  links {total}  ok {ok}  named dests {len(named)}")
print("problems:", dict(bad.most_common(10)) or "none")
print("pages with fewer than 20 links:", missing_tabs[:10] or "none")
