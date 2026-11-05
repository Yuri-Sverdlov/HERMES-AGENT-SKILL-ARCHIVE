"""Clean + chunk a PDF that HAS a good text layer (no OCR needed).
Usage: python clean_pdf.py <src.pdf> "<Book Key>" [ascii_name]
Strip running heads/page numbers, rebuild paragraphs,
split into ~850-word chunks for translation."""
import os, re, sys, json, shutil
import pymupdf

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
TARGET = 850


def clean_pages(pages):
    """pages: list[str] -> (lines, dropped_heads)"""
    # detect running heads: short lines repeated on many pages
    from collections import Counter
    cnt = Counter()
    for t in pages:
        seen = set()
        for ln in t.split("\n"):
            s = ln.strip()
            if 0 < len(s) <= 60 and s not in seen:
                seen.add(s)
                cnt[s] += 1
    repeats = {s for s, n in cnt.items() if n >= max(8, len(pages) * 0.15) and not re.search(r"[.!?]$", s)}
    out = []
    for t in pages:
        for ln in t.split("\n"):
            s = ln.strip()
            if not s or s in repeats or re.fullmatch(r"\d{1,4}", s):
                continue
            s = re.sub(r"\s{2,}", " ", s)
            if len(s) < 3:
                continue
            out.append(s)
    return out, repeats


def build_paragraphs(lines):
    if not lines:
        return []
    lens = [len(l) for l in lines]
    full = sorted(lens)[int(len(lens) * 0.7)]
    paras, cur = [], lines[0]
    for prev, nxt in zip(lines, lines[1:]):
        head = bool(re.match(r"^(\d+\.\s+[A-Z]|Part\s+[IVX]+|Chapter\s+\d+|Step\s+\d+|[A-Z][A-Z\s\"'\-]{6,})", nxt))
        if head or (re.search(r"[.!?\"'\u201d)]$", prev) and len(prev) < full * 0.92):
            paras.append(cur.strip()); cur = nxt
        else:
            cur = cur[:-1] + nxt if cur.endswith("-") and not cur.endswith(" -") else cur + " " + nxt
    paras.append(cur.strip())
    return paras


def chunk_paragraphs(paras, target=TARGET):
    blocks = []
    for p in paras:
        if len(p.split()) > target * 1.4:
            sents = re.split(r"(?<=[.!?])\s+", p)
            cur = ""
            for s in sents:
                if cur and len(cur.split()) + len(s.split()) > target:
                    blocks.append(cur.strip()); cur = s
                else:
                    cur = (cur + " " + s).strip()
            if cur:
                blocks.append(cur.strip())
        else:
            blocks.append(p)
    chunks, cur, n = [], [], 0
    for b in blocks:
        w = len(b.split())
        if cur and n + w > target:
            chunks.append(cur); cur, n = [], 0
        cur.append(b); n += w
    if cur:
        chunks.append(cur)
    return chunks


def run(src, key, ascii_name=None):
    os.makedirs(os.path.join(WORK, "books"), exist_ok=True)
    if ascii_name:
        dst = os.path.join(WORK, "books", ascii_name)
        shutil.copyfile(src, dst)
    d = pymupdf.open(src)
    pages = [d[i].get_text() for i in range(d.page_count)]
    lines, repeats = clean_pages(pages)
    paras = build_paragraphs(lines)
    paras = [p for p in paras if len(p.split()) > 2]
    chunks = chunk_paragraphs(paras)
    text = "\n\n".join(paras)
    out = os.path.join(WORK, "en", key)
    os.makedirs(os.path.join(out, "chunks_en"), exist_ok=True)
    open(os.path.join(out, "source.md"), "w", encoding="utf-8").write(text + "\n")
    man = []
    for i, ch in enumerate(chunks, 1):
        s = "\n\n".join(ch).strip() + "\n"
        p = os.path.join(out, "chunks_en", f"{i:03d}.md")
        open(p, "w", encoding="utf-8").write(s)
        man.append({"n": i, "path": p, "words": len(s.split())})
    json.dump(man, open(os.path.join(out, "chunks_en.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{key}: {d.page_count} pages, {len(text)} chars, {len(text.split())} words, "
          f"{len(paras)} paragraphs, {len(chunks)} chunks (avg {sum(m['words'] for m in man)//max(1,len(man))} w)")
    print("dropped running heads (sample):", list(repeats)[:8])
    return out


if __name__ == "__main__":
    src, key = sys.argv[1], sys.argv[2]
    ascii_name = sys.argv[3] if len(sys.argv) > 3 else None
    run(src, key, ascii_name)
