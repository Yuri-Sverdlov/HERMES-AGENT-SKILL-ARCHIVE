"""Score a PDF text layer: share of tokens found in an English wordlist + control chars.
Usage: python score_text_layer.py <file.pdf> [first_page last_page]
Wordlist: $BOOK_WORK_DIR/words_alpha.txt (dwyl/english-words)."""
import os, re, sys, collections
import pymupdf

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
words = set(w.strip().lower() for w in open(os.path.join(WORK, "words_alpha.txt"), encoding="utf-8", errors="ignore"))

def score(txt):
    toks = re.findall(r"[A-Za-z][A-Za-z']{1,}", txt)
    good = sum(1 for t in toks if t.lower().strip("'") in words)
    return (good / len(toks) if toks else 0), len(toks)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = pymupdf.open(sys.argv[1])
    a = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
    b = int(sys.argv[3]) if len(sys.argv) > 3 else d.page_count
    txt = "\n".join(d[i].get_text() for i in range(a, b))
    s, n = score(txt)
    print(f"{os.path.basename(sys.argv[1])}: pages {a+1}-{b}: {s*100:.1f}% of {n} tokens are dictionary words")
    cnt = collections.Counter(c for c in txt if ord(c) < 32 and c != "\n")
    print("control chars:", {repr(k): v for k, v in cnt.most_common(10)})
