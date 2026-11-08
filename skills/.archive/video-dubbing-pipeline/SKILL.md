---
name: video-dubbing-pipeline
description: >
  Dub or localize a video locally through a full pipeline (ASR -> LLM translation ->
  TTS -> mux) and MEASURE it. VideoLingo 3.x on Windows is the reference
  implementation. Use when translating a video into another language offline, when
  wiring VideoLingo's process_video, when a night-batch run must be justified by numbers
  (stage timings, peak VRAM, duration drift, API cost), or when a single control file
  has to be validated before committing a whole queue to it.
---

# Local video dubbing pipeline (ASR -> translation -> TTS -> mux)

Class: taking a recorded video in language A and producing a watchable file with spoken
language B, locally, as a repeatable pipeline rather than a one-off.

Tooling seen on this machine: **VideoLingo 3.x** (upstream `Huanshere/VideoLingo`) with
WhisperX large-v3 for ASR, an OpenRouter (or local Ollama) LLM for translation, Edge-TTS
for synthesis, ffmpeg for assembly.

## The rule that governs everything: one control file before the batch

Never wire the night-batch queue until a SINGLE short file has produced an acceptable
result. A batch run with a broken config manufactures twenty identically broken files
overnight and burns the API budget doing it. Order is always:

1. Prove the GPU/venv works in isolation (`stt-whisper-gpu-windows` skill).
2. Run ONE file end-to-end, measure every stage.
3. The owner listens to it and judges voice/синхрон.
4. Only then touch the queue.

## Single-run recipe (VideoLingo)

Input goes in `VideoLingo/batch/input/` — the repo does NOT ship that directory, create it.
Non-ASCII file names are avoidable pain; keep them ASCII.

```bash
# config first (see references/videolingo-windows.md for the exact fields)
cd VideoLingo && .venv/Scripts/python.exe ../scripts/videolingo_single_run.py <file.mp4> \
  2>&1 | tee ../logs/runNNN.log
```

`scripts/videolingo_single_run.py` in this skill wraps `process_video(file, dubbing=True)`
with per-step timers and a background `nvidia-smi` sampler, and writes a machine-readable
summary. Do not hand-run the pipeline when this exists. If the task prescribes the inline
`python -c "from batch.utils.video_processor import process_video; ..."` form, it works too —
but a file-based script needs the `sys.path` fix below.

## Measuring — what a dubbing report must contain

| Quantity | How |
|---|---|
| Stage times (4 buckets) | wrap each step function, do NOT edit the vendor code |
| Peak VRAM | `nvidia-smi` sampler, **never** `torch.cuda.max_memory_allocated()` (reads 0 for CTranslate2) |
| GPU utilisation | same sampler — `util == 0` for a whole stage while it "succeeded" = CPU fallback or a swallowed error |
| ASR length | segment count + character count of the source SRT |
| Duration drift | `abs(dubbed - source) / source * 100`; state the tolerance you were given |
| API cost | see pitfall — VideoLingo does not log it by default |

**Stage mapping is not obvious — write down the mapping you used.** `process_video` runs
eleven steps; the acceptance table usually names four buckets. The step that no bucket
mentions (subtitle mux) has to be assigned somewhere explicitly, and the sum of the buckets
should reconcile to the wall clock (a small remainder for wrapper overhead is fine — say so).

**Timing wrapper, non-invasively.** Import the module, `setattr` a timing shim over each
step attribute *before* calling `process_video`, restore nothing (one-shot process). The
step names are resolved at call time from module globals, so patching module attributes is
enough — no vendor files touched.

## Verifying the OUTPUT, not the exit status

`ok=True` from `process_video` does not mean the product is good. Check the artifacts:

- `ffprobe` the final file: it must show both a video and an audio stream, and the container
  duration must be within tolerance of the source.
- Count SRT blocks and check EVERY block: zero empty translations, zero blocks still in the
  source language. A batch that failed JSON validation and got retried can leave holes that
  the pipeline reports as success.
- Compare the TTS track length against the video: a dub noticeably shorter than the video
  (a few percent) is normal — it gets stretched/padded at mux — but a large gap means
  truncated speech or dropped lines.

