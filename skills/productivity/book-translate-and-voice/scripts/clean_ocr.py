
"""Clean + chunk OCR output (<book>.ocr.json from run_ocr.py) into $BOOK_WORK_DIR/en/<Book Key>/.
Usage: python clean_ocr.py <book.ocr.json> "<Book Key>"
HEADS = running heads to drop — edit per book."""
import os, re, json, sys
WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
HEADS = [r"10[.,]?\s*0?0?0\s*WORDS\s*AN\s*HOUR", r"FROM\s*ZERO\s*TO\s*PUBLISHED", r"THE\s*PLOT\s*MODULE", r"JASON\s*HAMILTON", r"MYTH\s*HQ"]
TARGET = 850

def clean_text(t):
    out = []
    for ln in t.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if any(re.fullmatch(rf"{h}\s*\d{{0,3}}", s, re.I) for h in HEADS):
            continue
        if re.fullmatch(r"\d{1,3}", s):
            continue
        # junk lines: watermark/logo garbage from OCR (e.g. "]yTbHQ", "Myth HQ,LLC" fragments)
        letters = sum(1 for c in s if c.isalpha())
        odd = sum(1 for c in s if not c.isalnum() and c not in " .,;:!?'\"-–—()[]%$/&*+=")
        if letters < 3 or (odd > len(s) * 0.3 and len(s) < 30):
            continue
        if re.search(r"[A-Za-z]{1,3}[HQhq]{1,2}\b", s) and len(s) < 40 and not s.endswith(('.', '!', '?')):
            continue
        s = re.sub(r"\s*10[.,]?\s*0?0?0\s*WORDS\s*AN\s*HOUR\s*", " ", s)
        s = re.sub(r"\s*(FROM\s*ZERO\s*TO\s*PUBLISHED|THE\s*PLOT\s*MODULE)\s*", " ", s, flags=re.I)
        s = re.sub(r"\s*JASON\s*HAMILTON\s*", " ", s, flags=re.I)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if len(s) < 3:
            continue
        out.append(s)
    return out

def build_paragraphs(lines):
    """join OCR lines into paragraphs; start a new paragraph on short-line + sentence end"""
    if not lines:
        return []
    lens = [len(l) for l in lines]
    full = sorted(lens)[int(len(lens) * 0.7)] if lens else 60
    paras, cur = [], lines[0]
    for prev, nxt in zip(lines, lines[1:]):
        new_para = False
        if re.search(r"[.!?\"'\u201d)]$", prev) and len(prev) < full * 0.92:
            new_para = True
        if re.match(r"^(\d+\.\s+[A-Z]|Part\s+[IVX]+|Chapter\s+\d+|Step\s+\d+|[A-Z][A-Z\s\"'\-]{6,}$)", nxt):
            new_para = True
        if new_para:
            paras.append(cur.strip())
            cur = nxt
        else:
            if cur.endswith("-") and not cur.endswith(" -"):
                cur = cur[:-1] + nxt
            else:
                cur = cur + (" " if not cur.endswith(" ") else "") + nxt
    paras.append(cur.strip())
    return paras

def chunk_paragraph(p, target=TARGET):
    """split an oversized paragraph at sentence boundaries"""
    sents = re.split(r"(?<=[.!?])\s+", p)
    out, cur = [], ""
    for s in sents:
        if cur and len(cur.split()) + len(s.split()) > target:
            out.append(cur.strip()); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur.strip())
    return out

def run(key, ocr_json):
    pages = json.load(open(ocr_json, encoding="utf-8"))
    lines = clean_text("\n".join(p["text"] for p in pages))
    paras = build_paragraphs(lines)
    blocks = []
    for p in paras:
        if len(p.split()) > TARGET * 1.4:
            blocks += chunk_paragraph(p)
        else:
            blocks.append(p)
    chunks, cur, n = [], [], 0
    for b in blocks:
        w = len(b.split())
        if cur and n + w > TARGET:
            chunks.append(cur); cur, n = [], 0
        cur.append(b); n += w
    if cur:
        chunks.append(cur)
    d = os.path.join(WORK, "en", key)
    os.makedirs(os.path.join(d, "chunks_en"), exist_ok=True)
    text = "\n\n".join(paras)
    open(os.path.join(d, "source.md"), "w", encoding="utf-8").write(text + "\n")
    man = []
    for i, ch in enumerate(chunks, 1):
        s = "\n\n".join(ch).strip() + "\n"
        p = os.path.join(d, "chunks_en", f"{i:03d}.md")
        open(p, "w", encoding="utf-8").write(s)
        man.append({"n": i, "path": p, "words": len(s.split())})
    json.dump(man, open(os.path.join(d, "chunks_en.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{key}: {len(text)} chars, {len(text.split())} words, {len(paras)} paragraphs, {len(chunks)} chunks "
          f"(avg {sum(m['words'] for m in man)//max(1,len(man))} w, max {max(m['words'] for m in man)})")
    return d

if len(sys.argv) < 3:
    sys.exit(__doc__)
d = run(sys.argv[2], sys.argv[1])
words = set(w.strip().lower() for w in open(os.path.join(WORK,"words_alpha.txt"), encoding="utf-8", errors="ignore"))
txt = open(os.path.join(d, "source.md"), encoding="utf-8").read()
toks = re.findall(r"[A-Za-z][A-Za-z']{1,}", txt)
good = sum(1 for t in toks if t.lower().strip("'") in words)
print(f"\nword recognition: {good/len(toks)*100:.1f}% of {len(toks)} tokens")
print("\n=== sample (middle of book) ===")
print(txt[150000:151200])
