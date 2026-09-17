---
name: video-fetch
description: Download one video fast; diagnose slow/403 by host.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [video, download, yt-dlp, aria2c, throttle, cloudflare, youtube, hls]
    related_skills: [video-source-resolve, video-batch-runner]
---

# Video Fetch

**Stage 2 of 3.** Get the bytes for **one** video, quickly, and diagnose it when
it is slow or blocked. Resolving aggregator links is `video-source-resolve`;
driving a list of N is `video-batch-runner`.

**Universal rule: try `yt-dlp` with the page URL first.** It attaches
Referer/tokens that raw curl/aria2c cannot, which is why aria2c 403s on CDNs
that yt-dlp handles without a flag.

```bash
yt-dlp -o "%(title).80s [%(id)s].%(ext)s" "<page-url>"
```

Per-host commands and quirks live in `references/host-matrix.md` — **read it
before improvising flags.** Adding a new host means adding a row there, not
writing a new skill.

## When to Use

- One video, one URL, and you want it on disk correctly
- A download is crawling and you need the cause, not a guess
- A download 403s and you need the right escalation, not flag roulette

For 5+ items, or anything that may outlive the session, go to
`video-batch-runner` — it adds the manifest/resume/verify layer that bare
parallel processes lack.

## What `-N` actually does (read before tuning it)

`-N` sets **concurrent fragment** downloads. One flag, four host behaviours:

| Format shape | Effect of `-N` | Example |
|---|---|---|
| Fragmented HLS / m3u8 | **Helps most** — `-N 8` ≈ 4 MB/s | Pornhub |
| Single plain mp4 | Harmless, mostly a no-op | eporner, lookatvintage |
| YouTube DASH | **Breaks it** — forces DASH-only clients → 403 | YouTube |
| Session-throttled CDN | Useless, but not the flag's fault | VK / okcdn.ru |

Two claims keep getting written down and are **both false**: "`-N` only helps
DASH" and "`-N` doesn't work on HLS". **HLS is exactly where it helps most;
YouTube DASH is where it hurts.** On VK it does nothing because okcdn.ru
throttles the *session*, not the connection count — a different root cause than
the flag.

## Slow stream? Diagnose the signed URL before touching flags

**This is the general rule, not a Pornhub trick.** When any download crawls, do
NOT restart it and do NOT cycle `-N` values. Read the signed URL first:

```bash
yt-dlp -f <format> -g "<page-url>"    # inspect rate= / burst= / validto= / ip=
```

- An explicit `rate=`/`burst=` pair is a **server-side per-connection cap**. No
  value of `-N` escapes it.
- If the format's proto is `https` (plain mp4, not `m3u8_native`), **each
  connection gets its own `rate=` allowance** → multi-connect with `aria2c -x16`
  multiplies the cap. Measured on this box: **500 KB/s → 8.0 MiB/s on the same
  file** (203 MB in ~25 s instead of ~13 min projected).

```bash
URL=$(yt-dlp -f 720p -g "<page-url>")
"C:/Users/Yuri/.hermes/aria2c.exe" -x 16 -s 16 -k 1M --file-allocation=none \
  --header="Referer: https://rt.pornhub.com/" \
  --header="User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  -o "out.mp4" "$URL"
```

Referer is required; a realistic UA avoids a bot-ish default.

- **Signed URLs are time-boxed** (`validfrom`/`validto` ≈ 2 h, plus `ip=`
  binding). Extract and download in the same command — never stash one.
- **Before killing a slow process, prove it is stalled:** stat the `.part` twice
  30–60 s apart and diff the sizes. A throttled download is still progressing,
  and killing it discards real wall-clock time. `~500 KB/s` is survivable;
  `<100 KB/s` warrants the `rate=` inspection above.

## Escalation ladder for 403

Stop at the first step that works. Do **not** cycle flags randomly — after two
failures with the same error class, move down the ladder.

| # | Action | Fixes |
|---|---|---|
| 1 | `pip install -U yt-dlp` | stale extractors — **the single highest-yield step**, especially YouTube |
| 2 | `--impersonate chrome:windows` (needs `curl-cffi`) | Cloudflare anti-bot challenge |
| 3 | `--js-runtimes deno` (`~/.deno/bin/deno.exe`) | "No supported JavaScript runtime" |
| 4 | `--remote-components ejs:github` | JS challenge solving |
| 5 | explicit format selection (`--list-formats` → pick IDs) | m3u8-only "best" that fails |
| 6 | `--cookies-from-browser firefox` (browser **closed**) | auth/age walls; helps format listing |
| 7 | `bgutil-ytdlp-pot-provider` plugin | YouTube PO Token / SABR |

**Verify freshness by date, not by a remembered version string.** yt-dlp breaks
on YouTube every ~2 weeks; anything older than ~2 weeks is suspect:

```bash
yt-dlp --version    # compare against today, not against a version in these notes
```

`--extractor-args "generic:impersonate"` is **not** a substitute for
`--impersonate` — it can extract via `-g` while the download still 403s.

## YouTube specifics

YouTube is the hardest host, and the flags that help elsewhere hurt here.

- **Never `-N` on YouTube** (see the table above).
- Video and audio are **separate DASH streams**; request both explicitly:

