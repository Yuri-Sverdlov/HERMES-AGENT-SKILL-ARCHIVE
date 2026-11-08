# A/B/C comparison runs and failure forensics (VideoLingo, RTX 3050 8 GB)

Session detail behind the "A/B/C comparison runs", "Measuring API cost" and zero-byte-TTS
pitfall sections of the parent skill. Project: VIDEO-TRANSLATE-BATCH, TASK 003, 2026-09-13.

## Comparison design actually used

One trimmed file (`3364-r.mp4`, 286.49 s = 4.77 min, h264 854x480, aac 48 kHz stereo) run
three times. Only the translation axis varies:

| Variant | Translation | TTS |
|---|---|---|
| A | OpenRouter `deepseek/deepseek-v4-flash` | Edge-TTS `ru-RU-DmitryNeural` |
| B | local Ollama `gemma3:4b` (fallback `llama3.2:3b`), `max_workers: 1` | same |
| C | OpenRouter `deepseek/deepseek-v4.1-flash` | same |

Deliberately held fixed: `whisper.model=large-v3`, `whisper.language=en`,
`whisper.runtime=local`, `demucs=false`, `burn_subtitles=true` (needed for the
`output_sub.mp4` artifact), `max_workers=4` for the API variants.

Config fields that had to be changed for the experiment:
`target_language` → `Russian`, `tts_method` → `edge_tts`, `edge_tts.voice` →
`ru-RU-DmitryNeural`; for B `api.base_url` → `http://127.0.0.1:11434/v1`, `api.key` →
`ollama`, `api.model` → `gemma3:4b`, `max_workers` → 1 (with a note to restore before C).

## Balance API (OpenRouter)

```
GET https://openrouter.ai/api/v1/auth/key
Authorization: Bearer <key>
-> {"data": {"label": "sk-or-v1-...", "is_free_tier": false, "limit": 5,
             "usage": 0.005078872, "limit_remaining": 4.994921128, "rate_limit": {...}}}
```

Baseline before A: `usage 0`, `limit_remaining 5`. After A: `usage 0.005078872`,
`remaining 4.994921128` ⇒ **$0.0051** for a 4.77-min dialogue despite the run FAILING at the
merge step (translation is paid the moment it returns; only synthesis died).

⇒ ≈ $0.00107 per video-minute ≈ $0.064 per hour of video. One sample, dialogue-dense,
`max_workers=4` — re-measure on the batch.

`label` returns the key's masked prefix; it is not a secret, but keep it out of reports anyway.

## Post-mortem: zero-byte TTS killed variant A

Command and outcome:

```
.venv/Scripts/python.exe ../scripts/run_single_dub.py 3364-r.mp4 ../logs/run003-A-metrics.json \
  2>&1 | tee ../logs/run003-A.log

RESULT ok=False failed_step='🔄 Merging full audio'
       error="[Errno 2] No such file or directory: 'output/audio/segs/15_0.wav_temp.mp3'"
```

Wall clock 476.29 s. Steps that completed: input 0.08 · WhisperX 44.77 · split 4.14 ·
translate 220.91 · align 0.19 · subtitle mux 18.43 · audio tasks 0.78 · refer audio 28.04 ·
gen audio 110.82 · then "Merging full audio" tried 3× (1.70 / 1.56 / 1.56 s) and failed.
Peak VRAM 6453 MB (baseline 1549 MB).

### Evidence chain

1. Edge-TTS returned nothing for several lines:

```
edge_tts.exceptions.NoAudioReceived: No audio was received. Please verify that your parameters are correct.
'output\\audio\\tmp\\15_0_temp.wav']' returned non-zero exit status 1
```

   On disk: `audio/tmp/15_0_temp.wav` — **0 bytes**.

2. `core/_10_gen_audio.py:178-179` — `adjust_audio_speed(temp_file, output_file, factor)`
   then `ad_dur = get_audio_duration(output_file)`. On empty input ffmpeg produces nothing,
   `get_audio_duration` finds no `Duration:` line, prints
   `❌ Error: Failed to get audio duration: list index out of range`
   (`core/asr_backend/audio_preprocess.py:82-88`) and **returns 0**.

