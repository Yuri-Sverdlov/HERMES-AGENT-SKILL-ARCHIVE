# Codec / container compatibility for compressed video

Which of the "shrink it" output settings will actually *play*, on this box and
on the targets the file might travel to.

## Check what is installed before promising anything

```bash
ffmpeg -hide_banner -encoders | grep -iE "libx264|libx265|libsvtav1|libaom|nvenc|qsv|amf"
"/c/Program Files/VideoLAN/VLC/vlc.exe" --version    # VLC 3.0.23 Vetinari on this box
```

This box: `libx264`, `libx265`, SVT/libaom AV1, `*_nvenc` (h264/hevc/av1 on the
RTX 4060), VP8/VP9. ffmpeg is at `/c/ffmpeg/bin`. **No `HandBrakeCLI`** — a GUI
HandBrake install is a separate, optional route for the user; ffmpeg covers it.

## VLC 3.0.23 (what the user watches on)

| Codec | Plays | Notes |
|---|---|---|
| H.264 / AVC | ✅ | no caveats |
| HEVC / H.265 | ✅ | decoder built in; `-tag:v hvc1` only matters for Apple |
| AV1 | ✅ | dav1d has been bundled since VLC 3.0.8; 360–540p decodes in software with little load |
| VP9 | ✅ | fine |
| Opus | ✅ | including **Opus inside MP4**, which is nonstandard but VLC tolerates |

Conclusion for a VLC-on-this-PC target: **every option is safe.** The risk is
never VLC — it is the *other* devices the file eventually lands on.

## Where the real breakage happens

| Target | H.264+AAC/MP4 | HEVC/MP4 | Opus/MP4 | AV1 |
|---|---|---|---|---|
| VLC (any platform) | ✅ | ✅ | ✅ | ✅ (3.0.8+) |
| Smart TV / DLNA renderer | ✅ | most 2016+ | ❌ common failure | ❌ unless 2020+ SoC |
| Older Android | ✅ | often ❌ | ❌ | ❌ |
| iPhone / QuickTime | ✅ | ✅ (needs `hvc1`) | ❌ | 17+ only |
| Windows "Films & TV" | ✅ | ❌ without HEVC extension | ❌ | ❌ |
| Windows Media Player | ✅ | ❌ | ❌ | ❌ |
| Chromecast / browser `<video>` | ✅ | partial | ❌ | ✅ in Chrome |

So:

- **Share-with-anyone / TV / DLNA copy → H.264 + AAC in MP4.** The only
  universally-safe pairing.
- **Personal VLC copy → HEVC wins on size at equal quality.** 10× and 5× runs in
  this library were both x265 (`-tag:v hvc1`, `+faststart`).
- **Want Opus for the audio** → put it in `.mkv`, or accept AAC. Do not ship
  Opus-in-MP4 anywhere but VLC. The bitrate saved is 1–2 MB out of 25 — rarely
  worth the compatibility cliff.
- **AV1** → best bytes-per-quality, but treat it as this-PC-only.

## Flags that matter

| Flag | Why |
|---|---|
| `-tag:v hvc1` | HEVC in an MP4 box that Apple/QuickTime and some TVs will accept; harmless elsewhere |
| `-movflags +faststart` | moves the moov atom to the front — instant start and seekable over network/DLNA |
| `-ac 1` | mono: nearly free quality-wise for voice/speech content, saves ~50 % of audio bytes |
| `-c:a aac -b:a 96k` | stereo comfort zone; AAC 256k stereo was the source, 96k is still clearly better than 32k mono |
| `-c:a copy` | if the source audio is already AAC and small, remux instead of re-encoding |

## Verifying the result actually plays

```bash
ffprobe -v error -show_entries format=duration,bit_rate \
  -show_entries stream=codec_name,profile,width,height,r_frame_rate,channels,bit_rate \
  -of default=noprint_wrappers=1 "OUT.mp4"
```

Confirm: duration identical to the source, `profile` present (an absent profile
means a broken header), and both stream bitrates roughly matching the budget.
Then have the user open it in VLC — the decode path is the only real proof.