```bash
yt-dlp --js-runtimes deno \
  -f "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]" \
  --merge-output-format mp4 -o "out.mp4" "<url>"
```

- **Don't hardcode format IDs.** `135+140` is not universal; some videos carry
  language-suffixed audio (`140-1`, `140-2`) and an explicit ID fails on videos
  without it. Prefer `bestvideo…+bestaudio`.
- `-f "best[height<=720]"` can select m3u8-only formats that then fail — prefer
  the explicit video+audio form.
- Cookies let yt-dlp **list** formats but the CDN still 403s SABR streams;
  freshness is the real fix. Anonymous cookies (no SID/HSID/SAPISID) do nothing.
- **Concurrency:** YouTube rate-limits hard. Max **2** parallel jobs; prefer
  sequential with `--playlist-items` ranges.

## Proving the download is complete

**Presence is not completeness, and size is not completeness.** Run the
verifier instead of eyeballing the directory:

```bash
python "C:/Users/Yuri/AppData/Local/hermes/skills/media/video-fetch/scripts/verify_media.py" --dir F:/_DOWNLOADS/batch
```

It checks each file for a real video stream with dimensions, readable container
duration, container-vs-stream agreement, leftover `.part` / `.part-FragN.part`
artifacts, and — decisively — a **full packet walk** comparing decodable
duration against the header's claim.

That last check matters: a file cut to a third of its length keeps the original
header, so container duration still reads the full 600 s, and a mere `-ss` seek
to the tail **exits 0 and passes**. The packet walk catches it (`partial file`,
`only 200.0s of 600.0s decodable`). Verified both ways on this box: it flags a
truncated file and an orphaned `.part`, and passes 10/10 real downloads.

**Never use a size threshold as an integrity test.** "<100 MB means truncated"
fails in both directions — it condemns a legitimately short clip (a real 58.8 MB
/ 600 s file here passes clean) and waves through a truncated 500 MB file.
Report the measured `ffprobe` values, not the quality you hoped yt-dlp picked.

## Fallback: direct multi-connection download

When you already hold a direct URL and yt-dlp has no extractor for the host,
check Range support first:

```bash
curl -I -H "Range: bytes=0-0" "<URL>" 2>&1 | grep -E "206|Content-Range"
```

`206 Partial Content` → multi-connect is safe. `200 OK` → single-stream curl.

```bash
python "C:/Users/Yuri/.hermes/smart_dl.py" "<URL>" "C:/out.mp4" 6
```

`smart_dl.py` prefers aria2c (6–32 connections, auto-resume) and falls back to a
threaded Python HTTP-Range downloader with `.dlstate.json` resume. Re-run the
same command to resume. Thread guidance: 4 for 10–100 MB, 6 for 100–500 MB, 8
above that — and if total speed doesn't rise with more threads, the server caps
per IP and more connections won't help.

`aria2c.exe` is **not on PATH** — it lives at `C:\Users\Yuri\.hermes\aria2c.exe`.

## Pitfalls

1. **Stale yt-dlp → YouTube 403.** `pip install -U yt-dlp` before any YouTube
   debugging. Check the version against today's date.
2. **`-N` on YouTube.** Forces DASH-only clients → 403. Use explicit
   video+audio format selection.
3. **Assuming `-N` is useless on HLS.** Backwards — HLS is where it helps most.
4. **Wrong Cloudflare flag.** `--extractor-args "generic:impersonate"` extracts
   but still 403s the download. Use `--impersonate chrome:windows`.
5. **Naked CDN URL to curl/aria2c.** Referer-checking CDNs (eporner's gvideo)
   return 403. Pass the page URL to yt-dlp.
6. **Killing a slow download before diagnosing.** Stat the `.part` twice, then
   read `rate=` in the signed URL. Killing throws away progress you can't buy back.
7. **Foreground download → killed at 300 s.** A throttled 478 MB HLS file needs
   ~18 min; a foreground `terminal` call dies at the timeout and takes yt-dlp
   with it. Go straight to `terminal(background=true, notify_on_complete=true)`
   and poll with `tail -2 dlN.log`.
8. **`--no-progress` logs carry no speed info.** To gauge throughput, stat the
   `.part` twice ~30–60 s apart and diff sizes.
9. **Dirty HLS restart.** A killed HLS download leaves
   `*.mp4.part-Frag<N>.part` beside the `.part`. Remove both before retrying.
10. **`$HOME` path mangling.** `$HOME/.hermes/foo` becomes
    `C:\c\Users\Yuri\.hermes\foo`. Use absolute Windows paths (`C:/Users/...`)
    in terminal commands **and** as script arguments — MSYS `/f/...` paths are
    invisible to Python (`file does not exist`).
11. **Assuming the resolution you asked for.** yt-dlp picks the best available;
    a small file often means a small source. Report ffprobe's numbers.

## Verification

- [ ] yt-dlp version fresh relative to today (`yt-dlp --version`)
- [ ] Page URL passed to yt-dlp, not a naked CDN URL
- [ ] `-N` choice matches the host's format shape (not applied to YouTube)
- [ ] Slowness diagnosed via signed-URL `rate=` before any restart
- [ ] `scripts/verify_media.py` passes — not "the file exists"
- [ ] Measured resolution/duration reported to the user
- [ ] No `.part` or `.part-Frag*.part` leftovers in the output dir
