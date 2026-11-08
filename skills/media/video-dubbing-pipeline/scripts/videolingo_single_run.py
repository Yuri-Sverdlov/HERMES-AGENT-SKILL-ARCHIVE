"""videolingo_single_run.py - one VideoLingo pipeline run with timings and GPU sampling.

Copy next to the VideoLingo checkout (e.g. <project>/scripts/) and run FROM the
VideoLingo directory with VideoLingo's own interpreter:

    cd VideoLingo
    .venv/Scripts/python.exe ../scripts/videolingo_single_run.py <file-in-batch/input> \
        [metrics.json] [--resume] [--failed-dir=PATH] [--log=../logs/runNNN.log] \
        2>&1 | tee ../logs/runNNN.log

Flags:
  metrics.json        optional 2nd positional: where to write the summary
                      (successive A/B/C runs must not overwrite one file)
  --log=PATH          the file your shell is tee-ing into; the wrapper counts
                      NoAudioReceived in it afterwards (post-hoc, no plumbing)
  --resume            replay the preserved failed run into output/, clear the
                      synthesis scratch dirs, and pass is_retry=True
  --failed-dir=PATH   where the preserved run lives (default
                      batch/output/<name>-A-FAILED, relative to the VideoLingo cwd)

Why this wrapper exists:
  * process_video() prints Rich panels but no timings, and its 3-attempt step retry
    can swallow a boundary. Wrapping every step gives honest wall-clock per stage
    (DEV-NOTES 18: measure the quantity, not "success").
  * torch.cuda.max_memory_allocated() reads 0 for CTranslate2/Whisper, so peak VRAM
    comes from a background nvidia-smi sampler. GPU utilisation is sampled the same
    way, to prove the stage really ran on the GPU instead of silently falling back
    to CPU.

Maintenance note: STEPS below mirrors batch/utils/video_processor.py. If upstream
renames a step function, fix this list - a missing attribute raises at wrap time,
which is the intended loud failure.

No absolute paths. Console output is ASCII only (cp1252 console).
"""

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


def say(text: str) -> None:
    sys.stdout.write(str(text) + "\n")
    sys.stdout.flush()


