# Host matrix

**Single source of truth for per-host download behaviour.** A new host is a new
**row here**, never a new skill. If a fact about a host appears in more than one
place, this file wins.

Universal rule: pass the **page URL** to yt-dlp first; it attaches
Referer/tokens that raw curl/aria2c cannot.

## Quick reference

| Host | Command | Pitfall |
|---|---|---|
| eporner.com | `yt-dlp -N 6 -o out.mp4 "<page-url>"` | aria2c/curl → 403. Never pass the gvideo URL |
| pornhub.com / rt.pornhub.com | `yt-dlp -N 8 --no-progress -o "%(title).80s [%(id)s].%(ext)s" "<page-url>"` | works out of the box; watch the `rate=` throttle |
| VK Video (vkvideo.ru) | `yt-dlp -o out.mp4 "<page-url>"` | okcdn.ru signed one-time URL, no Range; `-N` buys nothing |
| ukdevilz.com | rewrite `w0w.ukdevilz.com/watch/-OID_ID` → `vkvideo.ru/video-OID_ID` | direct hit = Cloudflare 403. It is a VK mirror |
| YouTube | `pip install -U yt-dlp`, then explicit video+audio | **never `-N`** → 403 on DASH. See SKILL.md |
| lookatvintage.com | `yt-dlp -N 8 "<page-url>"` | generic extractor; short URL 302s to the full-title slug |
| faphouse.com | `yt-dlp -g "<page-url>"` | generic extractor → xhcdn.com mp4 |
| fapnado.com | `yt-dlp --impersonate chrome:windows -o out.mp4 "<page-url>"` | Cloudflare; mp4 360–480p only |
| Cloudflare sites (generic) | `yt-dlp --impersonate chrome:windows -o out.mp4 "<url>"` | needs `curl-cffi`. NOT `--extractor-args "generic:impersonate"` |
| noodlemagazine / nmcorp.video | resolve first (`video-source-resolve`), then aria2c | JW Player; browser fails. CDN is fast |
| pbembed.me | `smart_dl.py` (HTTP Range) | server caps ~800 KB/s per IP — threads don't help |
| strip2.in | resolve → `fp.spac.me` mp4 | ~280 KB/s single-thread; multi-thread unproven |
| Yandex Video | not a host — resolve the pointer first | see `video-source-resolve` |
| reddit.com/user/<u> | list via Arctic Shift API → `i.redd.it` straight into aria2c | reddit 403s this IP, even in a real browser. See section below |
| redgifs.com | JSON API: temp token → `/v2/users/<u>/search` → `media.redgifs.com/<Slug>.mp4` into aria2c | hd URL is permanent and unsigned; no Referer, no login. See section below |
| erome.com | `yt-dlp -g` then check Range | album pages carry many items |
| ok.ru | `yt-dlp "<page-url>"` | usually works unmodified |

## CDN performance (measured on this box)

Real numbers from three sessions — use them to set expectations, not as
guarantees.

| Source → CDN | Size | Engine | Speed |
|---|---|---|---|
| noodlemagazine → cdn2.pvvstream.pro (CF) | 485 MB | aria2c, 6 conn | **81 MiB/s** |
| nmcorp.video → cdn2.pvvstream.pro (CF) | 651 MB | aria2c, 8 conn | **88 MiB/s** |
| Pornhub `https` mp4 + `aria2c -x16` | 203 MB | aria2c, 16 conn | **8.0 MiB/s** (from 500 KB/s) |
| Pornhub HLS via `yt-dlp -N 8` | ~180–500 MB | yt-dlp | ~4 MB/s |
| eporner (Referer via yt-dlp) | 140–600 MB | yt-dlp, 6 frag | 1.5–6 MB/s |
| strip2.in → fp.spac.me | 210 MB | single curl | ~280 KB/s |
| pbembed.me | 351 MB | single curl | ~800 KB/s (per-IP cap) |
| VK / okcdn.ru | — | yt-dlp | ~600 KB/s after first MBs |

**Decision tree by CDN:**

1. `pvvstream.pro` → aria2c, 6–8 connections. Fastest thing here by an order of magnitude.
2. Pornhub `https` format → `aria2c -x16` after reading `rate=`.
3. `pbembed.me` / `fp.spac.me` → single curl; per-IP caps make threads pointless.
4. Unknown CDN → test Range (`curl -I -H "Range: bytes=0-0"`), default to single
   stream until multi-connect is proven faster.

## Per-host notes

### eporner.com
Video sits behind JSON-LD `contentUrl` → `gvideo.eporner.com/<id>/<id>.mp4`.
The CDN **requires a Referer** and returns 403 to curl/aria2c; the failure looks
like `errorCode=22 ... status=403` and is not worth debugging. yt-dlp attaches
the header itself — always give it the page URL. `-N 6` works here (single plain
mp4, not DASH). Range is supported (206) once the Referer is present.

### pornhub.com / rt.pornhub.com
Easiest host after eporner: no cookies, no impersonation, no PO token.

- Single-format HLS via yt-dlp, **but** `1080p`/`720p`/`480p`/`240p` formats use
  proto `https` (plain mp4) — those multi-connect with aria2c.
- **Resolution varies per video.** Observed in one batch: 1080p (~400–500 MB /
  20 min), 720p (~180 MB / 12 min), 480p (~60 MB / 10 min), plus a 720p outlier
  at 2.07 GB. A small file means a small source, not a failed download.
- **Variable CDN throttle.** The signed URL carries `&rate=500k&burst=1400k` —
  a per-connection cap. `-N` cannot escape it; `aria2c -x16` on the `https`
  format can (16 connections ≈ 16× the cap). See SKILL.md for the exact command.
