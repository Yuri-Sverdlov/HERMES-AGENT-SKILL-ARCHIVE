#!/usr/bin/env python3
"""shrink_batch.py — shrink one or MANY local videos with named presets.

Stage-0 companion to the download pipeline. Wraps the probe -> sample ->
project -> encode -> verify loop from SKILL.md so it can be run over a whole
folder instead of one file at a time.

Presets (named after the two profiles settled on with Yuri):
    A  540p / 20 fps / CRF 33 / AAC 96k stereo   ~5x    quality-first
    B  360p / 15 fps / CRF 33 / AAC 32k mono     ~10x   size-first
    C  480p / 20 fps / CRF 31 / AAC 64k mono     ~8x    middle

Usage
-----
  python shrink_batch.py --list-presets
  python shrink_batch.py --preset B --file "C:/Videos/a.mp4"
  python shrink_batch.py --preset A --dir "G:/Video/HEGRE" --glob "*.mp4"
  python shrink_batch.py --preset B --dir DIR --target 10      # auto-CRF search
  python shrink_batch.py --preset A --dir DIR --dry-run        # samples only

  # clip-level selection / resume / proof
  python shrink_batch.py --preset B --dir DIR --only "_x10"     # substring filter
  python shrink_batch.py --preset B --dir DIR --verify-only     # re-verify outputs
  python shrink_batch.py --preset B --dir DIR --report out.json

Guarantees
----------
* The original file is never written to. Output = stem + suffix (e.g. `_360p_x10`).
* Idempotent: an existing output that passes verification is skipped, so
  re-running the same command is a no-op.
* `--target N` searches CRF (2 offsets, worst case drives it) instead of
  guessing, because scene variance on one file measured 1.6x at identical
  settings (SKILL.md Pitfall 3).
* Verification is per output: ffprobe duration vs source, resolution match,
  non-zero size, plus a full decode pass (catches bitstream damage that
  ffprobe's header read cannot see).

Paths: this box's ffmpeg is a WINDOWS binary, so every path handed to it is
converted to `C:/...` form (MSYS `/c/...` in argv => "No such file or
directory"). MSYS-style paths on the CLI are accepted and converted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --------------------------------------------------------------------------
# presets
# --------------------------------------------------------------------------
PRESETS: dict[str, dict] = {
    "A": {
        "label": "A",
        "note": "~5x, quality-first",
        "height": 540,
        "fps": 20,
        "crf": 33,
        "audio": "96k",
        "mono": False,
        "suffix": "_540p_x6",
    },
    "B": {
        "label": "B",
        "note": "~10x, size-first",
        "height": 360,
        "fps": 15,
        "crf": 33,
        "audio": "32k",
        "mono": True,
        "suffix": "_360p_x10",
    },
    "C": {
        "label": "C",
        "note": "~8x, middle",
        "height": 480,
        "fps": 20,
        "crf": 31,
        "audio": "64k",
        "mono": True,
        "suffix": "_480p_x8",
    },
}
PRESET_AUDIO_CODEC = "aac"  # MP4-safe everywhere; Opus-in-MP4 is nonstandard
SEG_DEFAULT = 60            # seconds per sample
SEARCH_SEG = 45             # shorter samples while hunting for a CRF


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def msys_to_win(path: str) -> str:
    """`/c/Users/x` -> `C:/Users/x`; leaves `C:/...` and `C:\\...` alone."""
    p = str(path)
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    if m:
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return p


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )


def ffprobe_json(path: str) -> dict:
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", msys_to_win(path),
        ],
        capture_output=True, text=True, errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout or "{}")


def probe_meta(path: str) -> dict:
    info = ffprobe_json(path)
    fmt = info.get("format", {})
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    rate = v.get("r_frame_rate", "0/1")
    try:
        n, d = rate.split("/")
        fps = float(n) / float(d) if float(d) else 0.0
    except Exception:
        fps = 0.0

    vbr = int(num(v.get("bit_rate")))
    if vbr == 0:
        # VBR sources (XVIDEOS and friends) omit the stream bitrate entirely;
        # fall back to container bitrate minus audio rather than printing 0.
        vbr = max(0, int(num(fmt.get("bit_rate"))) - int(num(a.get("bit_rate"))))

    return {
        "path": path,
        "size": int(fmt.get("size") or os.path.getsize(msys_to_win(path))),
        "duration": num(fmt.get("duration")),
        "bitrate": int(num(fmt.get("bit_rate"))),
        "vcodec": v.get("codec_name", "?"),
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "fps": fps,
        "vbitrate": vbr,
        "acodec": a.get("codec_name", "?"),
        "achannels": int(a.get("channels") or 0),
        "abitrate": int(num(a.get("bit_rate"))),
    }


def vf_scale(preset: dict) -> str:
    # -2 keeps the height even and preserves the source aspect ratio
    return f"scale=-2:{preset['height']},fps={preset['fps']}"


def ffmpeg_audio_args(preset: dict) -> list[str]:
    args = ["-c:a", PRESET_AUDIO_CODEC, "-b:a", preset["audio"]]
    if preset["mono"]:
        args += ["-ac", "1"]
    return args


def encode(src: str, out: str, preset: dict, crf: int, start: float | None = None,
           dur: float | None = None, quiet: bool = True) -> bool:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.0f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.0f}"]
    cmd += ["-i", msys_to_win(src), "-vf", vf_scale(preset)]
    cmd += ["-c:v", "libx265", "-crf", str(crf), "-preset", "medium", "-tag:v", "hvc1"]
    cmd += ffmpeg_audio_args(preset)
    if start is None:  # full encode only
        cmd += ["-movflags", "+faststart"]
    cmd += ["-y", msys_to_win(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(f"    ! ffmpeg failed: {r.stderr.strip().splitlines()[-1][:160] if r.stderr else '?'}")
        return False
    return True


def scratch(name: str) -> str:
    return str(Path(tempfile.gettempdir()) / name)


# --------------------------------------------------------------------------
# sampling / CRF search
# --------------------------------------------------------------------------
def sample_worst_bytes(src: str, meta: dict, preset: dict, crf: int, seg: int,
                       offsets=(0.2, 0.8)) -> tuple[int, float]:
    """Encode short samples at two offsets; return (worst_bytes, seg_seconds)."""
    dur = meta["duration"]
    seg = int(min(seg, max(5, dur - 2)))
    worst = 0
    for frac in offsets:
        off = max(0.0, dur * frac - seg / 2)
        tmp = scratch(f"shrink_probe_{os.getpid()}.mp4")
        if not encode(src, tmp, preset, crf, start=off, dur=seg):
            continue
        try:
            b = os.path.getsize(msys_to_win(tmp))
        finally:
            try:
                os.remove(msys_to_win(tmp))
            except OSError:
                pass
        worst = max(worst, b)
    return worst, float(seg)


def project(src: str, meta: dict, preset: dict, crf: int, seg: int) -> tuple[float, float]:
    """Return (projected_full_bytes, projected_factor), worst-case based."""
    worst, used = sample_worst_bytes(src, meta, preset, crf, seg)
    if worst <= 0 or used <= 0:
        return 0.0, 0.0
    full = worst * meta["duration"] / used
    return full, (meta["size"] / full if full else 0.0)


def find_crf(src: str, meta: dict, preset: dict, target: float, budget: int = 6) -> tuple[int, float, float]:
    """Search CRF so the worst-case projection lands at/just past `target`."""
    crf = preset["crf"]
    best = (crf, 0.0, 0.0)
    for _ in range(budget):
        full, factor = project(src, meta, preset, crf, SEARCH_SEG)
        if full <= 0:
            break
        print(f"    crf {crf:>2} -> {full / 1048576:6.1f} MB  {factor:5.1f}x")
        best = (crf, full, factor)
        if factor < target * 0.97:          # too big: squeeze harder
            crf = min(40, crf + 2)
        elif factor > target * 1.18:        # smaller than needed: buy quality back
            crf = max(18, crf - 1)
        else:
            break
    return best


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------
def verify_output(src_meta: dict, out: str, preset: dict, decode: bool = True) -> tuple[bool, str]:
    if not os.path.exists(msys_to_win(out)):
        return False, "missing"
    try:
        m = probe_meta(out)
    except Exception as exc:
        return False, f"ffprobe: {exc}"
    if m["size"] <= 0:
        return False, "zero size"
    if m["vcodec"] != "hevc":
        return False, f"codec={m['vcodec']} (expected hevc)"
    if m["width"] == 0 or m["height"] != preset["height"]:
        return False, f"resolution {m['width']}x{m['height']} != h{preset['height']}"
    if abs(m["fps"] - preset["fps"]) > 0.5:
        return False, f"fps {m['fps']:.2f} != {preset['fps']}"
    if src_meta["duration"] and abs(m["duration"] - src_meta["duration"]) > 1.5:
        return False, f"duration {m['duration']:.1f} vs src {src_meta['duration']:.1f}"
    if decode:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", msys_to_win(out), "-f", "null", "-"],
            capture_output=True, text=True, errors="replace",
        )
        if r.returncode != 0 or r.stderr.strip():
            first = r.stderr.strip().splitlines()
            return False, f"decode errors: {first[0][:120] if first else r.returncode}"
    return True, "ok"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def collect_files(args) -> list[str]:
    files: list[str] = []
    if args.file:
        files += [msys_to_win(f) for f in args.file]
    for d in args.dir or []:
        d = msys_to_win(d)
        pat = args.glob or "*.mp4"
        hits = sorted(Path(d).glob(pat))
        # never feed our own outputs back in
        suffixes = {p["suffix"] for p in PRESETS.values()}
        for h in hits:
            if any(h.stem.endswith(s) for s in suffixes):
                continue
            files.append(str(h).replace("\\", "/"))
    if args.only:
        files = [f for f in files if args.only in os.path.basename(f)]
    seen, uniq = set(), []
    for f in files:
        key = os.path.normcase(os.path.abspath(f))
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser(description="Shrink local videos with named presets.")
    ap.add_argument("--preset", default="B", choices=sorted(PRESETS), help="A/B/C profile")
    ap.add_argument("--file", action="append", help="input file (repeatable)")
    ap.add_argument("--dir", action="append", help="input directory (repeatable)")
    ap.add_argument("--glob", default="*.mp4", help="glob inside --dir (default *.mp4)")
    ap.add_argument("--only", default=None, help="only files whose name contains this")
    ap.add_argument("--suffix", default=None, help="override output suffix")
    ap.add_argument("--target", type=float, default=None,
                    help="wanted reduction factor; enables CRF search (e.g. 10)")
    ap.add_argument("--crf", type=int, default=None, help="override preset CRF (skips search)")
    ap.add_argument("--dry-run", action="store_true", help="sample + project only, no full encode")
    ap.add_argument("--verify-only", action="store_true", help="verify existing outputs only")
    ap.add_argument("--no-decode-check", action="store_true", help="skip full decode pass")
    ap.add_argument("--report", default=None, help="write a JSON report here")
    ap.add_argument("--list-presets", action="store_true")
    args = ap.parse_args()

    if args.list_presets:
        for k, p in PRESETS.items():
            keep = "stereo" if not p["mono"] else "mono"
            print(f"{k}: {p['height']}p/{p['fps']}fps CRF{p['crf']} {PRESET_AUDIO_CODEC} "
                  f"{p['audio']} {keep}  {p['note']}  suffix={p['suffix']}")
        return 0

    preset = dict(PRESETS[args.preset])
    if args.suffix:
        preset["suffix"] = args.suffix
    if args.crf:
        preset["crf"] = args.crf

    files = collect_files(args)
    if not files:
        print("no input files (use --file or --dir)", file=sys.stderr)
        return 2

    for tool in ("ffmpeg", "ffprobe"):
        if not any((Path(d) / f"{tool}.exe").exists()
                   for d in os.environ.get("PATH", "").split(os.pathsep) if d):
            print(f"warning: {tool} not found on PATH", file=sys.stderr)

    keep = "stereo" if not preset["mono"] else "mono"
    print(f"preset {preset['label']}: {preset['height']}p/{preset['fps']}fps "
          f"CRF{preset['crf']} {PRESET_AUDIO_CODEC} {preset['audio']} {keep}  ({preset['note']})")
    print(f"files: {len(files)}"
          f"{'  [DRY RUN]' if args.dry_run else ''}"
          f"{'  [VERIFY ONLY]' if args.verify_only else ''}\n")

    report, failures = [], 0
    for i, src in enumerate(files, 1):
        name = os.path.basename(src)
        stem, _ext = os.path.splitext(src)
        out = f"{stem}{preset['suffix']}.mp4"
        print(f"[{i}/{len(files)}] {name}")

        try:
            meta = probe_meta(src)
        except Exception as exc:
            print(f"    ! cannot probe: {exc}")
            failures += 1
            report.append({"src": src, "out": out, "status": "probe_failed", "note": str(exc)})
            continue

        src_mb = meta["size"] / 1048576
        print(f"    src: {src_mb:.1f} MB | {meta['width']}x{meta['height']} "
              f"{meta['fps']:.0f}fps | {meta['duration']:.0f}s | {meta['vcodec']} "
              f"{meta['vbitrate'] // 1000} kbps")

        if args.verify_only:
            ok, note = verify_output(meta, out, preset, decode=not args.no_decode_check)
            print(f"    verify: {'OK' if ok else 'FAIL'} ({note})")
            failures += 0 if ok else 1
            report.append({"src": src, "out": out,
                           "status": "ok" if ok else "verify_failed", "note": note})
            continue

        # idempotency: a verified output means nothing left to do
        if os.path.exists(msys_to_win(out)):
            ok, note = verify_output(meta, out, preset, decode=False)
            if ok:
                print(f"    skip: existing output verifies ({os.path.getsize(msys_to_win(out)) / 1048576:.1f} MB)")
                report.append({"src": src, "out": out, "status": "skipped", "note": "already done"})
                continue
            print(f"    redo: existing output failed verification ({note})")

        crf = preset["crf"]
        if args.target:
            print(f"    searching CRF for {args.target:g}x (worst of two segments)...")
            crf, full, factor = find_crf(src, meta, preset, args.target)
            if full > 0:
                print(f"    chose CRF {crf}: projected {full / 1048576:.1f} MB ({factor:.1f}x)")
        else:
            full, factor = project(src, meta, preset, crf, SEG_DEFAULT)
            if full > 0:
                print(f"    projected: {full / 1048576:.1f} MB ({factor:.1f}x) at CRF {crf}")

        if args.dry_run:
            report.append({"src": src, "out": out, "status": "dry_run", "crf": crf})
            continue

        t0 = time.time()
        if not encode(src, out, preset, crf):
            failures += 1
            report.append({"src": src, "out": out, "status": "encode_failed",
                           "crf": crf, "note": "ffmpeg error"})
            continue
        dt = time.time() - t0
        out_mb = os.path.getsize(msys_to_win(out)) / 1048576
        factor = src_mb / out_mb if out_mb else 0.0
        ok, note = verify_output(meta, out, preset, decode=not args.no_decode_check)
        print(f"    done: {out_mb:.1f} MB ({factor:.1f}x) in {dt:.0f}s | "
              f"verify: {'OK' if ok else 'FAIL ' + note}")
        failures += 0 if ok else 1
        report.append({"src": src, "out": out, "status": "ok" if ok else "verify_failed",
                       "crf": crf, "src_mb": round(src_mb, 1), "out_mb": round(out_mb, 1),
                       "factor": round(factor, 2), "seconds": round(dt, 1), "note": note})

    print(f"\n{'=' * 78}")
    ok = [r for r in report if r["status"] == "ok"]
    if ok:
        print(f"{'file':<44} {'src MB':>8} {'out MB':>8} {'x':>5}")
        for r in ok:
            print(f"{os.path.basename(r['out']):<44} {r.get('src_mb', 0):>8} "
                  f"{r.get('out_mb', 0):>8} {r.get('factor', 0):>5}")
    for st in ("skipped", "dry_run", "encode_failed", "verify_failed", "probe_failed"):
        hits = [r for r in report if r["status"] == st]
        for r in hits:
            print(f"{st:<14} {os.path.basename(r['src'])}  {r.get('note', '')}")
    print(f"total: {len(report)} | ok: {len(ok)} | problems: {failures}")

    if args.report:
        Path(msys_to_win(args.report)).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report: {args.report}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())