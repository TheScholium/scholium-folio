"""Post-process the Folio PDF.

1. Recompress the template images Chromium embeds as RGB into 8-bit gray.
2. Rewrite every link from a named destination to an explicit
   [page /Fit] destination, which every PDF reader understands, and drop
   the name tree.
"""
import sys, zlib, pikepdf
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
pdf = pikepdf.open(src)
done = set()
for page in pdf.pages:
    for name in list(page.Resources.get('/XObject', {}).keys()):
        if page.Resources.XObject[name].get('/Subtype') != '/Image': continue
        obj = page.Resources.XObject[name]
        if obj.objgen in done: continue
        done.add(obj.objgen)
        img = pikepdf.PdfImage(obj).as_pil_image().convert("L")
        obj.write(zlib.compress(img.tobytes(), 9), filter=pikepdf.Name.FlateDecode)
        obj.ColorSpace = pikepdf.Name.DeviceGray
        obj.BitsPerComponent = 8
        for k in ("/SMask", "/DecodeParms", "/Decode"):
            if k in obj: del obj[k]
# explicit destinations
names = {}
def walk(node):
    if "/Names" in node:
        arr = node.Names
        for i in range(0, len(arr), 2):
            d = arr[i + 1]
            d = d.D if isinstance(d, pikepdf.Dictionary) and "/D" in d else d
            names[str(arr[i])] = d
    for kid in node.get("/Kids", []):
        walk(kid)
root = pdf.Root
if "/Names" in root and "/Dests" in root.Names:
    walk(root.Names.Dests)
if "/Dests" in root:  # PDF 1.1 style: a plain dictionary of names
    for k, v in root.Dests.items():
        names[k.lstrip("/")] = v.D if isinstance(v, pikepdf.Dictionary) and "/D" in v else v
fixed = 0
for page in pdf.pages:
    for annot in page.get("/Annots", []):
        if annot.get("/Subtype") != "/Link":
            continue
        d = annot.get("/Dest")
        if d is None and "/A" in annot and annot.A.get("/S") == "/GoTo":
            d = annot.A.D
        key = str(d).lstrip("/") if d is not None else None
        if key in names:
            target = names[key][0]
            annot.Dest = pikepdf.Array([target, pikepdf.Name.Fit])
            if "/A" in annot:
                del annot["/A"]
            fixed += 1
if "/Names" in root and "/Dests" in root.Names:
    del root.Names["/Dests"]
if "/Dests" in root and fixed:
    del root["/Dests"]
print("links made explicit:", fixed)
pdf.save(dst, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
print("images recompressed:", len(done))
