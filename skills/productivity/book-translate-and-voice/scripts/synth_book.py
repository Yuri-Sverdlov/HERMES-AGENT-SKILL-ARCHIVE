"""RU chunks -> Silero speech -> per-section mp3 + combined mp3, 44.1k stereo 192k.
v2: resumable (skips rendered sections) and crash-proof (skips latin-only fragments,
retries a failing chunk sentence by sentence). RENDER_FORCE=1 re-renders everything."""
import os, re, sys, json, glob, subprocess, time
import numpy as np
import torch, soundfile as sf

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
OUT_ROOT = os.environ.get("BOOK_OUT_DIR") or os.path.join(WORK, "out")
SR = 48000
SPEAKER = "aidar"
CHUNK = 700
GAP = 0.25
FORCE = os.environ.get("RENDER_FORCE") == "1"
LOG = os.path.join(WORK, "tts.log")
CYR = re.compile(r"[\u0400-\u04ff]")
_model = None

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")

def model():
    global _model
    if _model is None:
        m, _ = torch.hub.load(repo_or_dir="snakers4/silero-models", model="silero_tts",
                              language="ru", speaker="v4_ru", trust_repo=True)
        m.to(torch.device("cpu")); _model = m
    return _model

def to_speech(md):
    t = md.replace("\u200b", "")
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*•●]\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\bAI\b", "ИИ", t)
    t = t.replace("«", "").replace("»", "").replace("·", ",").replace("…", "...")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()

def chunks(text, size=CHUNK):
    parts, cur = [], ""
    for piece in re.split(r"(?<=[.!?;:])\s+|\n", text):
        if not piece.strip():
            continue
        if cur and len(cur) + len(piece) + 1 > size:
            parts.append(cur.strip()); cur = piece
        else:
            cur = (cur + " " + piece).strip()
    if cur:
        parts.append(cur.strip())
    return parts

def synth(text):
    """Mono float array, or None when nothing is speakable."""
    m = model(); audios = []
    for c in chunks(text):
        if not CYR.search(c):
            continue
        try:
            a = m.apply_tts(text=c, speaker=SPEAKER, sample_rate=SR)
        except Exception as e:
            log(f"      ! chunk failed ({type(e).__name__}, {len(c)} chars) -> per-sentence retry")
            for s in re.split(r"(?<=[.!?])\s+", c):
                if not CYR.search(s):
                    continue
                try:
                    a2 = m.apply_tts(text=s, speaker=SPEAKER, sample_rate=SR)
                    audios.append(a2.numpy() if hasattr(a2, "numpy") else a2)
                    audios.append(np.zeros(int(GAP * SR), dtype="float32"))
                except Exception:
                    pass
            continue
        a = a.numpy() if hasattr(a, "numpy") else a
        audios.append(a); audios.append(np.zeros(int(GAP * SR), dtype="float32"))
    if not audios:
        return None
    if len(audios) > 1:
        audios.pop()
    return np.concatenate(audios)

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"FAILED {' '.join(cmd[:2])}: {p.stderr[-300:]}")
    return p

def synth_book(book):
    files = sorted(glob.glob(os.path.join(WORK, "en", book, "chunks_ru", "*.md")))
    if not files:
        log(f"!! {book}: no RU chunks"); return None
    outdir = os.path.join(OUT_ROOT, book); parts = os.path.join(WORK, "parts", book)
    os.makedirs(outdir, exist_ok=True); os.makedirs(parts, exist_ok=True)
    md_all = "\n\n".join(open(f, encoding="utf-8").read().strip() for f in files)
    open(os.path.join(outdir, f"{book} — RU.md"), "w", encoding="utf-8").write(md_all + "\n")

    norm, skipped, t_book = [], 0, time.time()
    for i, f in enumerate(files, 1):
        sec = os.path.join(outdir, f"{i:03d} — раздел {i}.mp3")
        if not FORCE and os.path.exists(sec) and os.path.getsize(sec) > 1024:
            norm.append(sec); skipped += 1
            continue
        sp = to_speech(open(f, encoding="utf-8").read())
        if not sp.strip():
            log(f"   {book} §{i:03d}: пусто после чистки, пропуск"); continue
        audio = synth(sp)
        if audio is None:
            log(f"   {book} §{i:03d}: нет русской речи (ссылки/каталог), пропуск"); continue
        wav = os.path.join(parts, f"{i:03d}.wav")
        sf.write(wav, audio, SR)
        run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-ar", "44100", "-ac", "2", "-b:a", "192k",
             "-write_xing", "1", "-metadata", f"title={book} — раздел {i}", "-metadata",
             "artist=Jason Hamilton", "-metadata", f"album={book} (RU)", sec])
        os.remove(wav)
        norm.append(sec)
        log(f"   {book} §{i:03d}: {len(sp)} chars ({time.time()-t_book:.0f}s elapsed)")

    lst = os.path.join(parts, "list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for p in norm:
            fh.write("file '" + p.replace("\\", "/") + "'\n")
    full = os.path.join(outdir, f"{book} — RU (полная озвучка).mp3")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-ar", "44100", "-ac", "2", "-b:a", "192k", "-write_xing", "1", full])

    def dur(f):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                           capture_output=True, text=True)
        return float(r.stdout.strip())
    cum = 0.0; idx = []
    for p in norm:
        d = dur(p); idx.append((cum, os.path.basename(p), d)); cum += d
    def ts(s):
        s = int(round(s)); return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
    open(os.path.join(outdir, f"{book} — индекс разделов.md"), "w", encoding="utf-8").write(
        f"# {book} — RU, аудио\n\n| Начало | Раздел | Длительность |\n|---|---|---|\n" +
        "\n".join(f"| {ts(c)} | {f} | {d/60:.1f} мин |" for c, f, d in idx) +
        f"\n\n**Итого:** {ts(cum)} ({cum/3600:.2f} ч). Голос Silero {SPEAKER}. "
        f"Разделов: {len(norm)}. Полный файл: `{os.path.basename(full)}`.\n")
    log(f"== {book}: {len(norm)} sections ({skipped} already rendered) | audio {cum/60:.1f} min "
        f"({cum/3600:.2f} h) | book time {(time.time()-t_book)/60:.1f} min | full {os.path.getsize(full)/1048576:.0f} MB")
    return {"book": book, "sections": len(norm), "minutes": round(cum/60, 1), "full": full}

if __name__ == "__main__":
    books = sys.argv[1:]
    if not books:
        sys.exit('usage: synth_book.py "<Book Key>" [...]   (output: $BOOK_OUT_DIR)')
    res = [synth_book(b) for b in books]
    log("RESULT " + json.dumps(res, ensure_ascii=False))
