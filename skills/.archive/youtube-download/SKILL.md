---
name: youtube-download
description: Batch-download YouTube videos, all Shorts from a channel, or full playlists via yt-dlp.
platforms: [windows, linux, macos]
---

# YouTube Download (yt-dlp)

## When to use
Use when the user wants to download one or more YouTube videos — a single video, ALL Shorts from a channel, or an entire playlist. The `youtube-content` skill handles transcripts/summaries; this one hands over actual video files.

## Setup
`yt-dlp` is a Python CLI. Install once:
```bash
pip install yt-dlp
```
Requires `ffmpeg` on PATH for merging video+audio streams and embedding thumbnails (yt-dlp output shows `[Merger]` / `[EmbedThumbnail]` errors if it's missing).

## Verify the target first (NEVER download blind)
Always inspect the target before downloading to learn the count, titles, and sizes. Use `--flat-playlist --dump-json` — it lists entries WITHOUT downloading:
```bash
yt-dlp --flat-playlist --dump-json "URL" 2>&1 | head -5
```
Key fields to read from the JSON: `playlist_title`, `n_entries` / `playlist_count`, `duration_string`, `title`. Note: one entry may be `"title": null` — that's usually the unavailable/hidden video.

## Core command
```bash
yt-dlp \
  -f "bv*[height<=1080]+ba/best[height<=1080]" \
  -o "DIR/%(playlist_index)02d_%(title).100s_[%(id)s].%(ext)s" \
  --embed-thumbnail --embed-metadata \
  --no-warnings \
  "URL"
```
- `-f "bv*[height<=1080]+ba/best[height<=1080]"` — best video up to 1080p + best audio, merged.
- `%(playlist_index)02d_` — zero-padded order number (01_, 02_, …) so files sort correctly.
- `%(title).100s_[%(id)s]` — truncate title to 100 chars, append video ID to avoid collisions.
- `--embed-thumbnail --embed-metadata` — stamp cover art + title/uploader into the file itself.
- Output is `.mkv` (yt-dlp merges video+audio into Matroska automatically).

## Workflow
1. **Create the destination directory first** — `mkdir -p "E:/PATH"`. yt-dlp won't create nested dirs by itself.
2. Inspect with `--flat-playlist --dump-json` (above) to confirm count/size and warn the user about space.
3. **Ask where to save** before launching on anything large.
4. Run the core command.

## PITFALLS
- **yt-dlp progress ≠ final file size (⚠️ critical).** `[download] 100% of 219MiB` shows the **last fragment** (often just the audio track), not the merged .mp4/.mkv. Actual file is 5-10× larger. **Always verify with `ls -lh`** after download before reporting size to the user.
- **Large playlists (many full-length videos) = many GB.** A 44-film playlist ≈ tens of GB. Tell the user the scale up front and confirm the target drive.
- **Long downloads must run in the background.** 44 films takes a long time. Use `terminal(background=true)` + `notify_on_complete=true` so you get pinged on completion. Do NOT use shell `&` (the terminal tool rejects it) and do NOT block the session.
- **`-N` multi-fragment causes YouTube 403.** Using `-N 6` (multi-thread) on YouTube videos can trigger `HTTP Error 403: Forbidden` — YouTube's CDN blocks multi-fragment requests. Fix: drop `-N` and add `--extractor-args "youtube:player_client=android"` (and optionally `--compat-options no-youtube-unavailable-videos`). This uses a single-thread android client download that YouTube allows:
  ```
  yt-dlp \
    --extractor-args "youtube:player_client=android" \
    --compat-options no-youtube-unavailable-videos \
    -f "best[height<=1080]" \
    -o "DIR/%(playlist_index)02d_%(title).80s_[%(id)s].%(ext)s" \
    --embed-thumbnail --embed-metadata \
    --no-warnings \
    "URL"
  ```
  Note: with android client, omit `+ba` (best audio is already included in `best[height<=1080]`), and use `%(title).80s` since titles can be long + contain emoji/pipe chars.
- **Paths with non-ASCII (Cyrillic) work fine** in both the output dir and titles — no extra escaping needed under git-bash on Windows.
- 1 hidden/unavailable video in a playlist is normal — yt-dlp logs `INFO - 1 unavailable video is hidden` and skips it. Don't treat it as a failure.
- Titles containing `?`/emoji are left as-is in filenames (valid on Windows, but the `?` in `03_film?` is technically an illegal filename char — yt-dlp strips/replaces it automatically; if you see a mismatch, that's why).

## Verification
After completion, `ls -lh` the target dir and confirm the file count matches `n_entries` (minus any hidden ones). Then report the count and total size to the user.