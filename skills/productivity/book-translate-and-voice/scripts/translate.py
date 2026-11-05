"""Batch-translate EN chunks -> RU via OpenRouter, with validation, retries and resume."""
import os, re, json, sys, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
MODEL = "deepseek/deepseek-v4.1-flash"
API = "https://openrouter.ai/api/v1/chat/completions"
WORKERS = int(os.environ.get("TR_WORKERS", "8"))
LOG = os.path.join(WORK, "translate.log")

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

GLOSSARY = """beat → бит; beat sheet → бит-лист; pinch point → пинч-пойнт; midpoint → середина (midpoint);
inciting incident → завязка (inciting incident); Ordinary World → Обычный мир; New World → Новый мир;
B Story → линия B; save the cat → «спасти кота»; Plot Module → модуль сюжета; reader magnet → ридер-магнит;
Act → акт; Chapter → глава; protagonist → протагонист; antagonist → антагонист; scene → сцена;
outline → план-структура; stakes → ставки; trope → троп; genre → жанр; self-publishing → самиздат;
newsletter → рассылка (newsletter); mailing list → список рассылки; blurb → блирб; beta reader → бета-ридер;
plot twist → сюжетный поворот; foreshadowing → предвосхищение (foreshadowing); character arc → арка персонажа;
revision → редактура; drafting → черновик; POV → точка зрения (POV)."""

SYS = f"""Ты профессиональный переводчик. Переводишь книгу по писательскому мастерству (Jason Hamilton, Myth HQ) с английского на русский.

ПРАВИЛА:
1. Переводи ВЕСЬ текст блока целиком. Ничего не выбрасывать, не сокращать, не пересказывать, не добавлять от себя, не комментировать.
2. Сохраняй структуру: заголовки отдельной строкой, пункты списка с ведущим «- », нумерованные пункты («1. ...») с их номерами, пустые строки между абзацами.
3. Живой литературный русский без канцелярита; сохраняй авторскую интонацию и шутки.
4. Имена и бренды латиницей: Jason Hamilton, Myth HQ, ChatGPT, Claude, Amazon, KDP, Canva, Photoshop, Scrivener, Midjourney. Числа и диапазоны — как в оригинале.
5. Текст получен через OCR: возможны мелкие артефакты («10,0o0», «Al» вместо «AI», слипшиеся слова, пропавшая кавычка, мусорные обрывки строк). Молча исправляй по смыслу. Если фрагмент нечитаем — переведи ближайший осмысленный вариант, не оставляй английский текст.
6. Верни ТОЛЬКО перевод, без пояснений и без markdown-обёртки.

ГЛОССАРИЙ (соблюдать единообразно):
{GLOSSARY}"""

USAGE = {"in": 0, "out": 0}

def call(text, attempt=1):
    body = json.dumps({
        "model": MODEL,
        "temperature": 0.3,
        "max_tokens": 16000,
        # deepseek-v4.1-flash is a reasoning model: left on, it burns 3-8k tokens per chunk on
        # internal reasoning, sometimes eating the whole budget and returning empty content.
        # Disabled it is ~3x cheaper, 3-4x faster and yields the same translation quality.
        "reasoning": {"enabled": False},
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": text}],
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
        "X-Title": "book-translate"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    u = d.get("usage") or {}
    USAGE["in"] += u.get("prompt_tokens", 0)
    USAGE["out"] += u.get("completion_tokens", 0)
    msg = d["choices"][0].get("message") or {}
    content = msg.get("content") or msg.get("reasoning_content")
    if not content or not str(content).strip():
        raise RuntimeError(f"empty content: {json.dumps(d)[:160]}")
    return str(content)

def looks_translated(en, ru):
    if not ru or len(ru.strip()) < 40:
        return False, "too short"
    cyr = sum(1 for c in ru if "\u0400" <= c <= "\u04ff")
    alpha = sum(1 for c in ru if c.isalpha())
    if alpha and cyr / alpha < 0.55:
        return False, f"cyrillic ratio {cyr/max(1,alpha):.2f}"
    ratio = len(ru) / max(1, len(en))
    if not (0.75 <= ratio <= 2.2):
        return False, f"length ratio {ratio:.2f}"
    return True, ""

def translate_one(args):
    book, path = args
    n = os.path.basename(path)
    outdir = os.path.join(WORK, "en", book, "chunks_ru")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, n)
    if os.path.exists(out) and len(open(out, encoding="utf-8").read()) > 40:
        return (n, "skip", 0)
    en = open(path, encoding="utf-8").read()
    last = ""
    for attempt in range(1, 4):
        try:
            ru = call(en, attempt).strip()
            ok, why = looks_translated(en, ru)
            if ok:
                ru = re.sub(r"^```[a-z]*\n|```$", "", ru).strip()
                open(out, "w", encoding="utf-8").write(ru + "\n")
                return (n, f"ok ({len(en)}->{len(ru)} chars)", attempt)
            last = why
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(3 * attempt)
    log(f"!! {book}/{n}: {last}")
    return (n, f"FAILED: {last}", 0)

def run_book(book):
    d = os.path.join(WORK, "en", book, "chunks_en")
    files = sorted(f for f in os.listdir(d) if f.endswith(".md"))
    log(f"=== {book}: {len(files)} chunks, {WORKERS} workers")
    t0 = time.time()
    done = fails = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for name, status, att in ex.map(translate_one, [(book, os.path.join(d, f)) for f in files]):
            if status.startswith("ok"):
                done += 1
                if done % 10 == 0:
                    log(f"   {book}: {done}/{len(files)} done, {time.time()-t0:.0f}s")
            elif status == "skip":
                done += 1
            else:
                fails += 1
    log(f"=== {book}: {done} ok, {fails} failed in {(time.time()-t0)/60:.1f} min")

if __name__ == "__main__":
    books = sys.argv[1:]
    if not books:
        sys.exit('usage: translate.py "<Book Key>" [...]   (chunks in $BOOK_WORK_DIR/en/<Book Key>/chunks_en)')
    for b in books:
        run_book(b)
    # deepseek-v4.1-flash list price on OpenRouter (per 1M tokens), for a rough figure only
    cost = USAGE["in"] / 1e6 * 0.14 + USAGE["out"] / 1e6 * 0.28
    log(f"TRANSLATION DONE | tokens in={USAGE['in']} out={USAGE['out']} | approx ${cost:.2f}")