def nvidia_smi() -> tuple[int, int] | None:
    """(used MiB, gpu util %) or None if nvidia-smi is unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return None
        parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        return int(parts[0]), int(parts[1])
    except Exception:
        return None


class GpuSampler(threading.Thread):
    """Poll nvidia-smi in the background; keep every sample for later slicing."""

    def __init__(self, interval: float = 0.3):
        super().__init__(daemon=True)
        self.interval = interval
        # NOT `_stop`: threading.Thread defines an internal _stop() method and
        # shadowing it makes Thread.join() raise 'Event' object is not callable
        # AFTER a successful run - it looks like the GPU test broke when it did not.
        self._halt = threading.Event()
        self.samples: list[tuple[float, int, int]] = []

    def run(self) -> None:
        while not self._halt.is_set():
            got = nvidia_smi()
            if got is not None:
                self.samples.append((time.perf_counter(), got[0], got[1]))
            self._halt.wait(self.interval)

    def stop(self) -> None:
        self._halt.set()

    def peak_mb(self) -> int | None:
        return max((s[1] for s in self.samples), default=None)

    def window(self, t0: float, t1: float) -> dict:
        sel = [s for s in self.samples if t0 <= s[0] <= t1]
        if not sel:
            return {"samples": 0}
        utils = [s[2] for s in sel]
        mems = [s[1] for s in sel]
        return {
            "samples": len(sel),
            "peak_mem_mb": max(mems),
            "max_util_pct": max(utils),
            "avg_util_pct": round(sum(utils) / len(utils), 1),
            "pct_samples_util_nonzero": round(
                100.0 * sum(1 for u in utils if u > 0) / len(utils), 1),
        }


# (step label, stage group, module key, attribute name)
STEPS = [
    ("Processing input file",             "1", "vp", "process_input_file"),
    ("Transcribing with Whisper",         "1", "core._2_asr", "transcribe"),
    ("Splitting sentences",               "2", "vp", "split_sentences"),
    ("Summarizing and translating",       "2", "vp", "summarize_and_translate"),
    ("Processing and aligning subtitles", "2", "vp", "process_and_align_subtitles"),
    ("Merging subtitles to video",        "4", "core._7_sub_into_vid", "merge_subtitles_to_video"),
    ("Generating audio tasks",            "3", "vp", "gen_audio_tasks"),
    ("Extracting reference audio",        "3", "core._9_refer_audio", "extract_refer_audio_main"),
    ("Generating audio",                  "3", "core._10_gen_audio", "gen_audio"),
    ("Merging full audio",                "3", "core._11_merge_audio", "merge_full_audio"),
    ("Merging dubbing to video",          "4", "core._12_dub_to_vid", "merge_video_audio"),
]

STAGE_NAMES = {
    "1": "1. Recognition (input file + WhisperX)",
    "2": "2. Translation (split + summarize + translate + align)",
    "3": "3. Synthesis (audio tasks + refer audio + gen audio + merge audio)",
    "4": "4. Assembly (merge subtitles + merge dubbing to video)",
}


def list_files(dirpath: Path) -> list:
    if not dirpath.is_dir():
        return []
    return sorted((p for p in dirpath.iterdir() if p.is_file()), key=lambda p: p.name)


def count_empty(dirpath: Path) -> int:
    return sum(1 for p in list_files(dirpath) if p.stat().st_size == 0)


def count_in_file(path: Path, needle: str) -> int:
    try:
        return path.read_text(encoding="utf-8", errors="replace").count(needle)
    except Exception:
        return -1


def prepare_resume(failed_dir: Path) -> None:
    """--resume: replay a preserved run, then redo only the synthesis.

    is_retry=True stops prepare_output_folder() from wiping output/, and the
    pipeline DOES reuse the ASR/translation artefacts already there (measured:
    ASR 0.00 s, translation 0.54 s, $0 of API spend on the repeat) even though
    no obvious `if exists: return` guard is visible in the sources.

    Both scratch dirs must be cleared: a stage retry regenerates from tmp/ and
    segs/, so a 0-byte TTS file left in them reproduces the same failure.
    Targets are listed in full before anything is removed.
    """
    out = Path("output")
    if not list_files(out):
        if not failed_dir.is_dir():
            raise SystemExit("ERROR (--resume): output/ is empty and failed dir "
                             "not found: " + str(failed_dir))
        shutil.copytree(failed_dir, out, dirs_exist_ok=True)
        say("resume   : copied " + str(failed_dir.resolve()) + " -> " + str(out.resolve()))
    else:
        say("resume   : output/ already populated, keeping it as is")

    for sub in ("segs", "tmp"):
        d = out / "audio" / sub
        victims = list_files(d)
        say("resume   : clearing output/audio/" + sub + " -- " + str(len(victims)) + " file(s)")
        for v in victims:
            say("             " + v.name + "  " + str(v.stat().st_size) + " b")
        for v in victims:
            v.unlink()


def main() -> int:
    raw = sys.argv[1:]
    flags = [a for a in raw if a.startswith("--")]
    positional = [a for a in raw if not a.startswith("--")]
    resume = "--resume" in flags
    failed_dir = Path("batch") / "output" / "3364-r-A-FAILED"
    log_path = None
    for f in flags:
        if f.startswith("--failed-dir="):
            failed_dir = Path(f.split("=", 1)[1])
        elif f.startswith("--log="):
            log_path = Path(f.split("=", 1)[1])

    if not positional:
        say("usage: python videolingo_single_run.py <file-in-batch/input> [metrics.json] "
            "[--resume] [--failed-dir=PATH] [--log=PATH]")
        return 2
    video_name = positional[0]
    metrics_arg = positional[1] if len(positional) > 1 else None

    say("=" * 70)
    say("VideoLingo single-run wrapper")
    say("cwd         : " + str(Path.cwd()))
    say("input file  : " + video_name)
    say("resume      : " + str(resume))
    say("=" * 70)

    # sys.path[0] is THIS script's directory, not the VideoLingo cwd, and the
    # pipeline imports batch.*/core.* relative to cwd. Without this line the run
    # dies instantly with ModuleNotFoundError: No module named 'batch'.
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))

    import batch.utils.video_processor as vp
    from core import (_2_asr, _7_sub_into_vid, _9_refer_audio, _10_gen_audio,
                      _11_merge_audio, _12_dub_to_vid)

    mods = {
        "vp": vp,
        "core._2_asr": _2_asr,
        "core._7_sub_into_vid": _7_sub_into_vid,
        "core._9_refer_audio": _9_refer_audio,
        "core._10_gen_audio": _10_gen_audio,
        "core._11_merge_audio": _11_merge_audio,
        "core._12_dub_to_vid": _12_dub_to_vid,
    }

    results: list[dict] = []

    def wrap(label: str, group: str, module, attr: str) -> None:
        original = getattr(module, attr)

        def timed(*args, **kwargs):
            say("")
            say(">>> STEP START: " + label)
            t0 = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                t1 = time.perf_counter()
                results.append({
                    "step": label, "group": group,
                    "seconds": round(t1 - t0, 2),
                    "t0": t0, "t1": t1,
                })
                say("<<< STEP DONE : " + label + "  {0:.2f} s".format(t1 - t0))

        setattr(module, attr, timed)

    for label, group, mod_key, attr in STEPS:
        wrap(label, group, mods[mod_key], attr)

    if resume:
        prepare_resume(failed_dir)

    sampler = GpuSampler()
    base = nvidia_smi()
    say("gpu baseline (mem MiB, util %): {0}".format(base))
    sampler.start()

    t_all = time.perf_counter()
    ok, step, err = vp.process_video(video_name, dubbing=True, is_retry=resume)
    total = time.perf_counter() - t_all

    sampler.stop()
    sampler.join(timeout=2)

    say("")
    say("RESULT ok={0} failed_step={1!r} error={2!r}".format(ok, step, err))

    stage_totals: dict[str, float] = {}
    for r in results:
        stage_totals[r["group"]] = round(stage_totals.get(r["group"], 0.0) + r["seconds"], 2)

    gpu_per_stage = {}
    for group in ("1", "2", "3", "4"):
        rs = [r for r in results if r["group"] == group]
        if rs:
            gpu_per_stage[group] = sampler.window(
                min(r["t0"] for r in rs) - 0.3,
                max(r["t1"] for r in rs) + 0.3,
            )

    tts_empty = count_empty(Path("output") / "audio" / "segs")
    no_audio = count_in_file(log_path, "NoAudioReceived") if log_path else -1

    summary = {
        "input": video_name,
        "resume": resume,
        "tts_empty_segments": tts_empty,
        "no_audio_received_count": no_audio,
        "no_audio_note": ("counted from " + str(log_path)) if log_path else
                         "not counted: no --log=PATH was passed",
        "ok": ok,
        "failed_step": step,
        "error": err,
        "total_seconds": round(total, 2),
        "steps": [{k: v for k, v in r.items() if k not in ("t0", "t1")} for r in results],
        "stage_seconds": stage_totals,
        "stage_names": STAGE_NAMES,
        "gpu_baseline": base,
        "gpu_peak_mb": sampler.peak_mb(),
        "gpu_samples": len(sampler.samples),
        "gpu_per_stage": gpu_per_stage,
    }

    say("")
    say("=" * 70)
    say("PER-STEP TIMES (s)")
    say("=" * 70)
    for r in results:
        say("  {0:<38} {1:>8.2f}".format(r["step"], r["seconds"]))

    say("")
    say("STAGE TOTALS (s)")
    for g in ("1", "2", "3", "4"):
        say("  {0:<60} {1:>8.2f}".format(STAGE_NAMES[g], stage_totals.get(g, 0.0)))

    say("")
    say("GPU (nvidia-smi)")
    say("  baseline (mem MiB, util %) : {0}".format(base))
    say("  peak memory (MiB)          : {0}".format(sampler.peak_mb()))
    say("  samples taken              : {0}".format(len(sampler.samples)))
    for g in ("1", "2", "3", "4"):
        say("  stage {0}                    : {1}".format(g, gpu_per_stage.get(g)))
    say("  total wall clock (s)       : {0:.2f}".format(total))
    say("")
    say("TTS / RESUME")
    say("  resume                     : " + str(resume))
    say("  tts empty segments (segs/) : " + str(tts_empty))
    say("  NoAudioReceived            : " + str(no_audio) +
        (" (from " + str(log_path) + ")" if log_path else " (no --log given)"))
    say("=" * 70)

    out = (Path(metrics_arg) if metrics_arg
           else Path("..") / "logs" / (Path(video_name).stem + "_metrics.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    say("metrics written to: " + str(out.resolve()))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())