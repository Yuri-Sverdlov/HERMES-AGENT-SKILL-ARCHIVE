import os, time, json, sys
import pymupdf
from rapidocr_onnxruntime import RapidOCR

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
# usage: run_ocr.py <book.pdf> [...]  -> <book>.ocr.json next to each pdf
BOOKS = [(os.path.basename(p), p) for p in sys.argv[1:]]
if not BOOKS:
    sys.exit("usage: run_ocr.py <book.pdf> [more.pdf ...]")
DPI = 220
LOG = os.path.join(WORK, "ocr.log")

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")

ocr = RapidOCR()
log("engine ready")
t_all = time.time()
for title, fname in BOOKS:
    src = fname
    d = pymupdf.open(src)
    out_pages = []
    t0 = time.time()
    for i in range(d.page_count):
        pix = d[i].get_pixmap(dpi=DPI)
        png = os.path.join(WORK, "page.png")
        pix.save(png)
        res, _ = ocr(png)
        txt = "\n".join(x[1] for x in res) if res else ""
        out_pages.append({"page": i + 1, "text": txt})
        if (i + 1) % 25 == 0 or i + 1 == d.page_count:
            el = time.time() - t0
            log(f"{title}: {i+1}/{d.page_count} pages | {el:.0f}s | {el/(i+1):.2f}s/page | eta {(d.page_count-i-1)*el/(i+1)/60:.0f} min")
    dst = fname[:-4] + ".ocr.json"
    json.dump(out_pages, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    chars = sum(len(p["text"]) for p in out_pages)
    log(f"DONE {title}: {d.page_count} pages, {chars} chars -> {os.path.basename(dst)} | {(time.time()-t0)/60:.1f} min")
log(f"ALL DONE in {(time.time()-t_all)/60:.1f} min")
