# VRAM accounting and cuBLAS resolution — measured data

Source: VIDEO-TRANSLATE-BATCH, TASK 001, 2026-09-12, [ПК1: RTX 3050 8 GB], Windows.
Purpose: record what was actually measured, so the "cublas trap did not reproduce"
result is not mistaken for "the trap is gone".

## Setup that produced the numbers

- Fresh VideoLingo clone, `py setup_env.py` → `uv` venv on Python 3.10.
- Installer auto-detects CUDA from `nvidia-smi` (driver 591.86) and picks
  `https://download.pytorch.org/whl/cu129` → `torch==2.8.0+cu129`,
  `torchaudio==2.8.0+cu129` (wheel 3571.8 MB). Whole install: 826 s.
- Versions after install: streamlit 1.49.1, spacy 3.8.16, whisperx 3.8.6, demucs 4.1.0a3.
- **No CUDA Toolkit installed, no `nvidia-cublas-cu12`, no manual DLL copying.**
- Probe input: 16.0 s of real English speech, cut with
  `ffmpeg -ss 5 -t 16 -i VideoLingo/docs/public/videos/demo.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le probe.wav`
  (ffprobe confirmed 15.999938 s). Not silence — deliberate.

## Result (3 runs, all with device=cuda, compute_type=float16, model=large-v3)

| metric | run 1 (bg) | run 2 | run 3 (final) |
|---|---|---|---|
| import torch | — | 3.85 s | 14.19 s |
| model load | 12.87 s | 26.92 s | 7.81 s |
| transcribe 16.0 s audio | 2.52 s | (crashed after) | 2.04 s |
| `torch.cuda.max_memory_allocated()` | 0 MB | — | 0 MB |
| `nvidia-smi` peak | — | — | 6259 MB (baseline 2054 MB → +4205 MB) |
| segments / chars | 4 / 152 | — | 4 / 152 |

Recognized text (real speech, coherent across sentences):

> But then, instead of getting back hexagon and octagon, you get back this.
> And I think we can agree that is just correct. That's right. That is Gabriela.

`get_device_name(0)` → `NVIDIA GeForce RTX 3050`; `torch.version.cuda` → 12.9.

Spread in load time (7.8 → 26.9 s) is cold-cache disk, not a regression; do not read it
as a fault.

## DLL evidence

```
.venv/Lib/site-packages/ctranslate2/
    ctranslate2.dll, cudnn64_9.dll, libiomp5md.dll, _ext.cp310-win_amd64.pyd   <- no cuBLAS

.venv/Lib/site-packages/torch/lib/
    cublas64_12.dll, cublasLt64_12.dll, cudnn64_9.dll, cudnn_*64_9.dll ...

.venv/Lib/site-packages/nvidia/     -> does not exist (never pip-installed)
```

`ctranslate2\` missing cuBLAS is exactly the Trap 1 precondition. It still worked, and
the difference from the failing STT case is the **import order**: the probe does
`import torch` before `from faster_whisper import WhisperModel`, and torch puts its own
`lib` dir on the process DLL search path. Status of that explanation: **hypothesis,
consistent with the evidence, not isolated by A/B test.** To confirm it, run the probe
with the torch import removed and see whether it hangs.

Actionable consequence: the real (in-app) VideoLingo path — whisperx inside the app —
has not been exercised. Verify its import order on a single-video run before treating
Trap 1 as closed.

## VRAM sampler that works (nvidia-smi, not torch)

```python
import subprocess, threading

def nvidia_smi_used_mb():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                          "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=5)
    return int(out.stdout.strip().splitlines()[0])

class VramSampler(threading.Thread):
    def __init__(self, interval=0.25):
        super().__init__(daemon=True)
        self.interval = interval
        self._halt = threading.Event()          # NOT self._stop — see below
        self.baseline = nvidia_smi_used_mb()
        self.peak = self.baseline
    def run(self):
        while not self._halt.is_set():
            used = nvidia_smi_used_mb()
            if used is not None and used > self.peak:
                self.peak = used
            self._halt.wait(self.interval)
    def stop(self):
        self._halt.set()
```

Start it right before model load, `stop()` + `join()` after transcription, then report
`peak` and `peak - baseline`.

### Pitfall: never name the stop-event `self._stop` on a Thread subclass

`threading.Thread` already defines an internal method `_stop`. Assigning
`self._stop = threading.Event()` shadows it and the thread's own teardown then dies with:

```
File ".../threading.py", line 1118, in _wait_for_tstate_lock
    self._stop()
TypeError: 'Event' object is not callable
```

It surfaces only at `join()`/interpreter exit — i.e. **after** your real work already
succeeded, which reads like "the test failed" when it did not. Use `self._halt`.

## Process/console notes from the same session

- The venv-relative probe call is the sanctioned form:
  `cd VideoLingo && .venv/Scripts/python.exe ../scripts/gpu_probe.py 2>&1 | tee ../logs/gpu_probe.log`
  (wav path is a CLI arg defaulting to `../logs/probe.wav`; no absolute paths in the script).
- `torch` import cost varies 3.8–14.2 s on this machine; budget for it before concluding
  anything is hung.
