# HDrezka / rezka.ag — полный разбор

Перенесено из старого скилла `video-extraction` (ПК1, проверено 2026-09-12).
Скрипты: `scripts/rezka_fetch.py`, `scripts/rezka_parse.py` этого скилла.

## HDrezka / rezka.ag (Anubis PoW + voidboost CDN) — verified 2026-09-12

`yt-dlp` does NOT support rezka.ag ("Unsupported URL"). The site sits behind
**Anubis** (techaro.lol) proof-of-work bot protection, and browser tools fail
with `Доступ запрещён: код ошибки ...` (Anubis deny rule on the datacenter IP).
Bypass both stages from the shell:

**Stage 1 — solve Anubis PoW (pure Python, ~1 s at difficulty 2):**

```python
import hashlib, json, re, subprocess, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CJ = r"C:\Users\Yuri\.hermes\rezka_cookies.txt"          # cookie jar - REQUIRED

def curl(url, extra=None, referer=None):
    cmd = ["curl","-s","--compressed","-m","40","-A",UA,"-b",CJ,"-c",CJ,
           "-H","Accept-Language: ru-RU,ru;q=0.9"]
    if referer: cmd += ["-e", referer]
    cmd += (extra or []) + [url]
    return subprocess.run(cmd, capture_output=True).stdout

def solve(url):
    for _ in range(5):
        html = curl(url).decode("utf-8","replace")
        m = re.search(r'<script id="anubis_challenge" type="application/json">(.*?)</script>', html, re.S)
        if not m: return html                       # already past the gate
        c = json.loads(m.group(1))["challenge"]
        rd, diff = c["randomData"], c["difficulty"]
        n, pre = 0, "0"*diff
        while not hashlib.sha256((rd+str(n)).encode()).hexdigest().startswith(pre):
            n += 1                                  # n found at ~difficulty*16 tries
        h = hashlib.sha256((rd+str(n)).encode()).hexdigest()
        q = urllib.parse.urlencode({"id":c["id"],"response":h,"nonce":n,
                                    "redir":url,"elapsedTime":3000})
        curl(f"https://rezka.ag/.within.website/x/cmd/anubis/api/pass-challenge?{q}",
             extra=["-o","/dev/null","-L"], referer=url)
    return curl(url).decode("utf-8","replace")
```

Key details: `--compressed` is mandatory (site serves gzip; without it you get binary junk).
The pass-challenge call is a **GET** (the JS does `window.location.replace`), params
`id / response / nonce / redir / elapsedTime`. The cookie lands in the jar and is
reused for the actual page. Reusable scripts are packaged with this skill — use them instead of retyping the
PoW or the JSON brace-matcher:

```
python "${HERMES_SKILL_DIR}/scripts/rezka_fetch.py" "<film_url>" page.html
python "${HERMES_SKILL_DIR}/scripts/rezka_parse.py" page.html urls.txt
```

`rezka_fetch.py` solves the gate and returns the page; `rezka_parse.py` emits
`<quality>\t<direct_url>` lines (LF endings, no trailing comma) ready to feed a
shell `while IFS=$'\t' read -r q u` loop. Ad-hoc copies also exist at
`C:\Users\Yuri\.hermes\rezka_fetch.py` / `rezka_parse.py` on this machine.

**Stage 2 — extract direct mp4 URLs from the page:**

Search the fetched HTML for `initCDNMoviesEvents`, brace-match the trailing JSON object:

```python
i = html.find("initCDNMoviesEvents"); seg = html[i:i+14000]
j = seg.find("{"); depth = 0
for k in range(j, len(seg)):
    depth += 1 if seg[k]=="{" else (-1 if seg[k]=="}" else 0)
    if depth == 0: end = k+1; break
data = json.loads(seg[j:end])          # {"streams": "[360p]<url>:hls:manifest.m3u8 or <url>,...", ...}
```

Parse `data["streams"]` with `re.findall(r"\[(\d+p)\]([^\[]+)", streams)`, split each body
on `" or "`, and **take the variant WITHOUT `m3u8`** (that is the direct mp4; the other is HLS).
Unescape `\/` → `/`. Qualities are 360p/480p/720p/1080p; `default_quality` is usually 480p.

**Stage 3 — download:**

The `stream.voidboost.one` URL returns **302** to a random edge subdomain
(`erbium.`/`hassium.`/`cobra.` …), and `curl -I` (HEAD) gives **404** — always use
GET with `-L` and `-r 0-0` + `grep Content-Range` to read the real size. The edge
supports Range → aria2c works directly (aria2c follows the redirect itself).

```bash
aria2c -x 6 -s 6 -k 4M --file-allocation=none --continue=true --max-tries=0 \
  --retry-wait=5 --timeout=20 --referer=https://rezka.ag/ -U "$UA" \
  -d "E:/VIDEO_FILMS/FILMS" -o "Name (year) [1080p].mp4" "$URL"
```

**Throttling — the real pitfall.** Observed behavior: an initial burst of ~40–100 MB/s,
then the CDN slams the door — connections go to `DL:0B`, the 302 target times out.
**8 conns/file × 2 files = 16 was too much**; 6 per file is stable (~3.2 MB/s each,
~5.3 MB/s aggregate). Symptom of blocks is `code=302 speed=0B/s` on a follow-up
`curl -L`. Do NOT add extra probe connections while a download runs — they compete
**and trigger the same block.**

**Batch downloads (3+ files): go SEQUENTIAL, ~8 conns on one file at a time.**
For a 3-film batch, running 3 × 8 connections in parallel tripped the same
throttle; running them one after another at `-x 8` each held a steady
4–8 MB/s and finished a 5.2 GB batch in ~15 min. Parallel only paid off for a
pair at 6 conns each. Order: fetch all pages first (Anubis solve is cheap and
the cookie is reusable), then loop the downloads serially. Check free disk space
before starting a batch — E: hit 97% after 8.7 GB of films.

**Windows/msys reading of the emitted URL list.** `rezka_parse.py` writes LF line
endings on purpose. If you generate the list by hand with Python's default text
mode you get CRLF, the trailing `\r` rides along in `$u`, and every curl/aria2c
call fails silently with no obvious error. Build the loop defensively:

```bash
tr -d '\r' < urls.txt > urls_clean.txt
while IFS=$'\t' read -r q u; do
  u="${u%,}"          # drop a trailing comma if present
  ...
done < urls_clean.txt
```

**Beware the sparse-file illusion.** aria2c with `-k 4M` writes chunks spread across
the whole file, so `ls -l` / `--file-size` jump to near-final size within seconds while
only a small % is real. **Never estimate progress from file size** — read aria2c's own
`NNMiB/NNMiB(PP%)` line, and verify completeness only by exact byte match at the end.
`.aria2` control files give working resume even after a kill (it resumed from 48% → 100%).

**Nominal vs actual resolution (rezka).** The tier labelled `1080p` delivered
`h264 1660x720` / `956x720` — height 720, i.e. rezka's labels are a quality *tier*, not
a guarantee of 1920x1080. Always confirm with `ffprobe` after download.

Verify with:
```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height -of default=nw=1 "<file>"
```

