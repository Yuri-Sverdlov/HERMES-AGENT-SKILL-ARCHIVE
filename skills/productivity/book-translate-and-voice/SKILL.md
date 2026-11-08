---
name: book-translate-and-voice
description: Translate books/PDFs to Russian and voice as audiobooks.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [audiobook, tts, translation, pdf, silero, edge-tts, ocr, openrouter]
    related_skills: [pdf-broken-text-layer-repair, coder-terminal-workflow]
---

# Book translate + voice (RU audiobook)

## When to Use
- The user asks to translate a book/PDF into Russian, or to voice one ("озвучь книгу", "сделай аудио").
- A batch of PDFs has to become audiobooks in one consistent format.
- If the extracted text looks garbled (`writinN`, `coPer`), load `pdf-broken-text-layer-repair` first.
- If the source text has to be pulled off a reading site (reader page, not a PDF), load `reader-page-text-capture` first — it covers the access gate, chapter iteration and cleaning.

## Pipeline (order matters)
1. Extract text page-by-page with PyMuPDF (`import fitz`). Check `len(page.get_text())` and `page.get_images()` per page — empty text means a scan and needs OCR.
2. Sanity-check the layer before trusting it: dictionary-word ratio (`words_alpha.txt` from dwyl/english-words), control-char count, tell-tale substitutions. Clean text scores 99 %+; broken scores 0–60 %.
3. Clean: drop running heads (auto-detect by lines repeating on ≥15 % of pages), page numbers, watermark junk; rebuild paragraphs; strip `\u200b`; `●` lists → `-`.
4. Chunk to ~850 source words (≈65–105 chunks per book). Oversized blocks must be split at sentence boundaries, otherwise a whole book collapses into one 29 000-word chunk.
5. Translate (see the OpenRouter section below), then post-edit, and only after that render audio.
6. Synthesize each chunk, encode to 44.1 kHz stereo 192 kbps, concat by **re-encoding**, write an index with timecodes, and verify.

## Scripts (in this skill) — one per pipeline step
Work dir `$BOOK_WORK_DIR` (default `%LOCALAPPDATA%\hermes\audio-work`); a book lives in
`$BOOK_WORK_DIR/en/<Book Key>/` (`chunks_en/`, `chunks_ru/`). Audio goes to `$BOOK_OUT_DIR`
(default `$BOOK_WORK_DIR/out`). The OpenRouter key is read from `OPENROUTER_API_KEY` or the
Hermes `.env`. Always launch with a sanitised env (no `PYTHONPATH`, see Pitfalls).

| Step | Command | venv |
|---|---|---|
| OCR a scan (skip if the text layer is good) | `python "${HERMES_SKILL_DIR}/scripts/run_ocr.py" book.pdf` → `book.ocr.json` | `pymupdf rapidocr-onnxruntime` |
| Clean + chunk the OCR output | `python "${HERMES_SKILL_DIR}/scripts/clean_ocr.py" book.ocr.json "<Book Key>"` (edit `HEADS` per book) | stdlib |
| Clean + chunk a PDF with a good text layer | `python "${HERMES_SKILL_DIR}/scripts/clean_pdf.py" book.pdf "<Book Key>"` | `pymupdf` |
| Translate EN → RU | `python "${HERMES_SKILL_DIR}/scripts/translate.py" "<Book Key>"` | stdlib |
| Post-edit leftover English | `python "${HERMES_SKILL_DIR}/scripts/repair.py" "<Book Key>"` | stdlib |
| Voice (Silero) + combined mp3 + index | `python "${HERMES_SKILL_DIR}/scripts/synth_book.py" "<Book Key>"` | `sileroenv` (torch, soundfile, numpy) + ffmpeg |

All steps resume: re-running skips finished chunks/sections. The glossary inside `translate.py`
and the allow-list of Latin names in `repair.py` are book-specific — edit them per book.

## Choosing the engine (decide before the first render)
Swapping the voice after the fact re-renders the whole book, so the engine is picked once — before the first render,
and only once the text is frozen. Default stays Silero (offline, ~30× faster than the quality models).
Alternatives with measured RTF, licences, cloud per-character prices, a character-counting cost recipe and the
one-section A/B probe that must precede any re-render: `references/tts-engine-choice.md`.
Never start a full re-render without that probe and a stated cost in time and money — the user rejects re-work
whose value has not been demonstrated, and asks "зачем это нужно?" for anything that only changes timbre.

