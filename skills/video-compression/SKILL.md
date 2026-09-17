---
name: video-compression
description: "Shrink a local video N× with ffmpeg: probe, test, encode."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [ffmpeg, transcode, compression, x265, crf, bitrate, resolution, fps, vlc]
    related_skills: [video-fetch, video-batch-runner, video-scene-analysis]
---

# Video Compression (re-encode a local file to a target size)

**Stage 0 companion** to the download pipeline (`video-source-resolve` →
`video-fetch` → `video-batch-runner`): those acquire files, this one shrinks a
file that is **already on disk**.

## When to Use

- "уменьшить размер в N раз", "сжать видео", "сделай по-меньше для телефона"
- "поменяй разрешение / частоту кадров, сохраняя пропорции"
- Storage cleanup, or a copy to send/share

Related but different: `video-scene-analysis` (keyframes/scene cuts), not size.

## The rule

**Never encode the full file to find out how big it will be.** Shrinking is a
budget problem: sample 60 s, measure the real bitrate, extrapolate, pick
settings, then commit. A wrong guess on a 25-minute file costs minutes of CPU
and hundreds of MB — a 6-second test costs nothing.

Second rule, specific to this user: **present the options table, then wait.**
Yuri's stop-signal applies — "посмотри, какие есть инструменты" means research
and propose, *not* encode. Execute only after an explicit "Выполняй / давай
начнем / старт". Deliver options as a table with projected size + factor.

## Presets — start here

Two profiles were agreed with Yuri; reusing them keeps shrunken files comparable
(the same factor always means the same settings). `scripts/shrink_batch.py`
implements all of them, including the probe → sample → project → encode → verify
loop over a whole folder:

```bash
B="C:/Users/Yuri/AppData/Local/hermes/skills/media/video-compression/scripts/shrink_batch.py"

python "$B" --list-presets
python "$B" --preset B --file "C:/Videos/a.mp4"                 # one file
python "$B" --preset A --dir "G:/Video/HEGRE" --glob "*.mp4"    # a folder
python "$B" --preset B --dir DIR --target 10                    # auto-CRF search
python "$B" --preset B --dir DIR --dry-run                      # projections only
python "$B" --preset B --dir DIR --verify-only                  # re-verify outputs
```

| Preset | Settings | Factor | Suffix |
|---|---|---|---|
| **A** | 540p / 20 fps / CRF 33 / AAC 96k **stereo** | ~5× (real 4.9×) | `_540p_x6` |
| **B** | 360p / 15 fps / CRF 33 / AAC 32k **mono** | ~10× (real 10.2×) | `_360p_x10` |
| **C** | 480p / 20 fps / CRF 31 / AAC 64k mono | ~8× (untested) | `_480p_x8` |

Properties that matter when running it over many files: the original is never
written to; an existing output that passes verification is skipped, so a re-run
is a no-op; `--target N` picks CRF instead of guessing; verification includes a
full decode pass (`ffmpeg -v error -i OUT -f null -`) that catches bitstream
damage ffprobe's header read cannot see. Tested on a 20 s synthetic clip:
encode → `verify: OK`, re-run → `skip`, `--target 5` converged 33→35→37 → 5.75×.
On a real batch, run `--dry-run` first and read the projections.

## Step 1 — probe before anything else

```bash
ffprobe -v error -show_entries format=duration,size,bit_rate \
  -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate,channels \
  -of default=noprint_wrappers=1 "IN.mp4"
```

Compute the budget — this is the number everything else serves:

```
target_total_bitrate(kbps) = src_size_bytes / N * 8 / duration_s / 1000
video_budget = target_total - audio_bitrate        # audio is NOT free
```

Worked example: 254 MB / 10 × 8 / 1482 s = **137 kbps total**; minus AAC 32k mono
leaves only ~100 kbps for video. That is why a 10× reduction on a 720p source
*always* means cutting resolution — say so up front instead of promising a
720p 10× that cannot exist.

## Step 2 — test matrix, then extrapolate

Sample from **2–3 different points** in the file (e.g. 20 % and 80 % of
duration), never one:

