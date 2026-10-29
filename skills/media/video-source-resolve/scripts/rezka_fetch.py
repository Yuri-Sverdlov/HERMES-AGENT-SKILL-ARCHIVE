#!/usr/bin/env python3
"""Fetch an HDrezka/rezka.ag page through the Anubis proof-of-work gate.

Usage:
    python rezka_fetch.py <url> [out.html]

Prints the page length and <title>, writes HTML to out.html if given.
Requires only stdlib + curl on PATH (curl must be >= 7.x; --compressed is mandatory,
the site serves gzip and you get binary junk without it).

The cookie jar is persistent, so a single solve unlocks subsequent page fetches
for the cookie's lifetime. If any call returns the Anubis challenge again, the
function re-solves automatically (up to 5 attempts).

Verified against Anubis 1.25.0 on rezka.ag / hdrezka.me (2026-09).
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Persistent cookie jar. Override with REZKA_COOKIE_JAR env var.
CJ = os.environ.get(
    "REZKA_COOKIE_JAR",
    os.path.join(os.path.expanduser("~"), ".hermes", "rezka_cookies.txt"))


def curl(url, extra=None, referer=None):
    """Run curl with the persistent cookie jar. Returns raw stdout bytes."""
    cmd = ["curl", "-s", "--compressed", "-m", "40", "-A", UA,
           "-b", CJ, "-c", CJ,
           "-H", "Accept-Language: ru-RU,ru;q=0.9",
           "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"]
    if referer:
        cmd += ["-e", referer]
    cmd += (extra or []) + [url]
    return subprocess.run(cmd, capture_output=True).stdout


def solve_anubis(url):
    """Return the page HTML, solving the Anubis PoW challenge if present.

    Protocol (Anubis >= 1.16, verified 1.25.0):
      1. GET page -> HTML contains
         <script id="anubis_challenge" type="application/json">{...}</script>
         with {"challenge": {"id", "randomData", "difficulty", ...},
               "rules": {"algorithm": "fast", "difficulty": N}}
      2. Find nonce n where sha256(randomData + str(n)).hexdigest() starts with
         N zero hex digits.
      3. GET /.within.website/x/cmd/anubis/api/pass-challenge
         ?id=..&response=<hash>&nonce=<n>&redir=<url>&elapsedTime=<ms>
         (it is a GET, not POST -- the client JS uses window.location.replace)
      4. The response sets the auth cookie in the jar; re-GET the page.
    """
    for attempt in range(5):
        html = curl(url).decode("utf-8", "replace")
        m = re.search(
            r'<script id="anubis_challenge" type="application/json">(.*?)</script>',
            html, re.S)
        if not m:
            return html  # already past the gate

        challenge = json.loads(m.group(1))["challenge"]
        random_data = challenge["randomData"]
        difficulty = challenge["difficulty"]
        prefix = "0" * difficulty

        nonce = 0
        while True:
            digest = hashlib.sha256((random_data + str(nonce)).encode()).hexdigest()
            if digest.startswith(prefix):
                break
            nonce += 1

        params = urllib.parse.urlencode({
            "id": challenge["id"],
            "response": digest,
            "nonce": nonce,
            "redir": url,
            "elapsedTime": 3000,
        })
        base = "{}/.within.website/x/cmd/anubis/api/pass-challenge".format(
            urllib.parse.urlparse(url).scheme + "://" + urllib.parse.urlparse(url).netloc)
        curl(base + "?" + params, extra=["-o", "/dev/null", "-L"], referer=url)
        print("[anubis] attempt {}: difficulty={} nonce={}".format(
            attempt, difficulty, nonce), file=sys.stderr)

    return curl(url).decode("utf-8", "replace")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    url = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    html = solve_anubis(url)
    print("len={}".format(len(html)))
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    print("title:", (title.group(1).strip() if title else "??"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
