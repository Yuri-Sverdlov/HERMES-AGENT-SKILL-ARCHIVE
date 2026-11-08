"""Direct GPU engine test for faster-whisper/CTranslate2 on Windows.

Run with the venv python of the app under test, e.g.:
  <venv-python> -u gpu_probe.py [model] [device] [compute_type] [wav]

Purpose: bypass the tray GUI (which can swallow tracebacks) and prove the
CUDA/CuBLAS stack actually transcribes. Healthy output:
  MODEL_LOADED   init=7.9s (large-v3, cuda, float16)
  TRANSCRIBED    took=2.0s lang=en
  PEAK_VRAM      peak=6259MB baseline=2054MB
  TEXT           <the transcript, for eyeballing>

Design notes (each one is a lesson already paid for):
* torch is imported FIRST, before faster_whisper, when it exists in the venv.
  torch registers site-packages/torch/lib in the Windows DLL search path, and
  the cu12x wheels ship cublas64_12.dll there -- so this import order lets
  cuBLAS resolve even when ctranslate2/ has no copy of it. A venv built on
  pure ctranslate2 (whisper-local) has no torch; the import is optional and
  wrapped so that case still works.
* torch.cuda.max_memory_allocated() reports 0 MB for CTranslate2 (it allocates
  outside the PyTorch caching allocator), so VRAM is sampled from nvidia-smi by
  a daemon thread instead. Report peak AND baseline -- a desktop/browser can
  hold ~2 GB idle.
* The sampler thread's stop flag is named _halt, NOT _stop: threading.Thread
  defines an internal _stop() method, and shadowing it with an Event makes
  Thread.join() raise "TypeError: 'Event' object is not callable".
* Pass a wav with 10-20 s of REAL SPEECH when you have one. With no argument
  the script synthesizes 2 s of digital silence, which is a weak probe: Whisper
  can return fluent text for silence, so a green RESULT_OK proves nothing about
  the audio chain (DEV-NOTES SS18). Always read the printed text.
* Hang at model load or transcribe => missing cuBLAS (see skill Trap 1):
  pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12, then copy the DLLs
  next to cudnn64_9.dll in the ctranslate2 package dir.
* Use -u so progress prints are not block-buffered when piped.
"""
import os
import subprocess
import sys
import threading
import time
import wave

sys.stdout.reconfigure(errors="replace")
sys.stderr.reconfigure(errors="replace")


def say(text):
    print(text, flush=True)


def nvidia_smi_used_mb():
    """Current used VRAM in MB, or None if nvidia-smi is unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


class VramSampler(threading.Thread):
    """Poll nvidia-smi and keep the peak.

    The stop flag is _halt, not _stop: Thread._stop is internal and shadowing
    it breaks join().
    """

    def __init__(self, interval=0.25):
        super().__init__(daemon=True)
        self.interval = interval
        self._halt = threading.Event()
        self.baseline = nvidia_smi_used_mb()
        self.peak = self.baseline

    def run(self):
        while not self._halt.is_set():
            used = nvidia_smi_used_mb()
            if used is not None and (self.peak is None or used > self.peak):
                self.peak = used
            self._halt.wait(self.interval)

    def stop(self):
        self._halt.set()


model = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
device = sys.argv[2] if len(sys.argv) > 2 else "cuda"
compute = sys.argv[3] if len(sys.argv) > 3 else "float16"
wav_arg = sys.argv[4] if len(sys.argv) > 4 else None

TMP = os.path.join(os.environ.get("TEMP", os.getcwd()), "gpu_probe")
os.makedirs(TMP, exist_ok=True)

if wav_arg:
    WAV = wav_arg
    if not os.path.isfile(WAV):
        say("ERROR wav not found: %s" % WAV)
        raise SystemExit(2)
else:
    WAV = os.path.join(TMP, "silence.wav")
    with wave.open(WAV, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * (16000 * 2))
    say("WARNING no wav given -> using 2s of SILENCE; a transcript from silence")
    say("WARNING proves nothing. Re-run with a 10-20s real-speech wav.")

# torch FIRST when available -- see design note above. Optional for pure
# ctranslate2 venvs (whisper-local ships no torch).
try:
    import torch
    say("torch          %s (cuda build %s, available=%s)"
        % (torch.__version__, torch.version.cuda, torch.cuda.is_available()))
    if device == "cuda" and torch.cuda.is_available():
        say("device         %s" % torch.cuda.get_device_name(0))
except ImportError:
    say("torch          not installed in this venv (cuBLAS must be co-located)")

from faster_whisper import WhisperModel

sampler = VramSampler()
sampler.start()
say("vram baseline  %s MB used before load" % sampler.baseline)

t0 = time.perf_counter()
m = WhisperModel(model, device=device, compute_type=compute)
t1 = time.perf_counter()
segs, info = m.transcribe(WAV, beam_size=5)
segs = list(segs)  # faster-whisper is lazy: force the work here
tx = "".join(s.text for s in segs).strip()
t2 = time.perf_counter()
sampler.stop()
sampler.join(timeout=2)

say("MODEL_LOADED   init=%.2fs (%s, %s, %s)" % (t1 - t0, model, device, compute))
say("TRANSCRIBED    took=%.2fs lang=%s segs=%d chars=%d"
    % (t2 - t1, getattr(info, "language", "?"), len(segs), len(tx)))
if sampler.peak is not None:
    say("PEAK_VRAM      peak=%sMB baseline=%sMB delta=%sMB (nvidia-smi)"
        % (sampler.peak, sampler.baseline,
           (sampler.peak - sampler.baseline) if sampler.baseline is not None else "?"))
say("TEXT           %s" % tx)

if not tx:
    say("WARNING empty transcript -- engine returned nothing")
    raise SystemExit(4)
say("RESULT_OK")