```bash
ffmpeg -hide_banner -loglevel error -ss 600 -t 60 -i "IN.mp4" \
  -vf "scale=640:-2,fps=15" -c:v libx265 -crf 33 -preset medium \
  -tag:v hvc1 -c:a aac -b:a 32k -ac 1 -y "OUT_sample.mp4"
```

`scripts/size_test.sh` runs a whole matrix of variants on two segments and
prints projected full-file size + compression factor per variant:

```bash
S="C:/Users/Yuri/AppData/Local/hermes/skills/media/video-compression/scripts/size_test.sh"
bash "$S" "IN.mp4" \
  "360p/15 CRF33 aac32|scale=640:-2,fps=15|33|32k" \
  "540p/20 CRF33 aac96|scale=960:-2,fps=20|33|96k"
```

Extrapolate with `full = sample_bytes × duration / 60`, then factor
`= src_bytes / full`. Take the **worst** segment, not the average — measured
scene variance on one file was **75.8 → 122.4 kbps (1.6×)** for *identical*
settings.

## Step 3 — full encode, then verify

```bash
ffmpeg -hide_banner -loglevel error -stats -i "IN.mp4" \
  -vf "scale=640:-2,fps=15" -c:v libx265 -crf 33 -preset medium \
  -tag:v hvc1 -c:a aac -b:a 32k -ac 1 -movflags +faststart \
  -y "IN_360p_x10.mp4"
```

- `-movflags +faststart` — instant start / seekable over network
- `-tag:v hvc1` — required for Apple/QuickTime; harmless elsewhere
- **Original is never touched.** New file, suffix encoding the result
  (`_360p_x10`, `_540p_x6`).
- Verify with `ffprobe` on the output (resolution, fps, both bitrates, duration
  unchanged) and report measured numbers, never "should be about".

## Levers, strongest first

| # | Lever | Effect | Cost |
|---|---|---|---|
| 1 | **Resolution** (`scale=640:-2`) | ~2× fewer pixels per 1.5× scale step | softness — the visible cost |
| 2 | **FPS** (`fps=15`) | roughly linear | judder on motion |
| 3 | **CRF** | **+6 CRF ≈ halves bitrate** (measured ~1.15× per +1 here) | smearing, artifacts |
| 4 | **Audio bitrate** | linear, but small | hiss/rosiness |

`-vf "scale=640:-2"` preserves aspect ratio automatically (`-2` = nearest even
height). Do **not** combine `-crf` with `-b:v` — `-crf` is ignored.

For an exact byte target use 2-pass ABR (`-b:v <budget> -pass 1/2`); prefer CRF
otherwise, it gives better quality at the same average.

`libx265 -preset medium` ran at **255–350 fps** on this box's RTX 4060 at
360–540p — a 25-minute film encoded in 1–2 minutes, so `hevc_nvenc` was never
needed. Reach for NVENC only when a job must finish in seconds.

## Measured reference

Source: 1280×720, 30 fps, H.264 **1107 kbps**, 1 482 s, 254 MB (already
lossy-compressed at ~1.1 Mbps — this matters, see Pitfall 2). Full-file
projections, 60 s samples:

| Settings | Video kbps | Full size | Factor |
|---|---|---|---|
| 360p / 15 fps / CRF 32 / aac48 | 122.4 | 31.2 MB | 7.8× |
| 360p / 15 fps / **CRF 33** / aac32 | ~106 | **23.7 MB (real)** | **10.2×** |
| 360p / 15 fps / CRF 34 / aac32 | 93.0 | 23.2 MB | 10.5× |
| 360p / 12 fps / CRF 33 / aac32 | 96.5 | 23.8 MB | 10.2× |
| 480p / 15 fps / CRF 32 / aac48 | 186.3 | 42.4 MB | 5.7× |
| 540p / 20 fps / CRF 28 / aac96 | 395.9 | 88.2 MB | 2.8× |
| 540p / 20 fps / CRF 32 / aac96 | 230.5 | 59.0 MB | 4.1× |
| 540p / 20 fps / **CRF 33** / aac96 | ~180 | **49.9 MB (real)** | **4.9×** |
| 540p / 20 fps / CRF 34 / aac96 | 175.4 | 49.3 MB | 4.9× |

