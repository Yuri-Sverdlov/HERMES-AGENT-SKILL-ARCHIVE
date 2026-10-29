#!/usr/bin/env python3
"""Extract direct mp4 stream URLs from an HDrezka/rezka.ag film page.

Usage:
    python rezka_parse.py <page.html> [urls_out.txt]

Fetch <page.html> first with rezka_fetch.py (the Anubis gate). Output file is
tab-separated:  <quality>\t<direct_url>   one line per quality tier, LF endings,
no trailing comma (so it is safe to consume with a plain shell while-read loop).

Also prints a note when the nominal tier is NOT 1920x1080 -- rezka's "1080p"
label is a quality TIER, not a resolution guarantee; always confirm with ffprobe
after downloading.
"""

import json
import re
import sys


def extract_block(html):
    """Brace-match the JSON object passed to initCDNMoviesEvents(...)."""
    i = html.find("initCDNMoviesEvents")
    if i < 0:
        raise SystemExit("initCDNMoviesEvents not found -- page is probably "
                         "the Anubis challenge, not the film page")
    seg = html[i:i + 14000]
    j = seg.find("{")
    depth = 0
    for k in range(j, len(seg)):
        if seg[k] == "{":
            depth += 1
        elif seg[k] == "}":
            depth -= 1
            if depth == 0:
                return seg[:k + 1], json.loads(seg[j:k + 1])
    raise SystemExit("unbalanced JSON in initCDNMoviesEvents")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    page, out_path = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)

    with open(page, encoding="utf-8") as f:
        html = f.read()

    seg, data = extract_block(html)
    streams = data["streams"]

    rows = []
    for quality, body in re.findall(r"\[(\d+p)\]([^\[]+)", streams):
        variants = [v.strip() for v in body.split(" or ")]
        # Each tier offers "<url>:hls:manifest.m3u8 or <url>" -- take the plain
        # mp4 (no m3u8); the CDN 302-redirects it to a random edge subdomain.
        direct = [v for v in variants if ".mp4" in v and "m3u8" not in v]
        url = (direct[0] if direct else variants[0]).replace("\\/", "/").rstrip(",")
        rows.append((quality, url))

    film_id = re.search(r"initCDNMoviesEvents\((\d+)", seg)
    print("film_id =", film_id.group(1) if film_id else "?")
    print("default_quality =", data.get("default_quality"))
    print("qualities =", [q for q, _ in rows])

    if out_path:
        # newline="\n" is critical on Windows: text mode would emit CRLF and a
        # trailing \r silently breaks the URL in shell while-read loops.
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            for q, u in rows:
                f.write("{}\t{}\n".format(q, u))
        print("wrote", out_path)

    print("NOTE: rezka quality labels are TIERS, not resolutions. "
          "The '1080p' tier commonly serves h264 at height 720.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
