---
name: stt-whisper-gpu-windows
description: Deploy and debug local GPU speech-to-text on Windows (whisper-local app, drajb/whisper-local, faster-whisper, CTranslate2). Covers the two CUDA traps that silently break transcription — missing cuBLAS DLL co-location and a stale CUDA runtime shadowing the driver from PATH — plus the reliable "direct engine test" that bypasses a GUI which closes too fast to show a traceback. Use when setting up whisper/faster-whisper/CTranslate2 on GPU, when transcription hangs on "transcribing…", when the installer reports "found CUDA <old> / requires 12", or when a Windows tray STT app starts but never produces text.
---

# Local GPU speech-to-text (whisper / faster-whisper / CTranslate2) on Windows

Class: deploying a local STT app that uses faster-whisper over CTranslate2 on an
NVIDIA GPU, on a Windows host, and debugging why it silently produces no text.

## Architecture facts that drive everything
- whisper-local's launcher bundles its own Python (`%LOCALAPPDATA%\Python\pythoncore-<ver>-64`).
  Its `site-packages` hold faster-whisper + ctranslate2 + the app (whisper_key). All
  CUDA DLL surgery happens inside that venv's `site-packages\ctranslate2\`.
- **CTranslate2 loads its CUDA DLLs ONLY from its own package dir** (`ctranslate2\dll`s),
  not from SYSTEM32/PATH. So the cure is co-location, not path editing.
- Driver gives the CUDA runtime; a CUDA Toolkit installation is NOT needed (and installing
  one is a trap — it pollutes PATH).