- Both viewkey styles work: legacy `ph5ed9aaf76a140` and new 13-hex `6774e86e0f666`.
- Output dir convention on this box: `F:\_DOWNLOADS\pornhub`.

### VK Video (vkvideo.ru / vk.com)
Canvas-based player, **no `<video>` element** — browser extraction cannot work.
okcdn.ru issues one-time signed URLs that reject HTTP Range for direct curl, and
throttles the *session* to ~600 KB/s after the first few MB. `-N` therefore
buys nothing — the cause is the session cap, not the flag.

Private/age-gated videos return `Access restricted` or `No video formats found`:
an auth wall needing a logged-in account. Mark `skipped`; retrying never helps.

### ukdevilz.com
A **VK mirror**. `w0w.ukdevilz.com/watch/-OID_ID` ↔ VK video `OID_ID`. Hitting
ukdevilz directly gives Cloudflare 403 — rewrite to `vkvideo.ru/video-OID_ID`
and treat it as VK (including the private-video caveat).

### lookatvintage.com
Generic extractor; the page embeds a signed mp4 from
`mp4-gcore.xvideos-cdn.com`. No impersonation or cookies needed.

- Short URLs 302 to the full-title slug — yt-dlp follows it, pass either form.
- **Only one format exists** (`mp4_sd`, 854x480). Don't hunt for 720p.
- `-N 8` works (plain mp4). Files are small (~50–60 MB / 9 min).

### YouTube
Full treatment in SKILL.md (DASH, format selection, SABR ladder, 2-job
concurrency cap). The one-line summary: **update yt-dlp, never use `-N`, request
`bestvideo…+bestaudio` explicitly.**

### reddit.com (profiles, galleries, gifs)

**The site itself is unreachable from this box.** `reddit.com/user/<u>/submitted.json`
returns 403, and a real browser gets `You've been blocked by network security`
after a `js_challenge` redirect loop (`title == "🐴"`). `old.reddit.com` is equally
blocked. Redlib mirrors (`safereddit.com`, `redlib.privacyredirect.com`) answer 200
but serve an Anubis / "Gandalf" proof-of-work wall — useless for curl. `yt-dlp`
has no RedditUser extractor any more (`Unsupported URL`).

**Listing: Arctic Shift API — no auth, works from here:**

```bash
curl -s "https://arctic-shift.photon-reddit.com/api/posts/search?author=<user>&limit=100&sort=desc"
```

Returns `{"data":[post…]}`, newest first. Paginate with
`&before=<created_utc of the last item>`; a batch smaller than `limit` means done.
`api.pullpush.io` (the other Pushshift successor) answered **526** — dead, don't
waste a step on it.

**Files: `i.redd.it` / `v.redd.it` is a different CDN and is NOT blocked** — no
Referer, no cookies, Range supported. aria2c `-j 3 -x 8` does ~7 MiB/s per file
(measured: 4.87 GB / 100 files in ~5 min).

Post shapes that matter:

- `post_hint == "image"` + `url_overridden_by_dest` on `i.redd.it` → exactly 1 file.
- `is_gallery` → one file per `media_metadata[id].s.u` (HTML-escaped — `html.unescape`
the `&amp;`). `e: AnimatedImage` / `m: image/gif` is a **gif**, i.e. one file.
- `is_video: true` on an `i.redd.it/*.gif` is just an animated gif — there is no
  DASH to merge. Only `v.redd.it` posts need yt-dlp per post.
- **Count files, not posts.** One author's 100 newest posts yielded 228 media
  files (50% galleries); the first 100 files covered only 40 posts.

Verify images/gifs by size against HEAD `Content-Length` **plus** magic bytes
(`GIF8`, `FF D8`, `\x89PNG`) — `verify_media.py` only understands video containers.

### redgifs.com
Creator/profile pages are a **JSON API, not HTML to scrape**. Anonymous temp
token, no account needed:

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
TOK=$(curl -s -H "User-Agent: $UA" https://api.redgifs.com/v2/auth/temporary \
      | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -H "Authorization: Bearer $TOK" -H "User-Agent: $UA" \
  "https://api.redgifs.com/v2/users/<name>/search?order=recent&count=100&page=1"
```

Response: `{gifs:[...], total, pages}` (paginate while `page < pages`). Each gif
carries `id`, `duration` (seconds, float), `width`/`height`, `fileSize` (often 0 —
ignore it), and `urls.{hd,sd,silent,poster,thumbnail}`.

- `urls.hd` is `https://media.redgifs.com/<Slug>.mp4` — **permanent, unsigned,
  no auth, no Referer required.** Unlike pornhub/eporner, feed it straight to
  aria2c. `<Slug>` is the TitleCase form of the gif id.
- aria2c input-file batch (`url` + `  out=<id>.mp4` lines, LF endings), 3 jobs ×
  8 conns, `--header="Referer: https://www.redgifs.com/"` as harmless insurance.
- Measured on this box: **21 clips (45–60 s, 1080x1926), 676 MB, ~3 min at
  8–11 MiB/s aggregate.**
- `duration` from the API makes a "short clips only" filter a JSON test — no
  ffprobe round-trip, no per-file yt-dlp probe.
- yt-dlp also has a RedGifs extractor (`redgifs.com/watch/<id>` page URL) — use
  it for a single file; use the API for a whole creator.
- Output dir convention on this box: `G:\_DOWNLOADS\redgifs-<user>`.

### Yandex Video
**Not a host.** `yandex.ru/video/preview/<ID>` is a pointer whose HTML names the
real platform in a `videoUrl` field. Resolve with `video-source-resolve`, then
download from the platform it names.