## TTS engine 1: edge-tts (good quality, unofficial free endpoint)
- Setup in its own venv: `uv venv "$W/ttsenv" --python 3.11`; `uv pip install --python "$W/ttsenv/Scripts/python.exe" edge-tts==7.3.1`. Never pip-install into the Hermes venv (no pip).
- Call: `"$W/ttsenv/Scripts/edge-tts.exe" --voice ru-RU-DmitryNeural --rate=-5% --file in.txt --write-media out.mp3`. Voices: `ru-RU-DmitryNeural` (male), `ru-RU-SvetlanaNeural` (female).
- **403 `Invalid response status` is usually a polluted child environment, not a stale library.** A child launched from Hermes inherits `PYTHONPATH` pointing at Hermes's own site-packages, so a foreign edge_tts/aiohttp is imported. Always run with a sanitised env (`clean = {k:v for k,v in os.environ.items() if k.upper() not in ("PYTHONPATH","PYTHONHOME","PYTHONSTARTUP")}`, `env=clean`). The same exe that 403'd then works.
- Bumping `CHROMIUM_FULL_VERSION` in `edge_tts/constants.py` does NOT fix 403 (verified across 143/144/145/148).
- Microsoft also blocks the WSS synthesis endpoint for hours at a time (403 on every request while HTTPS `voices/list` still answers). Retries and pauses do not help — fall back to Silero and re-render later if it returns.