3. Line 180: `new_sub_times.append([cur_time, cur_time+ad_dur])` ⇒ `[26.922, 26.922]`.
   Confirmed in `audio/tts_tasks.xlsx`, segment 15:
   `new_sub_times = [[26.922, 26.922], [26.922, 29.152]]`, `real_dur` 2.23 s vs slot 2.895 s.
   The line that lost its slot: RU "Ну серьёзно." for EN "Come on.".

4. `core/_11_merge_audio.py::process_audio_segment` → ffmpeg on `segs/15_0.wav` (0 bytes) →
   no `15_0.wav_temp.mp3` → `AudioSegment.from_mp3(temp_file)` raises `FileNotFoundError`.
   `merge_audio_segments` guards only `if not os.path.exists(audio_file): continue` — a
   zero-byte file passes the guard.

File evidence: `segs/15_0.wav` 0 bytes, `tmp/15_0_temp.wav` 0 bytes, the other 63 files in
`segs/` normal (13–165 KB).

### Class-check against the previous successful run

| Probe | Full 9-min run (OK) | Trimmed 4.77-min run A (FAILED) |
|---|---|---|
| `grep -ac "Failed to get audio duration"` | 0 | 2 |
| speed factors > `speed_factor.accept` (1.2) | 13 | 11 |
| max speed factor | 2.239 | 2.142 |

⇒ The zero-duration error is **new**; over-speed chunks are NOT the discriminator (present in
both). Without this comparison the honest verdict would have been "speed factor blew past
max" — a wrong root cause.

## Failed-run artifacts (preserved before relaunch)

`batch/output/ERROR/3364-r/` → copied to `batch/output/3364-r-A-FAILED/` (97 MB).
Survived: `3364-r.mp4`, `src.srt`, `trans.srt`, `src_trans.srt`, `trans_src.srt`,
`output_sub.mp4`, `dub.srt`, `gpt_log/` (summary + both translation-pass prompts +
`tts_correct_text.json`), `log/`, `audio/` (incl. `segs/`, `tmp/`, `tts_tasks.xlsx`).
Never produced: `output_dub.mp4`, `dub.mp3`, `normalized_dub.wav`.

## Ollama JSON-contract probe

`scripts/ollama_json_probe.py` (project copy) does, in order:

1. `GET http://127.0.0.1:11434/api/tags` — prove Ollama is alive before blaming the model.
2. Take N consecutive lines from the A-run `src.srt`.
3. `sys.path.insert(0, str(Path.cwd()))` then
   `from core.prompts import generate_shared_prompt, get_prompt_faithfulness`;
   `shared = generate_shared_prompt(None, None, None, None)` — minimal but genuinely the
   vendor's builder, so the prompt is the one the pipeline will really send.
4. POST to `/v1/chat/completions` (`stream: false`), time it, print `usage`.
5. Parse (fenced ```json or raw) and validate with the pipeline's own rule: dict, keys
   `"1".."n"`, each an object with a `direct` sub-key.
6. Write the raw answer to `logs/ollama_probe_answer.txt` (UTF-8) and print an
   ASCII-replaced copy — the answer is Cyrillic, and console printing must stay ASCII.

Deciding rule from the task: valid JSON ⇒ run B; invalid ⇒ retry once with the fallback
model; still invalid ⇒ record "B does not pass structured output" and **do not run B**.
A rejected local model is a deliverable, not something to prompt-engineer around.

## Why A's failure stopped the whole task

All three variants share ASR + Edge-TTS + mux; only the LLM differs. A synthesis-layer defect
therefore endangers B and C identically, while each attempt costs ~$0.005 and ~8 minutes of a
$5 budget. Correct move: stop, report the chain with evidence, and ask
(1) re-run A, (2) how to score a variant whose mux failed, (3) whether to add the size guard +
`NoAudioReceived` retry to the vendor code. All three are the architect's call, not the
coder's.
