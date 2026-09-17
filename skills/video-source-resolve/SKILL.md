---
name: video-source-resolve
description: Resolve a video page/aggregator link to its real source.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [video, url-extraction, yandex, iframe, browser, curl, jsonld]
    related_skills: [video-fetch, video-batch-runner]
---

# Video Source Resolve

**Stage 1 of 3.** Turn a link the user pasted into the URL you can actually
download from. Nothing here downloads bytes — that is `video-fetch`. For a list
of many links, `video-batch-runner` drives this skill per item.

```
[this skill]            [video-fetch]        [video-batch-runner]
page/aggregator link -> real source -> bytes on disk, verified
```

## When to Use

- The link is an aggregator/preview wrapper (`yandex.ru/video/preview/...`)
- The link is an embed host (`pbembed.me`, `noodlemagazine.net`, `nmcorp.video`, `strip2.in`)
- The link is a mirror of another platform (`ukdevilz.com` → VK)
- A GUI downloader failed and you need the direct file URL
- You need metadata (title, duration, resolution) before committing to a download

**Skip this skill** when yt-dlp already supports the host directly — most tube
sites need no resolution step. Check the host matrix in `video-fetch` first;
going to the browser when `yt-dlp <page-url>` would have worked is wasted work.

## The one rule that saves the most time

**An aggregator is a pointer, not a host.** Yandex Video never serves the file;
its page carries a `videoUrl` field naming the real platform (VK, OK, a tube
site), and the bytes always come from there.

So the question is never "download from Yandex or from VK" — it is "which real
host does this pointer name". Resolve the pointer, then hand the real host to
`video-fetch`.

## Decision order (cheapest first)

| # | Try | When |
|---|---|---|
| 1 | `yt-dlp -g "<page-url>"` | always try first — one command, supports most hosts |
| 2 | `curl` + grep for `videoUrl` | Yandex preview pages |
| 3 | `curl` + grep `window.playlist` | JW Player hosts (noodlemagazine, nmcorp) |
| 4 | browser → JSON-LD `contentUrl` | eporner and similar metadata-rich pages |
| 5 | browser → iframe → `<video>` src | everything else / JS-only players |

Escalate only when the cheaper step returns nothing. The browser is the last
resort, not the first move — it costs seconds per link and fails on hosts that
403 the tool.

## Yandex preview — curl fast path

Yandex embeds the true source in the page HTML. Skip the browser entirely:

```bash
curl -sL "https://yandex.ru/video/preview/<ID>" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  | grep -oE 'videoUrl[^,}]*'
```

Returns e.g. `videoUrl":"http://vk.com/video-223537754_456239071"`. ~10× faster
than the browser chain for a batch of 10+ links. Then map the host:

| `videoUrl` names | Hand to `video-fetch` as |
|---|---|
| `vk.com/video-OID_ID` | `https://vkvideo.ru/video-OID_ID` |
| `ukdevilz.com/watch/-OID_ID` | rewrite → `https://vkvideo.ru/video-OID_ID` |
| `youtube.com/...` | the YouTube URL (see YouTube section in `video-fetch`) |
| `ok.ru/video/ID` | the ok.ru URL, yt-dlp handles it |
| tube site (`ebalka.fun`, `myspree.club`, …) | the tube page URL |
| nothing / "Видео не найдено" | deleted — mark `skipped`, do not retry |

Use the browser iframe chain (below) only when `videoUrl` is absent.

## Yandex → embed host, browser chain

When the curl path yields nothing:

```
browser_navigate("https://yandex.ru/video/preview/<ID>")
browser_console("document.querySelector('iframe')?.src")
  → yastatic.net/video-player/…/iframe-default.html#html=<URL-ENCODED iframe>
```

URL-decode the `#html=` fragment to get the inner `<iframe src="...">`, navigate
to it, then:

```js
document.querySelector('video source')?.src || document.querySelector('video')?.src
```

Common embed hosts: `pbembed.me/embed/<id>`, `strip2.in/video/player/<id>/`,
`noodlemagazine.net/player/<id>`, `nmcorp.video/player/<id>`, spankbang. The
extraction method is identical regardless of which host it lands on.

