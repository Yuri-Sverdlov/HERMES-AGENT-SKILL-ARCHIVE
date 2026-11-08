"""OCR скриншот-PDF на русском через Tesseract (rus) с пометками «пропуск строки».

Зачем: RapidOCR (scripts/run_ocr.py) для кириллицы НЕ подходит — его дефолтные модели
китайско-английские и превращают русские буквы в латинские двойники
(«Чувственное зеркало» -> «YyBCTBeHHOe 3epKanlo»).

Использование:
    python ocr_scan_ru.py book.pdf [--out DIR] [--pages 1-27] [--dpi 300]

Что нужно заранее:
  * Tesseract 5.x в C:\\Program Files\\Tesseract-OCR\\tesseract.exe (в PATH его обычно нет);
  * rus.traineddata из tessdata_best, положенный в СВОЮ папку (не в Program Files),
    передаётся через --tessdata-dir. По умолчанию рядом со скриптом: <work>/tessdata.

Правила пометок (по требованию владельца):
  * пометка ставится в ЛЮБОМ месте, где строка не распозналась;
  * подряд идущие плохие строки дают ОДНУ пометку;
  * рекламные врезки выкидываются.
"""
import os, re, csv, statistics, subprocess, collections, argparse
import pymupdf

MARK = "пропуск строки"
AD_PAT = re.compile(r"(РЕКЛАМА|ТЕЛЕГРАМ|ТЕ!ЕДГАТ|Те!1едгат|граа!е|gramdate|@|ПОИСК\s*КНИГ|Книжный\s*Вестник|"
                    r"Канал\s*с\s*обзорами|Бот\s*для\s*удобн|24/7|ИИ-жена|ИИ-девушка|новинок\s*и\s*книжн|"
                    r"удобных\s*форматах|ВКОНТАКТЕ|вконтакте|афоризмы|книжные\s*подборки|БИБЛИОТЕКИ)", re.I)


def cyr_ratio(t):
    a = [c for c in t if c.isalpha()]
    return sum(1 for c in a if "\u0400" <= c <= "\u04ff") / len(a) if a else 0.0


def ocr_page(doc, pno, tess, tdata, work, dpi=300):
    png = os.path.join(work, f"_p{pno}.png")
    base = os.path.join(work, f"_p{pno}")
    doc[pno - 1].get_pixmap(dpi=dpi).save(png)
    subprocess.run([tess, png, base, "-l", "rus", "--tessdata-dir", tdata, "--psm", "3",
                    "-c", "tessedit_create_tsv=1"], capture_output=True, text=True, check=True)
    rows = list(csv.DictReader(open(base + ".tsv", encoding="utf-8"), delimiter="\t"))
    for f in (png, base + ".tsv"):
        try:
            os.remove(f)
        except OSError:
            pass
    words = [r for r in rows if r["level"] == "5" and (r["text"] or "").strip()]
    grouped = collections.defaultdict(list)
    for r in words:
        grouped[(r["block_num"], r["par_num"], r["line_num"])].append(r)
    out = []
    for ws in grouped.values():
        confs = [float(w["conf"]) for w in ws if w["conf"] not in ("-1", "")]
        top = min(int(w["top"]) for w in ws)
        bottom = max(int(w["top"]) + int(w["height"]) for w in ws)
        left = min(int(w["left"]) for w in ws)
        right = max(int(w["left"]) + int(w["width"]) for w in ws)
        out.append({"text": " ".join(w["text"] for w in ws).strip(),
                    "conf": sum(confs) / len(confs) if confs else 0.0,
                    "top": top, "left": left, "h": bottom - top, "w": right - left})
    out.sort(key=lambda L: L["top"])
    return out


def is_ad(L):
    return L["left"] > 1000 or bool(AD_PAT.search(L["text"]))


def page_text(lines):
    body = [L for L in lines if not is_ad(L)]
    if not body:
        return ""
    med_h = statistics.median([L["h"] for L in body])
    wide = [L["w"] for L in body if L["w"] > 200]
    med_w = statistics.median(wide) if wide else 0

    def bad(L):
        # уверенность / латинский мусор / обрезанная по высоте строка (разрез скриншота)
        return (L["conf"] < 60 or (len(L["text"]) > 8 and cyr_ratio(L["text"]) < 0.5)
                or L["h"] < med_h * 0.55)

    paras, cur, prev_bad, prev = [], "", False, None
    for L in body:
        if bad(L):
            if not prev_bad:
                if cur:
                    paras.append(cur.strip()); cur = ""
                paras.append(MARK); prev_bad = True
            continue
        prev_bad = False
        t = L["text"].strip()
        if not t:
            continue
        # граница абзаца — по ШИРИНЕ строки (короткая строка = конец абзаца), а не по длине текста
        short = bool(med_w) and L["w"] < med_w * 0.85
        sent = bool(prev) and bool(re.search(r"[.!?…»\"]$", prev["text"].strip()))
        if not cur:
            cur = t
        elif short or sent:
            paras.append(cur.strip()); cur = t
        elif cur.endswith("-") and not cur.endswith(" -"):
            cur = cur[:-1] + t
        else:
            cur = (cur + " " + t).strip()
        prev = L
    if cur:
        paras.append(cur.strip())
    return "\n\n".join(p for p in paras if p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default=os.path.join(os.environ.get("BOOK_WORK_DIR",
                     os.path.expandvars(r"%LOCALAPPDATA%\hermes\audio-work")), "scan"))
    ap.add_argument("--tess", default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    ap.add_argument("--tessdata-dir", default=None)
    ap.add_argument("--pages", default=None, help="например 1-27")
    ap.add_argument("--dpi", type=int, default=300)
    a = ap.parse_args()
    work = os.environ.get("BOOK_WORK_DIR", os.path.expandvars(r"%LOCALAPPDATA%\hermes\audio-work"))
    tdata = a.tessdata_dir or os.path.join(work, "tessdata")
    if not os.path.exists(os.path.join(tdata, "rus.traineddata")):
        raise SystemExit(f"нет rus.traineddata в {tdata} — скачай из tessdata_best и положи туда")
    os.makedirs(a.out, exist_ok=True)
    doc = pymupdf.open(a.pdf)
    first, last = 1, doc.page_count
    if a.pages:
        m = re.match(r"(\d+)\s*-\s*(\d+)", a.pages)
        if m:
            first, last = int(m.group(1)), int(m.group(2))
    for pno in range(first, min(last, doc.page_count) + 1):
        txt = page_text(ocr_page(doc, pno, a.tess, tdata, work, a.dpi))
        open(os.path.join(a.out, f"page_{pno:02d}.txt"), "w", encoding="utf-8").write(txt + "\n")
        print(f"стр.{pno:02d}: пометок {txt.count(MARK):2d} | знаков {len(txt)}", flush=True)


if __name__ == "__main__":
    main()
