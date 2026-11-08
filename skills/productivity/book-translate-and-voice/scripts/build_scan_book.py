"""Сборка книги из постраничных OCR-файлов (выход scripts/ocr_scan_ru.py):
склейка слов, разорванных переносом, схлопывание соседних пометок, обрезка хвоста, нарезка на блоки.

    python build_scan_book.py "<Book Key>" --pages-dir <scan> --last-page 27

ВАЖНО: последние страницы скриншот-книг часто заняты интерфейсом мобильного приложения
(«ВРОАТЕ», «Далее > К описанию») — это не книга, такие страницы отсекаются --last-page,
значение определяется глазами по последним 2-3 страницам.
"""
import os, re, json, glob, argparse

MARK = "пропуск строки"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--pages-dir", required=True)
    ap.add_argument("--last-page", type=int, default=None)
    ap.add_argument("--work", default=os.environ.get("BOOK_WORK_DIR",
                     os.path.expandvars(r"%LOCALAPPDATA%\hermes\audio-work")))
    ap.add_argument("--target-words", type=int, default=850)
    a = ap.parse_args()

    paras, marks = [], []
    for p in sorted(glob.glob(os.path.join(a.pages_dir, "page_*.txt"))):
        pno = int(re.search(r"page_(\d+)", p).group(1))
        if a.last_page and pno > a.last_page:
            continue
        for para in re.split(r"\n\s*\n", open(p, encoding="utf-8").read()):
            para = para.strip()
            if not para:
                continue
            if para == MARK:
                if not (paras and paras[-1] == MARK):
                    paras.append(MARK); marks.append(pno)
                continue
            paras.append(para)

    # склейка переносов: "возник-" + "шей ..." -> "возникшей ..."
    joined, i = [], 0
    while i < len(paras):
        cur = paras[i]
        while (cur.endswith("-") and not cur.endswith(" -") and i + 1 < len(paras)
               and paras[i + 1] != MARK and paras[i + 1][:1].islower()):
            cur = cur[:-1] + paras[i + 1]; i += 1
        joined.append(cur); i += 1

    final = []
    for p in joined:
        p = re.sub(r"\s{2,}", " ", p).strip()
        if not p:
            continue
        if p == MARK and final and final[-1] == MARK:
            continue
        final.append(p)

    text = "\n\n".join(final)
    out = os.path.join(a.work, "en", a.key)
    os.makedirs(os.path.join(out, "chunks_ru"), exist_ok=True)
    open(os.path.join(out, "source_ru.md"), "w", encoding="utf-8").write(text + "\n")

    chunks, cur, n = [], [], 0
    for b in final:
        w = len(b.split())
        if cur and n + w > a.target_words:
            chunks.append(cur); cur, n = [], 0
        cur.append(b); n += w
    if cur:
        chunks.append(cur)

    for f in glob.glob(os.path.join(out, "chunks_ru", "*.md")):
        os.remove(f)
    man = []
    for i, ch in enumerate(chunks, 1):
        s = "\n\n".join(ch).strip() + "\n"
        open(os.path.join(out, "chunks_ru", f"{i:03d}.md"), "w", encoding="utf-8").write(s)
        man.append({"n": i, "words": len(s.split()), "marks": s.count(MARK)})
    json.dump(man, open(os.path.join(out, "chunks_ru.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{a.key}: {len(text)} знаков, {len(text.split())} слов, блоков {len(chunks)}, "
          f"пометок {text.count(MARK)} (страницы {sorted(set(marks))})")
    print(f"оценка аудио: {len(text)/14.4/3600:.2f} ч")


if __name__ == "__main__":
    main()
