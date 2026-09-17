# Worked extraction traces

Real end-to-end resolutions, kept as evidence of what the chains actually look
like. Useful when a new aggregator link does not match the happy path.

---

## Trace A — Yandex preview → pbembed.me (2026-08-22)

Input: `https://yandex.ru/video/preview/16637789163750160700`

**Hop 1 — Yandex page → yastatic player iframe**
```js
document.querySelector('iframe')?.src
// → https://yastatic.net/video-player/0x5fc846d0d96/pages-common/iframe-default/iframe-default.html#html=<url-encoded iframe>
```

The `#html=` fragment holds a URL-encoded `<iframe>` tag. Decoded:
```html
<iframe src="https://pbembed.me/embed/31568" ... />
```

**Hop 2 — embed page → direct mp4**
```js
document.querySelector('video source')?.src
// → https://pbembed.me/get_file/3/6a17b682160e9a6fb83db9e041b382d5/31000/31568/31568_m.mp4/?embed=true&rnd=1787411858745
```

**Download:** 351 MB. `pbembed.me` caps ~800 KB/s per IP regardless of thread
count, so multi-threading buys nothing here — single stream is fine.

**Counters JSON** in the player fragment also names the original source page:
```json
{"videoUrl": "http://m.pornobomba.co/videos/vecherinka-s-pyanymi-studentkami/"}
```
Handy for metadata even when you download from the embed host.

---

## Trace B — Yandex preview → noodlemagazine.net, JW Player (2026-08-24)

Input: `https://yandex.ru/video/preview/4048101684045215147`

**Hop 1** — same yastatic wrapper; decoded inner iframe:
```
https://noodlemagazine.net/player/-105862004_456239596?m=ab79fa34c4bc26d22534c5d1efa7ad5b&h=332bae4271a7051a
```

**Hop 2 — browser FAILS here**
- with query params → `'utf-8' codec can't decode byte 0xad`
- without query params → `403 Forbidden`

**Hop 2 workaround — curl + Referer**
```bash
curl -sL -e "https://yandex.ru/" "https://noodlemagazine.net/player/-105862004_456239596?m=...&h=..."
```

Page carries `window.playlist`:
```json
{"sources": [
  {"file": "https://cdn2.pvvstream.pro/videos/-105862004/456239596/vid_480p.mp4?secure=...", "label": "480"},
  {"file": "https://cdn.pvvstream.pro/videos/-105862004/456239596/vid_360p.mp4?rs=...",      "label": "360"},
  {"file": "https://cdn.pvvstream.pro/videos/-105862004/456239596/vid_240p.mp4?rs=...",      "label": "240"}
]}
```

Take the highest label → `vid_480p.mp4`.

**Hop 3 — CDN download.** `cdn2.pvvstream.pro` (Cloudflare): Range supported
(206), 507 MB at 480p, **81 MiB/s with aria2c at 6 connections.**

**Why the browser can't win here:** noodlemagazine exposes no `<video>` element;
JW Player constructs it at runtime from `window.playlist`, and the page itself
won't load in the browser tool. Always curl + JSON for this family of hosts.

---

## Trace C — eporner JSON-LD (metadata path)

```js
document.querySelectorAll('script[type="application/ld+json"]')[0].textContent
```

yields:
```json
{"title":"Slutwife At The Gloryhole 1",
 "url":"https://gvideo.eporner.com/P4BXbjqZb9y/P4BXbjqZb9y.mp4",
 "duration":"PT0H23M40S","quality":"1920x1080"}
```

Use it for **title/duration/resolution up front**. Do not download the
`contentUrl` directly — that CDN 403s without a Referer:

```
Exception [AbstractCommand.cc:351] errorCode=22 URI=https://gvideo.eporner.com/...
  -> [HttpSkipResponseCommand.cc:239] The response status is not successful. status=403
```

This aria2c failure is expected and not worth debugging. Pass the **page URL**
to yt-dlp, which attaches the header itself.

---

## Failure note — GUI downloaders are a dead end here

Cisdem VideoPaw (Qt app, window title "Video Downloader") could not be driven:

- `computer_use click element=<Download>` — UIA reports success, the unactivated
  Qt app ignores it
- `delivery_mode='foreground'` — returns `foreground_unavailable: exact target
  HWND … was not foreground after the click`
- same for the `+` and `+ Add URL(s)` buttons

Browser/curl extraction (this skill) replaced it entirely. Expect the same class
of failure from other Qt-based downloaders; don't spend turns on the GUI.
