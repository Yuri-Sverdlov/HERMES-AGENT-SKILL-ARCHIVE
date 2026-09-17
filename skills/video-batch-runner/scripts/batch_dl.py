#!/usr/bin/env python3
"""batch_dl.py — manifest-driven, resumable, idempotent video batch downloader.

Solves the failure this skill exists for: a 40-film batch launched as bare
background processes with no state file. The session died and left files of
unknown integrity that had to be triaged by guessing at sizes.

A batch here is a manifest plus a loop that is safe to re-run at any time:
re-running skips verified items, retries failures, and never points two
processes at one destination.

Workflow
--------
    # 1. parse a pasted dump into a manifest (handles glued URLs and '==')
    python batch_dl.py init --out F:/_DOWNLOADS/batch --urls-file dump.txt

    # 2. show what would happen -- no downloads
    python batch_dl.py status --out F:/_DOWNLOADS/batch

    # 3. run pending/failed items (repeat freely; it is idempotent)
    python batch_dl.py run --out F:/_DOWNLOADS/batch --concurrency 3

    # 4. re-verify everything and print the final table
    python batch_dl.py verify --out F:/_DOWNLOADS/batch

Resume after a crash: `run` treats items left 'running' as crash victims,
verifies their files, and requeues the ones that fail.

Notes
-----
* Only page URLs go in the manifest -- signed CDN URLs are time-boxed and
  IP-bound, so resolution happens at download time.
* 'done' is set only when verify_media.py passes, never on exit code alone.
* YouTube is capped at 2 concurrent jobs regardless of --concurrency.
* Windows: pass Windows-style paths (F:/...); MSYS /f/... is invisible to Python.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# verify_media.py ships with the video-fetch skill (stage 2).
VERIFIER = os.path.normpath(
    os.path.join(HERE, "..", "..", "video-fetch", "scripts", "verify_media.py")
)

MANIFEST_NAME = "manifest.jsonl"
TERMINAL_OK = "done"
YOUTUBE_MAX_CONCURRENCY = 2

URL_RE = re.compile(r"https?://[^\s'\"<>]+")


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def manifest_path(out):
    return os.path.join(out, MANIFEST_NAME)


def load_manifest(out):
    p = manifest_path(out)
    if not os.path.exists(p):
        return []
    items = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def save_manifest(out, items):
    """Atomic rewrite -- a half-written manifest is worse than none."""
    p = manifest_path(out)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


_lock = threading.Lock()


def update_item(out, item_id, **fields):
    with _lock:
        items = load_manifest(out)
        for it in items:
            if it["id"] == item_id:
                it.update(fields)
                break
        save_manifest(out, items)


# --------------------------------------------------------------------------- #
# URL parsing
# --------------------------------------------------------------------------- #
def split_urls(text):
    """Recover URLs from a pasted dump.

    Handles the two shapes seen in real dumps: '==' separators, and two URLs
    glued with no separator at all
    (...viewkey=AAAhttps://rt.pornhub.com/...=BBB). Order preserved, exact
    duplicates dropped.

    The glued case is why a plain findall is not enough: the regex happily
    matches the whole run as ONE url, silently swallowing the second video.
    Inserting a newline before every scheme occurrence except the first
    splits them apart before matching.
    """
    text = text.replace("==", "\n")
    # Break glued URLs: "...AAAhttps://..." -> "...AAA\nhttps://..."
    text = re.sub(r"(?<!^)(?<![\s'\"<>(])(https?://)", r"\n\1", text)
    found = URL_RE.findall(text)
    out, seen = [], set()
    for u in found:
        u = u.rstrip(").,;'\"")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def guess_id_from_url(url):
    for pat in (r"viewkey=([A-Za-z0-9]+)", r"/video-(\d+_\d+)",
                r"video[-/]([A-Za-z0-9_-]{5,})", r"/([A-Za-z0-9_-]{6,})/?$"):
        m = re.search(pat, url)
        if m:
            return m.group(1)[:24]
    return None


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #
def verify_file(path):
    """Return (ok, detail). Delegates to verify_media.py (packet-walk based)."""
    if not os.path.exists(VERIFIER):
        return False, f"verifier missing at {VERIFIER}"
    if not os.path.exists(path):
        return False, "file does not exist"
    p = subprocess.run(
        [sys.executable, VERIFIER, "--json", path],
        capture_output=True, text=True,
    )
    try:
        results = json.loads(p.stdout)
    except json.JSONDecodeError:
        return False, f"verifier output unparseable (rc={p.returncode})"
    if not results:
        return False, "verifier returned nothing"
    r = results[0]
    ok = r.get("status") == "OK"
    detail = r.get("status", "?")
    if r.get("reasons"):
        detail += ": " + "; ".join(r["reasons"][:2])
    return ok, detail


def cleanup_partials(dest):
    """Remove .part and HLS fragment leftovers so a retry starts clean."""
    import glob as _glob
    removed = []
    for pat in (dest + ".part", dest + ".part-Frag*.part", dest + ".ytdl"):
        for f in _glob.glob(pat):
            try:
                os.remove(f)
                removed.append(os.path.basename(f))
            except OSError:
                pass
    return removed


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_init(a):
    os.makedirs(a.out, exist_ok=True)
    if a.urls_file:
        text = open(a.urls_file, encoding="utf-8", errors="replace").read()
    elif a.urls:
        text = "\n".join(a.urls)
    else:
        text = sys.stdin.read()

    urls = split_urls(text)
    if not urls:
        print("no URLs recovered from input", file=sys.stderr)
        return 2

    existing = load_manifest(a.out)
    known = {it["url"] for it in existing}
    start = len(existing)
    added = []
    for n, url in enumerate(u for u in urls if u not in known):
        item_id = f"{start + n + 1:02d}"
        tag = guess_id_from_url(url) or item_id
        added.append({
            "id": item_id, "url": url,
            "dest": f"{item_id}_{tag}.mp4",
            "status": "pending", "note": "",
        })
    save_manifest(a.out, existing + added)

    # This count is the number to state back to the user before downloading.
    print(f"recovered URLs      : {len(urls)}")
    print(f"already in manifest : {len(urls) - len(added)}")
    print(f"added               : {len(added)}")
    print(f"manifest            : {manifest_path(a.out)}")
    if added:
        print("\nfirst few:")
        for it in added[:5]:
            print(f"  {it['id']}  {it['url'][:78]}")
    return 0


def cmd_status(a):
    items = load_manifest(a.out)
    if not items:
        print(f"no manifest at {manifest_path(a.out)} -- run `init` first")
        return 2
    counts = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    print(f"manifest: {manifest_path(a.out)}  ({len(items)} items)")
    for k in ("pending", "running", "done", "failed", "skipped"):
        if counts.get(k):
            print(f"  {k:<8} {counts[k]}")
    stuck = [it for it in items if it["status"] == "running"]
    if stuck:
        print(f"\n{len(stuck)} item(s) left 'running' -- crash victims; "
              f"`run` will verify and requeue them")
    todo = [it for it in items if it["status"] in ("pending", "failed")]
    print(f"\nwould download: {len(todo)}")
    for it in todo[:10]:
        print(f"  {it['id']} [{it['status']}] {it['url'][:70]}")
    return 0


def download_one(a, item, results):
    out, iid, dest = a.out, item["id"], item["dest"]
    path = os.path.join(out, dest)
    log = os.path.join(out, f"dl{iid}.log")

    ok, _ = verify_file(path)
    if ok:  # idempotency: already complete
        update_item(out, iid, status="done", note="verified (pre-existing)")
        results[iid] = ("done", "already verified")
        return

    cleanup_partials(path)
    update_item(out, iid, status="running", note="")

    cmd = ["yt-dlp", "--no-progress", "-o", path]
    if a.ytdlp_args:
        cmd += a.ytdlp_args.split()
    cmd.append(item["url"])

    with open(log, "w", encoding="utf-8") as lf:
        rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT).returncode

    ok, detail = verify_file(path)
    if ok:
        update_item(out, iid, status="done", note="verified")
        results[iid] = ("done", detail)
    else:
        low = ""
        try:
            low = open(log, encoding="utf-8", errors="replace").read()[-2000:].lower()
        except OSError:
            pass
        if any(s in low for s in ("access restricted", "no video formats found",
                                  "video unavailable", "private video")):
            update_item(out, iid, status="skipped",
                        note="unreachable by design (auth/removed)")
            results[iid] = ("skipped", "auth wall or removed")
        else:
            update_item(out, iid, status="failed", note=f"rc={rc}; {detail}"[:200])
            results[iid] = ("failed", detail)


def cmd_run(a):
    items = load_manifest(a.out)
    if not items:
        print(f"no manifest at {manifest_path(a.out)} -- run `init` first")
        return 2

    # Requeue crash victims after verifying whatever they left behind.
    for it in items:
        if it["status"] == "running":
            ok, detail = verify_file(os.path.join(a.out, it["dest"]))
            new = "done" if ok else "pending"
            update_item(a.out, it["id"], status=new,
                        note="recovered after crash: " + detail[:120])
            print(f"  {it['id']}: was 'running' -> {new}")

    items = load_manifest(a.out)
    todo = [it for it in items if it["status"] in ("pending", "failed")]
    if not todo:
        print("nothing to do -- every item is done or skipped")
        return 0

    conc = max(1, a.concurrency)
    if any("youtube.com" in it["url"] or "youtu.be" in it["url"] for it in todo):
        if conc > YOUTUBE_MAX_CONCURRENCY:
            print(f"YouTube present -> capping concurrency at {YOUTUBE_MAX_CONCURRENCY}")
            conc = YOUTUBE_MAX_CONCURRENCY

    print(f"downloading {len(todo)} item(s), {conc} at a time")
    results, queue = {}, list(todo)
    active = []
    while queue or active:
        while queue and len(active) < conc:
            it = queue.pop(0)
            t = threading.Thread(target=download_one, args=(a, it, results),
                                 daemon=True)
            t.start()
            active.append((it, t))
            print(f"  -> {it['id']} started")
        time.sleep(1)
        for it, t in active[:]:
            if not t.is_alive():
                st, detail = results.get(it["id"], ("?", ""))
                print(f"  <- {it['id']} {st}: {detail[:70]}")
                active.remove((it, t))

    print()
    return cmd_verify(a)


def cmd_verify(a):
    items = load_manifest(a.out)
    if not items:
        print(f"no manifest at {manifest_path(a.out)}")
        return 2

    rows, bad = [], 0
    for it in items:
        path = os.path.join(a.out, it["dest"])
        if it["status"] == "skipped":
            rows.append((it["id"], it["dest"], "-", "-", "-", "skipped"))
            continue
        ok, detail = verify_file(path)
        size = res = dur = "-"
        if os.path.exists(path):
            p = subprocess.run([sys.executable, VERIFIER, "--json", path],
                               capture_output=True, text=True)
            try:
                r = json.loads(p.stdout)[0]
                size = f"{r.get('size_bytes', 0) / 1048576:.1f} MB"
                res = r.get("resolution", "?")
                d = r.get("duration_s")
                dur = f"{d:.0f}s" if isinstance(d, (int, float)) else "?"
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
        status = "OK" if ok else f"BAD ({detail[:40]})"
        if not ok:
            bad += 1
        rows.append((it["id"], it["dest"], size, res, dur, status))

    w = max((len(r[1]) for r in rows), default=10)
    w = min(w, 60)
    print(f"{'#':<4} {'file':<{w}} {'size':>11} {'res':>10} {'dur':>7}  status")
    for r in rows:
        print(f"{r[0]:<4} {r[1][:w]:<{w}} {r[2]:>11} {r[3]:>10} {r[4]:>7}  {r[5]}")

    counts = {}
    for it in load_manifest(a.out):
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    print()
    print("  ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    leftovers = [f for f in os.listdir(a.out)
                 if f.endswith(".part") or ".part-Frag" in f]
    if leftovers:
        print(f"\nWARNING: {len(leftovers)} unfinished artifact(s): {leftovers[:5]}")
    return 1 if (bad or counts.get("failed")) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--out", required=True,
                       help="output dir (Windows path, e.g. F:/_DOWNLOADS/batch)")

    p = sub.add_parser("init", help="parse a dump into a manifest")
    common(p)
    p.add_argument("--urls-file")
    p.add_argument("--urls", nargs="*")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="show manifest state; downloads nothing")
    common(p)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("run", help="download pending/failed items")
    common(p)
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--ytdlp-args", default="",
                   help="extra yt-dlp flags, e.g. '-N 8'")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("verify", help="re-verify every file and print the table")
    common(p)
    p.set_defaults(func=cmd_verify)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
