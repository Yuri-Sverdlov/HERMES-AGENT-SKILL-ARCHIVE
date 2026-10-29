#!/usr/bin/env python3
"""verify_media.py — prove a downloaded video is complete, not just present.

Replaces the bad "<100 MB means truncated" heuristic, which both false-accuses
short clips and silently passes truncated large files.

Usage:
    python verify_media.py FILE [FILE ...]
    python verify_media.py --dir F:/_DOWNLOADS/pornhub
    python verify_media.py --dir DIR --json        # machine-readable

Exit code 0 = every file OK, 1 = at least one BAD/SUSPECT, 2 = usage/ffprobe error.

Checks per file (real signals, not size guesses):
  1. a video stream exists and reports width/height
  2. container duration is readable  (unreadable => truncated/incomplete moov)
  3. duration vs stream duration agree within tolerance
  4. no leftover .part / .part-FragN.part sibling (download still unfinished)
  5. decode probe of the LAST seconds — catches tail truncation that metadata hides

Requires ffprobe/ffmpeg on PATH.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".ts", ".m4v"}


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def ffprobe_json(path):
    code, out, err = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ])
    if code != 0:
        return None, err or "ffprobe failed"
    try:
        return json.loads(out), None
    except json.JSONDecodeError as e:
        return None, f"unparseable ffprobe output: {e}"


def tail_decode_ok(path, duration, window=6.0):
    """Decode the final seconds. Truncated files often keep a plausible
    header but fail here — this is the check that catches a killed download.

    NOTE: `-ss` past the end of the actual data exits 0 with no output, so
    seeking alone silently passes a truncated file. We therefore also run a
    full packet count (see packet_scan) which reports "partial file".
    """
    if not duration or duration <= window:
        start = 0.0
    else:
        start = max(0.0, duration - window)
    code, _, err = run([
        "ffmpeg", "-v", "error", "-ss", f"{start:.3f}",
        "-i", path, "-f", "null", "-",
    ])
    return code == 0, err


# Errors that mean the byte stream ends early, as opposed to cosmetic
# container warnings. Matched case-insensitively against ffprobe stderr.
TRUNCATION_MARKERS = (
    "partial file",
    "invalid nal unit size",
    "missing picture in access unit",
    "error while decoding stream",
    "invalid data found when processing input",
    "truncat",
)


def packet_scan(path):
    """Walk every video packet and report readable-vs-expected duration.

    This is the check that actually catches a killed download: a file cut to
    a third of its length keeps the original header (so container duration
    still reads 600 s) but only decodes a third of the packets, and ffprobe
    emits "partial file" on stderr.

    Returns (packets, readable_duration_or_None, truncation_errors[]).
    """
    code, out, err = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
        "-show_entries", "stream=nb_read_packets",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    packets = None
    if out:
        try:
            packets = int(out.splitlines()[0].strip())
        except (ValueError, IndexError):
            packets = None

    low = (err or "").lower()
    errors = sorted({m for m in TRUNCATION_MARKERS if m in low})

    # Longest decodable timestamp — independent of the header's claim.
    code2, out2, _ = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "packet=pts_time", "-read_intervals", "99999%+#1",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    readable = None
    if out2:
        vals = [v for v in (x.strip() for x in out2.splitlines()) if v and v != "N/A"]
        if vals:
            try:
                readable = float(vals[-1])
            except ValueError:
                readable = None
    return packets, readable, errors


def partials_for(path):
    base = os.path.basename(path)
    d = os.path.dirname(path) or "."
    hits = []
    for pat in (f"{base}.part", f"{base}.part-Frag*.part", f"{base}.ytdl"):
        hits += glob.glob(os.path.join(d, pat))
    return hits


def verify(path):
    r = {"file": path, "status": "OK", "reasons": []}
    if not os.path.isfile(path):
        r.update(status="BAD", reasons=["file does not exist"])
        return r

    r["size_bytes"] = os.path.getsize(path)
    if r["size_bytes"] == 0:
        r.update(status="BAD", reasons=["zero-byte file"])
        return r

    leftovers = partials_for(path)
    if leftovers:
        r["status"] = "BAD"
        r["reasons"].append(
            f"unfinished download artifacts present: {[os.path.basename(x) for x in leftovers]}"
        )

    meta, err = ffprobe_json(path)
    if meta is None:
        r.update(status="BAD")
        r["reasons"].append(f"ffprobe cannot read the file ({err}) — truncated or broken container")
        return r

    fmt = meta.get("format", {})
    streams = meta.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]

    if not vstreams:
        r["status"] = "BAD"
        r["reasons"].append("no video stream")
    else:
        v = vstreams[0]
        w, h = v.get("width"), v.get("height")
        if not w or not h:
            r["status"] = "BAD"
            r["reasons"].append("video stream reports no dimensions")
        else:
            r["resolution"] = f"{w}x{h}"
        r["vcodec"] = v.get("codec_name")

    r["has_audio"] = bool(astreams)
    if not astreams:
        r["reasons"].append("note: no audio stream (may be intentional)")

    dur = fmt.get("duration")
    try:
        dur = float(dur)
    except (TypeError, ValueError):
        dur = None
    if dur is None or dur <= 0:
        r["status"] = "BAD"
        r["reasons"].append("container duration unreadable — incomplete moov atom")
    else:
        r["duration_s"] = round(dur, 2)
        # container vs stream duration disagreement => damaged index
        for s in vstreams:
            sd = s.get("duration")
            try:
                sd = float(sd)
            except (TypeError, ValueError):
                continue
            if sd > 0 and abs(sd - dur) > max(2.0, 0.05 * dur):
                if r["status"] == "OK":
                    r["status"] = "SUSPECT"
                r["reasons"].append(
                    f"container duration {dur:.1f}s vs video stream {sd:.1f}s disagree"
                )

    ok, derr = tail_decode_ok(path, dur)
    if not ok:
        r["status"] = "BAD"
        r["reasons"].append(f"tail decode failed — file is truncated ({derr.splitlines()[:1]})")

    # Full packet walk. This is the check that catches a killed download whose
    # header still advertises the original duration: `-ss` past the real end
    # exits 0, so seeking alone is not enough.
    packets, readable, terrs = packet_scan(path)
    if packets is not None:
        r["video_packets"] = packets
    if readable is not None:
        r["readable_duration_s"] = round(readable, 2)
    if terrs:
        r["status"] = "BAD"
        r["reasons"].append(
            f"byte stream ends early — ffprobe reports {terrs} (truncated download)"
        )
    if dur and readable is not None and readable > 0:
        # Decodable content materially shorter than the header's claim.
        shortfall = dur - readable
        if shortfall > max(5.0, 0.05 * dur):
            r["status"] = "BAD"
            r["reasons"].append(
                f"only {readable:.1f}s of {dur:.1f}s decodable "
                f"({100.0 * readable / dur:.0f}% present) — truncated"
            )

    if dur and dur > 0:
        r["avg_bitrate_kbps"] = round(r["size_bytes"] * 8 / dur / 1000)

    return r


def main():
    ap = argparse.ArgumentParser(description="Verify downloaded video files are complete.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dir", help="verify every video file in this directory")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    a = ap.parse_args()

    targets = list(a.files)
    if a.dir:
        for n in sorted(os.listdir(a.dir)):
            if os.path.splitext(n)[1].lower() in VIDEO_EXT:
                targets.append(os.path.join(a.dir, n))
    if not targets:
        ap.error("give FILE(s) or --dir")

    code, _, _ = run(["ffprobe", "-version"])
    if code != 0:
        print("ERROR: ffprobe not on PATH — install ffmpeg", file=sys.stderr)
        return 2

    results = [verify(t) for t in targets]

    if a.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        width = max(len(os.path.basename(r["file"])) for r in results)
        for r in results:
            mark = {"OK": "OK     ", "SUSPECT": "SUSPECT", "BAD": "BAD    "}[r["status"]]
            mb = r.get("size_bytes", 0) / 1048576
            print(
                f"{mark} {os.path.basename(r['file']):<{width}}  "
                f"{mb:8.1f} MB  {r.get('duration_s', '?'):>8} s  "
                f"{r.get('resolution', '?'):>10}"
            )
            for why in r["reasons"]:
                print(f"        - {why}")
        bad = sum(1 for r in results if r["status"] != "OK")
        print(f"\n{len(results) - bad}/{len(results)} OK, {bad} need attention")

    return 1 if any(r["status"] != "OK" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