Real-vs-projected agreed within ~5 % on the 10× run (23.7 vs ~22–25 MB) and
landed 1.6 % off target on the 5× run — the method is trustworthy **when you
pick the worst segment**. Mild `hqdn3d` denoise changed bitrate by <1 % on this
source (121.26 vs 122.42 kbps): do not bother unless the source is visibly noisy.

## Codec / container compatibility

See `references/codec-compat.md` for the full matrix. Short version: H.264 + AAC
in MP4 is the only pairing that plays **everywhere** (TV, DLNA, old Android,
WMP). HEVC plays in VLC and most modern targets but not Windows' built-in player
without the extension. **Opus inside MP4 is nonstandard** — VLC copes, other
players may not; use `-c:a aac` in MP4, or an `.mkv` container if you want Opus.
AV1/VLC 3.x plays it, but anything outside this PC probably has no decoder.

## Pitfalls

1. **MSYS paths passed to ffmpeg.** `ffmpeg` here is a **Windows** binary at
   `/c/ffmpeg/bin`: `-y /c/Users/.../out.mp4` fails with
   `Error opening output ... No such file or directory`. Pass `C:/Users/.../`
   style paths as arguments (bash's own `ls`/`cd` still take MSYS paths).
2. **Estimates come out low on an already-compressed source.** x265 happily
   spends bitrate preserving grain the original encoder kept. A first guess of
   "540p CRF 28 ≈ 45–55 MB" measured **88 MB (2.8×)**. Always measure; expect to
   need 4–6 more CRF than intuition.
3. **One test segment lies.** 1.6× variance between segments on the same file —
   test at least two, size for the worst.
4. **Forgetting audio in the budget.** AAC 48k mono × 1 482 s = 8.9 MB, which is
   28 % of a 32 MB target. `-ac 1` on speech-heavy or non-musical content is
   nearly free; 96k stereo beats 32k mono audibly when there is headroom.
5. **`-crf` alongside `-b:v`.** Silently ignored — pick one mode.
6. **Reusing one temp output path across parallel test runs.** Each variant
   needs its own file, or sizes cross-contaminate.
7. **Reporting the target instead of the result.** Four of the five full-encode
   projections here were within 5 %, one was 4.9× against a stated 5–6× goal —
   say the measured factor, and offer the one-step CRF nudge that fixes it
   (`CRF 33 → 34` was ~2 minutes of work for the correction).
8. **The factor in a preset name does not transfer between files.** A and B were
   tuned on the 254 MB / 1107 kbps / 24-minute source above. On four other clips
   in the same folder (61–129 MB, **721–1201 kbps**, 6–14 min) the *identical*
   settings produced **5.7–8.1×** for B and only **2.8–4.0×** for A — a source
   already squeezed to 721 kbps has little left to discard. Never quote "10×"
   from the preset name: run the projection per file (`--dry-run`), and if a
   factor is genuinely required use `--target N`, which trades quality for it
   (on these clips 10× would need CRF ~37 at 360p and looks it).
9. **A script nobody executed is not a tested script.** `size_test.sh` and this
   skill were generated by the curator from a live session; the sizes here are
   from running them on a real 254 MB file, not from trusting the generator. Run
   any fresh script on one file before pointing it at a folder.
9. **Batch tools are only as proven as their last batch.** `shrink_batch.py` was
   verified on a 20 s synthetic clip (encode, skip-on-rerun, CRF search) — the
   first *real* batch still deserves `--dry-run` and a spot-check of one output
   in VLC. Pending upgrades and open questions live in
   `references/future-improvements.md`.

## Verification

- [ ] `ffprobe` run on source **and** output; resolution/fps/bitrate/duration stated as measured
- [ ] Target budget computed and shown (why this resolution, not a bigger one)
- [ ] Test samples taken from ≥2 offsets; worst case drove the choice
- [ ] Original untouched; output filename encodes resolution + factor
- [ ] `+faststart` (and `hvc1` if HEVC) present
- [ ] Audio codec/bitrate/channels reported explicitly
- [ ] Actual factor reported honestly, with a named lever to correct it if off
