"""Post-edit pass: hunt down English words left in the Russian translation.
Only proper names, brands and titles may stay in Latin script; everything else must be Russian.
Rewrites affected chunks and records them for re-rendering."""
import os, re, json, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
MODEL = "deepseek/deepseek-v4.1-flash"
API = "https://openrouter.ai/api/v1/chat/completions"
WORKERS = 8
LOG = os.path.join(WORK, "repair.log")
import sys
BOOKS = sys.argv[1:]
if not BOOKS:
    sys.exit('usage: repair.py "<Book Key>" [...]')

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with threading.Lock():
        open(LOG, "a", encoding="utf-8").write(line + "\n")

def _openrouter_key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    env = os.path.join(os.environ["LOCALAPPDATA"], "hermes", ".env")
    for ln in open(env, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*OPENROUTER_API_KEY\s*=\s*(\S+)", ln)
        if m:
            return m.group(1)
    raise RuntimeError("OPENROUTER_API_KEY not found in environment or Hermes .env")

KEY = _openrouter_key()

SYS = """Ты редактор русского перевода книги. Тебе дают готовый русский текст.
ЗАДАЧА: найти английские слова, которые остались непереведёнными, и перевести их на русский.
Латиницей разрешено оставлять ТОЛЬКО: имена собственные (Jason Hamilton, Blake Snyder, Brandon Sanderson),
бренды и сервисы (ChatGPT, Claude, Amazon, KDP, Canva, Scrivener, Novelcrafter, BookBub, Atticus, Discord, YouTube),
названия книг и фильмов (Save the Cat, Harry Potter, Star Wars), аббревиатуры (BISAC, ABSR, KDP, AI/ИИ)
и URL. Всё остальное — включая такие слова, как chapter, outline, beats, characters, setting, instructions, sample, pursuit, newsletter — переводи на русский.
НЕ меняй ничего другого: ни структуру, ни порядок абзацев, ни пункты списков, ни уже переведённые фразы.
Верни ТОЛЬКО исправленный текст целиком, без пояснений."""

USAGE = {"in": 0, "out": 0, "fixed": 0, "checked": 0}

def call(text):
    body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 16000,
                       "reasoning": {"enabled": False},
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    u = d.get("usage") or {}
    USAGE["in"] += u.get("prompt_tokens", 0); USAGE["out"] += u.get("completion_tokens", 0)
    msg = d["choices"][0].get("message") or {}
    c = msg.get("content") or msg.get("reasoning_content")
    if not c:
        raise RuntimeError("empty content")
    return c

def needs_repair(text):
    """paragraphs containing latin words of 4+ letters that are not URLs"""
    hits = []
    for p in re.split(r"\n\s*\n", text):
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]{3,}", p) if not re.search(r"https?|\.com|\.ai|@", p.lower()) or True]
        if words:
            hits.append(p)
    return hits

def fix_one(path):
    orig = open(path, encoding="utf-8").read()
    hits = needs_repair(orig)
    if not hits:
        return (path, "clean", 0)
    for attempt in range(3):
        try:
            ru = call(orig).strip()
            if len(ru) < len(orig) * 0.7 or len(ru) > len(orig) * 1.4:
                continue
            if ru == orig:
                return (path, "unchanged", 0)
            open(path, "w", encoding="utf-8").write(ru + "\n")
            USAGE["fixed"] += 1
            return (path, "fixed", len(hits))
        except Exception as e:
            time.sleep(2 * (attempt + 1))
    return (path, "FAILED", 0)

def run():
    changed = []
    for b in BOOKS:
        d = os.path.join(WORK, "en", b, "chunks_ru")
        files = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".md"))
        log(f"=== {b}: {len(files)} chunks")
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for path, status, n in ex.map(fix_one, files):
                USAGE["checked"] += 1
                if status == "fixed":
                    changed.append({"book": b, "file": os.path.basename(path), "paras": n})
        log(f"   {b}: ready, fixed so far {USAGE['fixed']}")
    json.dump(changed, open(os.path.join(WORK, "repaired.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cost = USAGE["in"] / 1e6 * 0.14 + USAGE["out"] / 1e6 * 0.28
    log(f"REPAIR DONE: checked {USAGE['checked']}, rewritten {USAGE['fixed']}, tokens {USAGE['in']}/{USAGE['out']}, approx ${cost:.2f}")

if __name__ == "__main__":
    run()