## Quality questions you must answer honestly

The acceptance template normally asks four questions (terminology / voice / sync /
watchable). Answer the two you can measure **with numbers**, and say plainly that the
audio-judgement part is the owner's:

- **Terminology / text** — you can read the subtitle file and quote lines comparing source
  and translation. Do that; machine-check for untranslated blocks.
- **Voice** — you have no hearing. Report the TTS engine and voice, note whether one voice
  was used for multi-speaker source (a real quality risk), and hand the verdict to the
  owner. Do not invent a plausible-sounding assessment.
- **Sync** — quantify with duration drift and subtitle time codes; subjective drift in the
  middle cannot be verified without listening.
- **Verdict** — only sign off "watchable" for what you verified.

## Cross-check the pipeline's OWN terminology table — the strongest quality evidence

The pipeline extracts a terminology table during translation (`log/terminology.json`:
`{"theme": ..., "terms": [{"src","tgt","note"}]}`) and then **does not have to obey it**.
So the table is not a spec — it is a list of exactly which words to inspect. Method:

1. Load `log/terminology.json`, take every `src` term.
2. Find each term's segment index in the source SRT, then read the SAME index in the final
   SRT — match by block number, **not** by grepping the translation for the guessed Russian
   word (a grep for the table's `tgt` misses re-worded lines and produces false "missing").
3. Tabulate: term | table target | final line | matches or not.

Real result (94-segment dialogue, `deepseek/deepseek-v4-flash`): only **3 of 9** terms landed
verbatim. Most divergences were *improvements* (colloquial register: "образовательный
инструмент" → "Учебное пособие"). Two mattered:
- "consequences" → "наказание" — meaning preserved and sharpened for the scene, but the
  table's term is unused.
- "Good doggy" → "Умница / Молодец" — the table's own `note` calls it a *humiliating*
  address; the neutral praise in the output **loses the register**, which is the one finding
  worth reporting as a real quality defect.

**Why the table drifts, and why that is structural not a bug:** translation runs two passes —
a faithfulness prompt and an expressiveness prompt (`gpt_log/translate_faithfulness.json`,
`gpt_log/translate_expressiveness.json`). The second deliberately rewrites wording for
naturalness, so no extracted term is binding. Say this in the report instead of calling the
divergence an error.

Bonus: `gpt_log/summary.json` carries the pipeline's own content summary
(`### Content Summary`) — use it to state what the material actually is (a lecture vs a
drama scene with adult themes changes what "correct terminology" even means).

## Sizing a night batch (measured, RTX 3050 8 GB, 9.0-min dialogue)

| Quantity | Ratio |
|---|---|
| Translation step alone | ≈ **30 % of video length** (3.3× faster than realtime) |
| Full pipeline | ≈ **120 % of video length** (1.2× longer than the video) |
| Per minute of video | translation 18 s · whole pipeline 72 s |
| ⇒ 8 h overnight | ≈ **6.6 h of video** |

Caveats to state with these numbers: translation is **LLM-bound, scaling with chunk/segment
count, not with minutes** (fast dialogue → more chunks); `max_workers` (4 here) parallelises
the LLM calls and raising it can roughly halve stage 2; and one file is one sample — re-measure
on the batch. Stage shares were flat (ASR 16 %, translation 28 %, synthesis 29 %, assembly 27 %).

## Measuring API cost — use a metered key, read the balance from the provider API

VideoLingo logs no token/cost data, so the only honest measurement is the provider's own
balance, taken before and after a run. Recipe (works for OpenRouter; any metered provider
has an equivalent endpoint):

1. Ask the owner for a **separate key with a hard limit** (here: $5). A shared key makes
   `balance_before - balance_after` meaningless, and the limit doubles as a runaway guard.
2. Read the key **out of the config file inside the script** — never as a CLI argument
   (lands in shell history/process list), never echoed. Print only `label`, `limit`,
   `usage`, `limit_remaining`. Ready-to-run: `scripts/openrouter_balance.py`.
   ```
   GET https://openrouter.ai/api/v1/auth/key   (Authorization: Bearer <key>)
   -> {"data": {"limit": 5, "usage": 0.005078872, "limit_remaining": 4.994921128, ...}}
   ```
3. Take a baseline BEFORE the run, and again after. Cost = difference, rounded to cents.
4. **A failed run still costs money** if it got past translation — the translation was paid
   for. Report the spend and say which stage burned it.

Measured reference (4.77-min dialogue, `deepseek/deepseek-v4-flash`, `max_workers=4`):
$0.0051 for the run ⇒ ≈ **$0.00107 per video-minute** ⇒ ≈ **$0.064 per hour of video**.
Translation dominates the spend; synthesis (Edge-TTS) and ASR are free.

**Verify a key was really saved without printing it.** Owners say "ключ я вставил" while the
file is untouched. Check the value's *shape*, not its content:

```python
v = line.partition("key:")[2].strip()          # length + placeholder test, never the value
print(len(v), v.strip("'\"") in ("YOUR_API_KEY", "your_api_key", ""))
```

Also compare the file's `mtime` against the clone/checkout time — a mtime unchanged since
`git clone` is proof the file was never written, whatever the owner remembers. Report
"key saved / still placeholder" and nothing else.

## A/B/C comparison runs — isolate what you are comparing

When the task varies one axis (e.g. A = API model X, B = local Ollama, C = API model Y) and
holds the rest fixed:

- **Every variant that shares a downstream layer inherits that layer's failures.** Here all
  three share ASR + Edge-TTS + mux, so a synthesis-side defect threatens B and C too — even
  though the task only asked you to compare translation. Say this out loud when variant A
  fails; do not silently continue.
- **Each run costs real money and 8+ minutes.** When A fails for a reason that is not the
  axis under test, stop and ask before re-running or continuing. Burning a limited budget to
  discover the same defect three times is the failure mode.
- Keep CSV/config switching minimal and record it: what changed, what deliberately did not.
- Never "fix" the failure by tweaking the vendor's prompts — capture it as a result.

## Preserve a failed run before the next one overwrites it

`process_video` wipes `output/` at the start (`prepare_output_folder`) and, on failure, moves
its remains to `batch/output/ERROR/<name>/`. Before relaunching anything, copy that directory
out under an explicit name:

```
cp -r batch/output/ERROR/<name> batch/output/<name>-A-FAILED
```

A failed run is still evidence: ASR + translation survive (`src.srt`, `trans.srt`,
`output_sub.mp4`) even when synthesis dies, and `audio/tts_tasks.xlsx` is where the defect
shows up numerically. Report which artifacts survived vs which were never produced.

## Resuming a run that died late (measured recipe)

When the failure is in synthesis and stages 1–2 are intact, a `--resume` mode can redo only
the cheap part. Give the wrapper a flag that does three things:

1. **Replay the preserved run back into the working dir** — if `output/` is empty, copy
   `<name>-A-FAILED/` into `output/` (in the wrapper: `shutil.copytree(failed, out,
   dirs_exist_ok=True)`); the failed dir path must be given relative to the pipeline cwd
   (`batch/output/<name>-A-FAILED`), not to the project root.
2. **Pass the pipeline's own retry flag** to `process_video(..., is_retry=True)` so it does
   not wipe `output/` at startup (`prepare_output_folder` is what destroys the reuse).
3. **Clear the scratch dirs that carry the poisoned artifacts** — both `output/audio/tmp/`
   (raw TTS) and `output/audio/segs/` (post-processed). Clearing only the 0-byte files is not
   enough: a stage retry regenerates from these dirs, so the empty file survives and the same
   failure repeats identically. List every target with its byte size before deleting.

**Reuse really does happen — verify it by measurement, not by reading the source.** An
obvious `if exists: return` guard is NOT visible in `_2_asr`/`_4_2_translate`, which is
tempting to read as "resume re-runs everything and re-pays". It reuses anyway. Evidence from
a real resume: ASR **0.00 s**, translation **0.54 s**, total 92 s instead of 476 s, and the
metered balance **unchanged to the cent ($0)**. Rule: before telling anyone a resume will or
won't re-pay, measure stage seconds and the balance delta — do not infer from the code, and
do not leave a wrong claim in the report.

**Transient vs deterministic is answered by the repeat.** Same file, same config, same
`max_workers` → first run 48 × `NoAudioReceived`, resume run **0**. That confirms a
service-side storm rather than an input-dependent defect, and it is the evidence that decides
"don't touch concurrency" vs "lower it". Compare the two counts explicitly in the report.

**Carry the counts into the metrics.** Pass the wrapper its own log path
(`--log=../logs/runNNN.log`) so it can count `NoAudioReceived` from the file after the run,
and have it compute `tts_empty_segments` by scanning `output/audio/segs/` for 0-byte files.
Those two numbers, printed in the run summary, are what make "the storm passed" a measurement
instead of an impression.

### Guard patch for the zero-byte-TTS class (three edits, all in vendor code)

Apply only when the TASK authorises editing the cloned pipeline — otherwise report and stop.
The three edits cover three different stages; one alone is not enough:

1. **Synthesis, fail fast** (`_10_gen_audio.merge_chunks`, right after
   `ad_dur = get_audio_duration(output_file)`): `if ad_dur <= 0: raise Exception(f"TTS
   produced no audio for line {number}_{line_index}: file=..., text={line!r}")`. The raise
   lands in the pipeline's own per-step retry loop, which regenerates TTS — and a transient
   storm is exactly what a retry fixes.
2. **Merge, guard on size** (`_11_merge_audio`): replace `os.path.exists(audio_file)` with an
   `exists() and getsize() > 0` helper, increment a module-level `skipped_empty_segments`
   counter, and print it after the merge — plus an explicit "the dub is INCOMPLETE" line when
   the counter is non-zero. Never let a run finish silently having dropped lines.
3. **End of synthesis, report the count** (`_10_gen_audio.gen_audio`): scan `segs/` for
   0-byte files and print `TTS empty segments: N` (also count `real_dur == 0` rows). Carry it
   into the metrics JSON.

Keep the edits local (the clone is gitignored) and list changed files + the 3–5 changed lines
in the report. Do not touch translation, Whisper or the prompts.

## Testing whether a LOCAL LLM can stand in for the API

Don't judge "can Ollama do it" by reading a reply — test the **contract the pipeline
enforces**: the faithful-translate step needs JSON with keys `"1".."n"`, each carrying a
`direct` sub-key, and it retries 3× then raises.

- Build the prompt with the vendor's OWN builders, not a re-typed copy:
  `core/prompts.py: generate_shared_prompt(None, None, None, None)` + `get_prompt_faithfulness(lines, shared)`.
- Send it to the OpenAI-compatible endpoint (`http://127.0.0.1:11434/v1/chat/completions`),
  parse the answer (fenced ```json or raw), validate against the same rule the code uses,
  and print model, response time, `JSON valid: True/False`, and the answer verbatim.
- `ollama list` / `GET /api/tags` first — a dead Ollama returns connection errors that look
  like a model failure. Reference probe: `references/ab-comparison-and-failure-forensics.md`.
- A model that fails the contract is a **result**, not a bug to prompt-engineer away.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'batch'` | running `python ../scripts/x.py` sets `sys.path[0]` to the SCRIPT's dir, not cwd; the pipeline imports `batch.*`/`core.*` relative to cwd | `sys.path.insert(0, str(Path.cwd()))` at the top of `main()`. The inline `python -c` form is immune (its `sys.path[0]` is cwd) |
| First split step takes ~20 s and logs a download warning | spaCy model (`en_core_web_md` etc.) missing from a fresh venv | expected — it self-downloads; do not treat as a failure |
| `Project model cache is incomplete; falling back to the global HuggingFace cache` | `model_dir` (e.g. `_model_cache`) is empty | expected on first run; the model lives in the user's HF cache, not next to the project — matters for batch disk planning |
| Pipeline ends `ok=True` but a translation batch failed | LLM returned JSON missing keys; client wrote `error.json` and retried | count `retry:` lines in the log, verify every SRT block by hand/programmatically, report the retry count |
| One synthesized voice for a dialogue | Edge-TTS uses a single `voice:` | flag as a quality risk; multi-voice needs a different TTS backend — a separate task |
| Peak VRAM near the card's total | 8 GB card, large-v3, desktop already holding ~2 GB | put a measured number in the report and raise the mode question (medium model vs "GPU must be idle during batch") |
| API cost unmeasurable | `log/` and `gpt_log/` are **directories**, and a `0` next to them in a Windows `ls -l` listing is the directory-entry size, not the content. They actually hold `terminology.json`, `split_by_*.txt`, the intermediate `translation_results*.xlsx`, `summary.json` and the two translation-pass prompt dumps — but **no token or cost data** | record "не снято", not "0"; raise it as a prerequisite for any local-LLM-vs-API comparison task. **Do not repeat the "`log`/`gpt_log` are 0 bytes" claim — it is false**, and it hides the fact that these dirs are your best evidence source. Cost is now measurable — see "Measuring API cost" above |
| **Synthesis dies: `FileNotFoundError: .../segs/N_0.wav_temp.mp3`** (step fails after 3 retries) | TTS returned **nothing** for one line. Chain: Edge-TTS `NoAudioReceived` → 0-byte `audio/tmp/N_0_temp.wav` → ffmpeg writes nothing → `get_audio_duration()` hits its `except` branch, prints `Failed to get audio duration: list index out of range`, and **returns 0** → `new_sub_times.append([t, t+0])` = a **zero-length slot** → `_11_merge_audio.process_audio_segment` runs ffmpeg on a 0-byte `.wav` and `AudioSegment.from_mp3` raises. The only guard is `os.path.exists()`, which a 0-byte file passes | Diagnose by **size**, not presence: `ls -l segs tmp` and look for `0`-byte entries; confirm the slot in `audio/tts_tasks.xlsx` (`new_sub_times` showing `[t, t]`). **Compare occurrence counts against a run that worked** (`grep -ac "Failed to get audio duration"` — 0 before, 2 after) to prove the defect is new and not always-on. Then STOP: this is a vendor-code defect (needs a size guard + a retry on `NoAudioReceived`), not a parameter to guess at. Re-running MAY pass — the cause is transient/service-side — but that spends money, so ask first |
| `NoAudioReceived` appears several times but the run "succeeded" | Edge TTS rate-limits / intermittently returns no audio; failed lines leave 0-byte files that downstream steps tolerate *until* the merge | reduce TTS concurrency (`max_workers` also drives it) or add a retry — as a separate, authorised change to vendor code |
| A stage's helper swallows an error and returns a sentinel | e.g. `get_audio_duration` returns `0` in `except` | a sentinel `0` then flows on as a legitimate measurement (a zero-length timeline slot). Treat any "0 on error" helper as a defect site; validate the value, don't just catch |

## References

- `references/videolingo-windows.md` — config field list, output layout, measured numbers
  from a real RTX 3050 8 GB run, and the quality sample.
- `scripts/videolingo_single_run.py` — timing + GPU wrapper around `process_video`.
  Takes an optional 2nd positional for the metrics output path (successive A/B/C runs must
  not overwrite one summary file), plus `--resume`, `--failed-dir=` and `--log=` — the last
  one lets the wrapper count `NoAudioReceived` in the log it is already teeing into, and it
  always reports `tts_empty_segments` from `output/audio/segs/`.
- `scripts/openrouter_balance.py` — read a metered OpenRouter key's `limit`/`usage`/
  `limit_remaining` from `config.yaml` without ever printing the key.
- `references/ab-comparison-and-failure-forensics.md` — the A/B/C comparison design, the
  Ollama JSON-contract probe, and a worked post-mortem of the zero-byte-TTS failure
  (exact log strings, line numbers, file evidence).
- `mlops/stt-whisper-gpu-windows` — the GPU/cuBLAS/VRAM layer this builds on.
- `software-development/coder-terminal-workflow` — REPORT discipline for the
  architect-reviewer workflow these tasks run under.