## TTS engine 2: Silero v4_ru (offline, always works, fast)
- `uv venv "$W/sileroenv" --python 3.11`; `uv pip install --python .../python.exe torch --index-url https://download.pytorch.org/whl/cpu`; then `soundfile omegaconf numpy`.
- Load: `m, _ = torch.hub.load(repo_or_dir="snakers4/silero-models", model="silero_tts", language="ru", speaker="v4_ru", trust_repo=True)`; `m.apply_tts(text=..., speaker="aidar", sample_rate=48000)`.
- Male speakers: `aidar` (slower, deliberate — the user's pick), `eugene` (faster). Output 48 kHz, peak ~0.77, no clipping.
- Chunk text at ~700 chars on sentence boundaries, 0.25 s silence between chunks; neutralise `«»` and `·` first.
- **Hard length limit: ~900 chars.** `v4_ru` dies at 1000 chars with `Model couldn't generate your text, probably it's too long`.
  Short chunks cost you: measured 300 chars → RTF 0.101, 600 → 0.057, 900 → 0.025 (fixed per-call overhead dominates).
- Speakers in `v4_ru`: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`, `random`. SSML tags actually supported: `break`, `prosody`.
- `v5_ru` is newer (SSML richer, `v5_4_ru` handles questions, wider voice set, aliases changed: old `aidar` = `ru_eduard`).
  Switching is one line in the script — a free quality bump before any engine swap.
- Stress control: prefix a vowel with `+` (`зам+ок`, `т+ундра`) — the fix for English names and Russian homographs.
- Licence: Silero models are **CC BY-NC** (non-commercial), same for XTTS-v2 (CPML) and F5-TTS-ru (CC BY-NC).
  Commercially clean voices: Piper `denis`/`dmitri` (CC0), Kokoro (Apache-2.0). Chatterbox (MIT) watermarks its output.
- **numpy `No module named 'numpy._core._multiarray_umath'`** in a fresh venv is the same inherited-PYTHONPATH trap (a cp3xx numpy from Hermes shadows the venv's). Sanitise the env; reinstalling numpy does not help.

## Engine choice: when Silero is not enough
Silero is the *fast/reliable* pick, not the best-sounding one. Full comparison (local engines with measured RTF and licences,
cloud prices, cost recipe, A/B protocol): `references/tts-engine-choice.md`. Check the GPU with `nvidia-smi` — a profile
can name a card the machine does not have.
Order of improvement: text normalisation → stress marks → Silero v5 → Piper/XTTS/F5 — never re-render audio before the text is frozen.
Never swap engines without rendering the same section on both and letting the user's ear decide.

## Throughput (measured: i5-12400F CPU, torch 2.15.0+cpu, Silero aidar)
530–580 source chars/s → ~24 min of audio per minute of synthesis; 10 min of wall time ≈ 235 000 chars ≈ 4.4 h of audio. ffmpeg adds ~11 s per section. Planning rule: ~1 min of work per 100 000 chars, ~12 s per section end-to-end.

## Batch translation via OpenRouter API (not delegate_task per chunk)
For 100+ chunks drive the API from a script: plain `urllib` POST to `https://openrouter.ai/api/v1/chat/completions`, `ThreadPoolExecutor(max_workers=8)`, resume by skipping chunks whose output exists, validate each result (Cyrillic ≥ 0.55 of letters, RU/EN length ratio 0.75–2.2) before accepting.
- **Switch reasoning OFF on reasoning models.** `deepseek/deepseek-v4.1-flash` defaults to 3 000–8 400 `reasoning_tokens` per chunk (16–20 s, $0.0036) and when reasoning eats the `max_tokens` budget the API returns **empty `content`** (`NoneType has no attribute 'strip'`, or `finish_reason=length`). `"reasoning": {"enabled": false}` → same quality, 5 s, $0.0012. `"reasoning": {"effort": "low"}` does NOT help.
- Read the API key with an anchored `re.match(r"\s*KEY\s*=\s*(\S+)", line)`; a bare `re.search` over the whole `.env` matches the commented-out line and yields a 1-char key (`HTTP 401 Missing Authentication header`).
- Accumulate `usage` from every response and log the total: 274 chunks / 1.6 M chars cost ≈ $0.25 in total.
- A post-edit pass ("leave Latin script only for names, brands and titles") removes English words left in the prose; it rewrote 177 of 274 chunks for $0.11. Do it BEFORE rendering, and re-translate tail chunks ("About the Author", link lists, "Also by") by hand — they legitimately fail the Cyrillic-ratio check.

## Long jobs: resilience rules (learned the hard way)
- **Finish every text edit before rendering audio.** A post-edit pass rewrote 55 of 66 chunks while a render was already going, so the first 55 sections were voiced from stale text. Sequence: translate → post-edit → render.
  The engine choice belongs to that freeze too — changing the text after a render means voicing the book twice.
- Make synthesis **resumable**: skip a section whose mp3 already exists (`RENDER_FORCE=1` to override). Resuming over 47 finished sections took 1.7 min instead of ~12 min.
- **Silero raises `ValueError` in `process_simple_text` on fragments with no Cyrillic** (link lists, "Also by" catalogues, latin front matter). Guard with `re.search(r"[\u0400-\u04ff]", chunk)` and skip; wrap the call in try/except with a per-sentence retry so one chunk cannot kill a 40-minute run.
- Count sections by pattern (`^\d{3} — раздел \d+\.mp3$`); a substring match on «раздел» also catches the index file.
- Never rename or delete an output folder while a render writes into it: first verify the fresh copy (sections + combined + index), then delete the stale duplicate (one such duplicate was 938 MB).
- Verify at the end: format (44 100 Hz / 2 ch / 192 kbps), non-silent audio (peak ≫ 0), combined duration == sum of sections (±1 s), seek at a >2 h offset with `ffmpeg -ss 02:00:00 -t 30 -i out.mp3 -f null -`.
- **Prove the audio matches the CURRENT text, not a stale render.** Per section compute `chars(chunks_ru/NNN.md) / (duration_min × 60)`: RU Silero output lands near a median of 15 chars/s, so a section deviating by more than ~30 % is a candidate voiced from text that was edited afterwards. Sections under ~1 min (index/tail ones) always sit outside the band — that is the pause-to-speech ratio, not a defect.
- The artefact the user actually reads is `<Book> — RU.md` per book: it is byte-for-byte the ordered concatenation of `chunks_ru/`, and chunk number `NNN` corresponds to section `NNN — раздел N.mp3`. When he asks "where is the translation", name all three layers — the per-book `RU.md`, `chunks_ru/NNN.md` (the exact text that was voiced) and the section index with timecodes for reading along.

## Pitfalls
### Never concat section mp3s with `-c copy`
Independently encoded mp3s carry their own Xing header, so the concat demuxer emits non-monotonic DTS (`Application provided invalid, non monotonically increasing dts to muxer`). The file plays but seeking breaks. Re-encode: `ffmpeg -f concat -safe 0 -i list.txt -ar 44100 -ac 2 -b:a 192k out.mp3` (~110 s per 4.4 h).
`os.replace()` cannot cross drives on Windows (`WinError 17`) — `shutil.copyfile` + `os.remove`.

### Silence in the Hermes desktop inline player
edge-tts output is mono / 24 kHz / 48 kbps and the desktop app's in-chat player shows a moving slider but plays nothing, while VLC plays the same file fine. The file is not broken: check `ffmpeg -i f.mp3 -ac 1 -f s16le out.raw` then max/RMS (speech ≈ RMS 3000+ of 32768). Deliver 44.1 kHz stereo 192 kbps instead.

### Job hygiene
- Never keep venvs, downloads or source PDFs in `hermes\cache\scratch` — pruned after ~24 h idle and everything vanishes mid-project. Use a durable dir (`%LOCALAPPDATA%\hermes\audio-work`); rebuilding from the uv cache takes ~20 s.
- Keep `words_alpha.txt` in the work dir as the quality yardstick for any extraction claim.
- Terminal calls need interactive approval and die on a 2-min timeout when the user is away; `execute_code` runs local Python/subprocess without that prompt — use it for synthesis/ffmpeg jobs, splitting work under its 5-min cap.