## Trap 1 — missing cuBLAS = silent "transcribing…" hang (THE main gotcha)
- The build ships `cudnn64_9.dll` inside `ctranslate2\` but NOT `cublas64_12.dll`.
  Without cuBLAS the app reaches the transcribe step and hangs forever; the
  `cublas64_12.dll is not found` message is swallowed and invisible in the UI.
- Fix (do once per venv):
  ```
  <venv-python> -m pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12
  # copy into the ctranslate2 package dir, next to cudnn64_9.dll:
  cp site-packages/nvidia/cublas/bin/cublas64_12.dll    site-packages/ctranslate2/
  cp site-packages/nvidia/cublas/bin/cublasLt64_12.dll  site-packages/ctranslate2/
  cp site-packages/nvidia/cuda_runtime/bin/cudart64_12.dll site-packages/ctranslate2/
  ```
  Resulting dir should contain: cublas64_12, cublasLt64_12, cudart64_12, cudnn64_9,
  ctranslate2.dll. Verify with `find .../ctranslate2 -iname '*.dll'`.

## Counter-case — Trap 1 does NOT always bite: import order can save it
- Real case (VIDEO-TRANSLATE-BATCH, 2026-09-12): fresh VideoLingo venv, torch 2.8.0+cu129,
  whisperx 3.8.6. `ctranslate2\` held `cudnn64_9.dll` but NO `cublas64_12.dll` — exactly
  the Trap 1 layout — yet large-v3/cuda/float16 transcribed fine on the first run.
- Reason (hypothesis, not proven): the test script did `import torch` BEFORE `faster_whisper`.
  torch registers its own `torch\lib` in the Windows DLL search path, and the cu12x wheels
  ship `cublas64_12.dll` + `cublasLt64_12.dll` there. The loader finds cuBLAS from torch\lib
  even though `ctranslate2\` has no copy.
- Practical rule: **import order masks Trap 1.** A standalone probe that imports torch first
  is NOT proof that the app's own code path is safe. Check whether the target app imports
  torch before loading the model; if it doesn't, co-locate the DLLs anyway.
- **Battle-path confirmation (2026-09-12):** the same venv then ran VideoLingo's full
  `process_video` pipeline — eleven steps, ~11 min, WhisperX on `cuda`/`float16`, batch
  size 2 — with no cuBLAS co-location and no OOM, peak 7134 MiB of 8192 (baseline 2212 MiB
  held by the desktop). So for this stack the hypothesis holds on the real path, not just
  in a purpose-built probe. Keep the DLL copy as insurance for entry points that reach
  CTranslate2 without torch (see `media/video-dubbing-pipeline` for the pipeline itself).
- Source for the copy needing no extra pip install:
  `<venv>\Lib\site-packages\torch\lib\{cublas64_12.dll,cublasLt64_12.dll}` -> `ctranslate2\`.

## Measuring VRAM for CTranslate2 — torch's counter reads 0
- `torch.cuda.max_memory_allocated()` returns **0 MB** for a faster-whisper/CTranslate2 run:
  CTranslate2 allocates on the GPU outside PyTorch's caching allocator. Not a failed
  measurement — the counter simply cannot see those buffers. Don't report "peak VRAM 0".
- Measure with nvidia-smi: poll `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits`
  every ~0.25 s from a daemon thread during load+transcribe, keep the max, and report peak
  AND baseline (a desktop/browser can hold ~2 GB). Real numbers on RTX 3050 8 GB:
  baseline 2054 MB -> peak 6259 MB for large-v3/float16 (+4205 MB); 16 s audio transcribed
  in 2.0 s (~7.8x realtime).

## Running diagnostic .ps1 through a pipe on this PC — Cyrillic collapses to '?'
- `pwsh -NoProfile -File .\scripts\x.ps1 2>&1 | tee log` produced a log of `?` where Russian
  should be (cp1252 cannot encode Cyrillic). `-NoProfile` skips the profile's UTF-8 setup
  (DEV-NOTES п.12 fixes this only for shells that load the profile), so set it explicitly:
  ```
  pwsh -NoProfile -Command '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8; & "./scripts/x.ps1"' 2>&1 | tee log
  ```
- Corollary: once OutputEncoding is forced to UTF-8, a script that pipes a native tool
  (`powercfg`, etc.) into `Select-String` on a **localized** pattern silently matches
  nothing — native tools emit the OEM codepage. Parse by `0x`/index, not by localized text.
- git-bash/MSYS mangles leading-slash args (`powercfg /query` becomes a path -> "invalid
  parameters"). Run native tools via `pwsh -Command`, never bare in bash (DEV-NOTES п.14.2).
- **Before doing the surgery — check the import order and torch's own DLL dir.** cuBLAS
  does not *have* to be co-located: `import torch` registers `site-packages/torch/lib`
  in the Windows DLL search path for the current process, and the CUDA torch wheels ship
  `cublas64_12.dll` / `cublasLt64_12.dll` there. So a venv where **torch is imported
  before faster_whisper** transcribes fine even with a `ctranslate2\` that has no cuBLAS.
  Verified 2026-09-12 in a VideoLingo venv (torch 2.8.0+cu129): `ctranslate2\` held only
  `cudnn64_9.dll`, yet large-v3/cuda/float16 transcribed in 2.04 s — because the probe
  script does `import torch` before `from faster_whisper import WhisperModel`.
  Two consequences:
  - **Order is load-bearing.** Any entry point that reaches CTranslate2 without importing
    torch first loses that search path and can still hang. Don't call Trap 1 "fixed"
    because your standalone probe passed — check the app's real import order, or co-locate
    the DLLs as insurance.
  - **Changing the order is a cheaper experiment than copying DLLs.** Before surgery,
    try `import torch` ahead of the faster_whisper import and re-run. Only copy DLLs when
    the venv has no CUDA torch at all.
  Session detail (dir listing, numbers, what is proven vs hypothesis):
  `references/vram-and-cublas-resolution.md`.

## Trap 2 — "found CUDA 6.5" / driver vs stale cudart in PATH
- Symptom: installer says "found CUDA <6.x> / requires 12" even though `nvidia-smi`
  shows a modern driver (CUDA 13.x). An old `cudart*.dll` earlier in PATH shadows the
  driver. Common culprit: `C:\Program Files (x86)\NVIDIA Corporation\PhysX\Common\cudart64_65.dll`
  (and 32-bit twin). Present in BOTH User and Machine PATH.
- Check both scopes, don't just echo `$PATH` (git-bash PATH is merged/translated; use
  registry scopes):
  ```powershell
  [Environment]::GetEnvironmentVariable('Path','User')
  [Environment]::GetEnvironmentVariable('Path','Machine')
  ```
- User-scope PATH is editable from a normal shell:
  ```powershell
  $p=[Environment]::GetEnvironmentVariable('Path','User')
  $items=$p -split ';' | Where-Object { $_ -notmatch 'PhysX\\Common' }
  [Environment]::SetEnvironmentVariable('Path',($items -join ';'),'User')
  ```
- **Machine-scope PATH needs elevation (UAC)**: `SetEnvironmentVariable(...,'Machine')`
  throws "Requested registry access is not allowed." Don't fight it from a non-admin
  agent — co-locating CUDA-12 DLLs in `ctranslate2\` makes the stale 6.5 irrelevant
  (Trap 1), so the Machine PATH can be left alone. Note it for the owner to clean up
  manually with admin rights. Removed PATH takes effect in NEW processes, not the
  current one — restart the app after editing.

## Trap 3 — GUI hangs on CUDA inference even when the direct engine test passes
- **Symptom (real, STT-WHISPER-LOCAL 2026-09-08):** direct engine run of large-v3/cuda/
  float16 transcribes a 2.6 s clip in ~0.15 s (healthy), but the whisper-local GUI tray
  app, on the SAME config, records the clip then hangs forever: `app.log` ends at
  `faster_whisper - INFO - Processing audio with duration 00:02.576` with no
  "Transcription complete". `nvidia-smi` shows VRAM held (e.g. 5270/8192 MiB) but
  **GPU-util 0%** — the CUDA context is allocated but the inference never runs. After
  the hang the hotkey dies (next Ctrl+Space gives no beep at all). This is a
  GUI-wrapper CUDA-context stall, NOT the cuBLAS trap — the DLLs are present and the
  engine works. Do NOT keep diagnosing this one; the pragmatic fix is below.
- **Pragmatic fix (architect-mandated "working whisper any price"):** fall back the app
  to the stable CPU baseline that worked before — `model: base, device: cpu,
  compute_type: int8` in BOTH `user_settings.yaml` and the active profile in
  `profiles.yaml`. GPU tuning goes to a separate backlog task, not held hostage here.
- **Restart hygiene after a hang:** the hung process still holds VRAM. `Stop-Process`
  it, verify VRAM released (`nvidia-smi --query-gpu=memory.used`), then relaunch. A
  relaunched app that stays alive but writes NOTHING new to `app.log` and has CPU~0
  is stuck at startup (possibly waiting on an onboarding dialog or a stale pid file) —
  treat that as a fresh blocker, not "starting up".
- **Model fallback data point:** `medium`/cuda/float16 TIMED OUT (150 s) on the same
  machine where large-v3 worked in 12 s. Don't assume a smaller model is a safer GPU
  fallback — verify each candidate by direct engine run before switching config to it.

## Measuring VRAM: `torch.cuda.max_memory_allocated()` returns 0 for CTranslate2
- faster-whisper's inference runs in CTranslate2, which allocates GPU memory on its own,
  **outside the PyTorch caching allocator**. So after a full large-v3 run
  `torch.cuda.max_memory_allocated()` legitimately reports **0 MB** — that is not a broken
  probe and not "no GPU use". Verified 2026-09-12 (VideoLingo venv, torch 2.8.0+cu129):
  torch counter 0 MB, `nvidia-smi` peak 6259 MB.
- **Measure VRAM with a background `nvidia-smi` sampler, not the torch API.** Poll
  `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits` every ~0.25 s from a
  thread (or a shell loop) around load+transcribe and keep the max. Report **both** the
  absolute peak and the delta over the pre-run baseline — on a desktop GPU the baseline is
  not zero (2054 MB idle here: browser/desktop), so the raw peak overstates the model.
- Working sampler + numbers: `scripts/gpu_probe.py` (nvidia-smi thread) and
  `references/vram-and-cublas-resolution.md`.
- **A silent WAV is a bad probe input.** This skill's original `scripts/gpu_probe.py`
  transcribes 2 s of digital silence; Whisper can "successfully" return fluent text for
  silence, so a green `RESULT_OK text_len=N` proves nothing about the audio chain
  (DEV-NOTES §18). For a real proof, feed 10–20 s of actual speech and **print the text
  for eyeballing**. Cheap source when you have no sample clip: pull a segment out of a
  repo's own demo video —
  `ffmpeg -ss <start> -t 16 -i docs/public/videos/demo.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le probe.wav`.

## Diagnose by direct engine test, not the GUI (DEV-NOTES §16: verify by running)
- A tray STT GUI can open/close in ~2-3 s and swallow the Python traceback, so "app ran"
  proves nothing. Drive faster_whisper directly with the venv python on a synthetic
  silent WAV (16 kHz, mono, 2 s) and print timings:
  ```python
  from faster_whisper import WhisperModel
  m = WhisperModel("large-v3", device="cuda", compute_type="float16")
  segs, info = m.transcribe(silence.wav, language="ru", beam_size=5)
  ```
  Healthy output: `MODEL_LOADED init≈8 s`, transcribe on silence ≈1 s, lang=ru. A hang
  - A hang here = missing cuBLAS (Trap 1). A fast clean pass = GPU stack is fine; then do a GUI
    smoke test and read `app.log` for hotkeys/model/device registrations.
  - Ready-to-run version: `scripts/gpu_probe.py` in this skill — run with `-u`:
    `<venv-python> -u gpu_probe.py [model] [device] [compute_type] [wav]`.
    It imports **torch first when the venv has it** (registers `torch/lib` in the DLL
    search path, so cuBLAS resolves without co-location), falls back cleanly when torch is
    absent (whisper-local), samples nvidia-smi in a daemon thread for peak VRAM, and prints
    the transcript for eyeballing. Pass a 10–20 s real-speech wav as the 4th argument —
    with no argument it still synthesizes silence and now warns that this proves nothing.
  - The sampler's stop flag is named `_halt`, deliberately: `threading.Thread` has an
    internal `_stop()` method, and shadowing it with an `Event` makes `Thread.join()` raise
    `TypeError: 'Event' object is not callable`. Copy that naming if you write your own
    sampler — the failure surfaces *after* a successful run, which makes it look like the
    GPU test broke when it did not.

## Background-process debugging pitfall: python stdout is block-buffered
- When you launch a Python model-load/download as a `terminal(background=true)` job with
  `2>&1`, stdout is a pipe → **block-buffered**: `print()` sits until the process exits,
  so long inits look hung (no output, low CPU). Don't assume a hang — add `-u`
  (unbuffered) or `PYTHONUNBUFFERED=1`, and/or flush in-print, before judging. Also do the
  timing with a small foreground `sleep`/`poll` loop rather than one giant blocking wait,
  so a `wait` timeout can't be confused with a process death. A background process killed
  by a long foreground command timing out is not a model failure — distinguish
  "process killed" from "process crashed".

## Config gotchas (whisper-local `%APPDATA%\whisperkey\`)
- Per-machine config, NOT in the repo: `user_settings.yaml` + `profiles.yaml`. The active
  profile (`profiles.yaml: active:`) overrides base `user_settings.yaml` — edit BOTH or
  your changes silently won't apply. Back up both (`*.bak-<date>`) before editing.
- Hotkeys: only letters, `space`, F-keys, mods `ctrl/alt/shift/win`. NOT right-Alt/AltGr,
  NOT symbols (`/ . ,`) — crash at startup. Empty `stop_key: ''` also crashes startup.
- First model load downloads ~3.3 GB from HuggingFace (`~/.cache/huggingface/hub`); growth
  of that dir confirms a download is progressing vs stuck. Later runs are instant (cached).

## Verify honestly
- Report what you actually ran: driver/CUDA version from `nvidia-smi`, which DLLs now sit
  in `ctranslate2\`, direct-engine timing, GUI smoke-test log lines. The owner still does
  the final microphone dictation — you can verify the engine and app startup, not live voice.
- GPU STT accuracy/quality depends on model size: CPU base/small; GPU can run large-v3.
  RAM/VRAM tight → fall back to smaller model or CPU int8.