## JW Player hosts (noodlemagazine.net, nmcorp.video)

**The browser fails here** — with query params it throws
`'utf-8' codec can't decode byte 0xad`, without them `403 Forbidden`. These
pages build the `<video>` element dynamically from `window.playlist`, so DOM
inspection cannot reach it. Use curl with a Referer:

```bash
curl -sL -e "https://yandex.ru/" "<player_url>" \
  | grep -oP 'window\.playlist\s*=\s*\K[^;]+'
```

Parse the JSON and take the highest-resolution `sources[].file`:

```json
{"sources": [
  {"file": "https://cdn2.pvvstream.pro/videos/.../vid_480p.mp4?secure=...", "label": "480"},
  {"file": "https://cdn.pvvstream.pro/videos/.../vid_360p.mp4?rs=...",      "label": "360"}
]}
```

`pvvstream.pro` is Cloudflare-fronted and multi-connects beautifully — see the
CDN table in `video-fetch` (measured ~81–88 MiB/s with aria2c).

## eporner — JSON-LD

Metadata including the direct URL sits in `application/ld+json`:

```js
(() => {
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const d = JSON.parse(s.textContent);
      if (d.contentUrl) return JSON.stringify({
        title: d.name, url: d.contentUrl,
        duration: d.duration, quality: d.width + 'x' + d.height,
      });
    } catch (e) {}
  }
  return null;
})()
```

Useful for **metadata** (title, duration, resolution before committing). But do
**not** hand `gvideo.eporner.com` to a downloader — that CDN needs a Referer and
403s without it. Pass the **page URL** to yt-dlp instead; see `video-fetch`.

## VK Video

VK uses a canvas-based player — there is **no `<video>` element** in the DOM, so
browser extraction cannot work. Resolve with yt-dlp:

```bash
yt-dlp -g "https://vkvideo.ru/video-OID_ID"
```

- `ukdevilz.com` is a **VK mirror**. Hitting it directly → Cloudflare 403.
  Rewrite `w0w.ukdevilz.com/watch/-OID_ID` → `vkvideo.ru/video-OID_ID`.
- **Private / age-gated** videos return `Access restricted` or
  `No video formats found`. These need a logged-in VK account. Mark them
  `skipped` — retrying without cookies never changes the outcome.

## Handing off

Give `video-fetch` the **page URL** whenever yt-dlp supports the host (it
attaches Referer/tokens for you). Only pass a naked CDN URL when you extracted
it yourself and yt-dlp has no extractor for that host.

**Signed URLs are time-boxed** (`secure=`, `rs=`, `validto=`, plus an `ip=`
binding). Resolve and download in the same operation — never stash a CDN URL for
later, and never write one into a manifest as the work item. The manifest stores
the **page URL**; resolution happens at download time.

## Pitfalls

1. **Treating the aggregator as the host.** Yandex serves no bytes. Resolve to the
   real platform and download there.
2. **Going to the browser first.** Try `yt-dlp -g`, then curl, and only then the
   browser. Most links never need step 4 or 5.
3. **Passing `gvideo.eporner.com` to a downloader.** 403 without Referer. Use the
   page URL with yt-dlp.
4. **Expecting a `<video>` element on VK or JW Player hosts.** There isn't one.
   Use yt-dlp for VK, curl + `window.playlist` for JW Player.
5. **Queuing a signed URL.** Tokens expire in minutes and are IP-bound. Store page
   URLs, resolve at fetch time.
6. **Retrying private VK videos.** `Access restricted` is an auth wall, not a
   transient error. Mark `skipped` and move on.
7. **`search_files` with MSYS paths.** It needs `C:/Users/Yuri/...`; a
   `/c/Users/Yuri/...` path silently returns 0 results.

## Verification

- [ ] Resolved target names a **real host**, not the aggregator
- [ ] Cheapest sufficient method used (`yt-dlp -g` / curl before browser)
- [ ] For a batch: every input link classified — resolved, or `skipped` with a reason
- [ ] Page URL preferred over naked CDN URL when handing off
- [ ] No signed URL stored for later use
- [ ] Unreachable-by-design items (private VK, deleted previews) marked, not retried
