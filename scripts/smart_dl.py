"""
Smart downloader — aria2c with resume (primary) or Python multi-thread with resume (fallback).

Usage:
    python smart_dl.py <URL> <DEST> [THREADS]
    python smart_dl.py "https://..." "C:\\out.mp4" 6

Default: 6 connections. Supports resume on interruption (Ctrl+C / crash).
"""
import os
import sys
import json
import time
import shutil
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen


# ── discovery ──────────────────────────────────────────────────────────
def _find_aria2c():
    """Find aria2c: hermes cache → PATH → None."""
    hermes_dir = os.path.expandvars(r"%USERPROFILE%\.hermes")
    candidates = [
        os.path.join(hermes_dir, "aria2c.exe"),
        shutil.which("aria2c"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


# ── aria2c path ────────────────────────────────────────────────────────
def _download_aria2c(url, dest, threads, state_path):
    """aria2c strategy: 6 conns, resume, verify checksum, progress."""
    aria2 = _find_aria2c()
    # Build command
    cmd = [
        aria2,
        url,
        "-o", os.path.basename(dest),
        "-d", os.path.dirname(dest) or ".",
        "-x", str(threads),             # max connections per server
        "-s", str(threads),             # max connections total
        "-c",                           # continue (resume)
        "--max-connection-per-server", str(threads),
        "--min-split-size", "1M",       # dynamic chunk splitting
        "--console-log-level", "notice",
        "--summary-interval", "5",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
    ]
    # If dest exists, aria2c -c will resume
    print(f"[aria2c] {aria2}")
    print(f"[aria2c] resuming: {os.path.exists(dest)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    # Cleanup state on success
    if os.path.exists(state_path):
        os.remove(state_path)


# ── Python fallback with resume ────────────────────────────────────────
def _get_file_size(url):
    """Get total size via Range request."""
    req = Request(url)
    req.add_header("Range", "bytes=0-0")
    with urlopen(req) as resp:
        cr = resp.headers.get("Content-Range", "")
        if not cr:
            raise RuntimeError(f"Server doesn't support Range (got {resp.status})")
        return int(cr.split("/")[-1])


def _get_final_url(url):
    """Follow redirects to the actual CDN URL."""
    req = Request(url, method="HEAD")
    with urlopen(req) as resp:
        return resp.url


def _load_state(state_path):
    """Load resume state or None."""
    if os.path.exists(state_path):
        with open(state_path) as f:
            return json.load(f)
    return None


def _save_state(state_path, state):
    """Atomic save."""
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    tmp = state_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, state_path)


def _download_chunk(chunk_id, start, end, url, dest, lock, progress, state, state_path):
    """Download byte range with resume. Writes to .partNN, tracks progress in state."""
    part_path = dest + f".part{chunk_id:02d}"
    cur_start = start + state["chunks"][str(chunk_id)]["done"]

    if cur_start >= end:
        with lock:
            progress[0] += (end - start)
        return chunk_id

    req = Request(url)
    req.add_header("Range", f"bytes={cur_start}-{end - 1}")

    with urlopen(req, timeout=60) as resp:
        with open(part_path, "ab") as f:   # ab = append for resume
            while True:
                data = resp.read(256 * 1024)
                if not data:
                    break
                f.write(data)
                n = len(data)
                with lock:
                    progress[0] += n
                state["chunks"][chunk_id]["done"] += n
        # Save state periodically (after each chunk completes)
        _save_state(state_path, state)

    return chunk_id


def _download_python(url, dest, threads, state_path):
    """Python multi-thread download with resume support."""
    print("[python] Checking server...")
    total = _get_file_size(url)
    print(f"[python] Total: {total:,} bytes ({total / 1024 / 1024:.1f} MB)")

    final_url = _get_final_url(url)

    state = _load_state(state_path)
    new_download = state is None or state.get("url") != url or state.get("total") != total

    if new_download:
        chunk_size = total // threads
        state = {
            "url": url,
            "total": total,
            "threads": threads,
            "chunks": {
                str(i): {
                    "start": i * chunk_size,
                    "end": (i + 1) * chunk_size if i < threads - 1 else total,
                    "done": 0,
                }
                for i in range(threads)
            },
        }
        _save_state(state_path, state)
        # Clean up old partials for fresh download
        for i in range(threads):
            p = dest + f".part{i:02d}"
            if os.path.exists(p):
                os.remove(p)
        print("[python] Fresh download")
    else:
        # Resume
        total_done = sum(c["done"] for c in state["chunks"].values())
        pct = total_done / total * 100
        print(f"[python] RESUMING at {pct:.1f}% ({total_done / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB)")
        # Verify part files exist
        for cid, cinfo in state["chunks"].items():
            if cinfo["done"] > 0:
                part = dest + f".part{int(cid):02d}"
                actual = os.path.getsize(part) if os.path.exists(part) else 0
                if actual != cinfo["done"]:
                    print(f"[python] WARNING: part{int(cid):02d} size mismatch ({actual} vs {cinfo['done']}), resetting")
                    cinfo["done"] = 0
                    if os.path.exists(part):
                        os.remove(part)

    # Print chunk status
    for cid, cinfo in state["chunks"].items():
        remain = cinfo["end"] - cinfo["start"] - cinfo["done"]
        pct_done = cinfo["done"] / max(cinfo["end"] - cinfo["start"], 1) * 100
        status = "DONE" if cinfo["done"] >= cinfo["end"] - cinfo["start"] else f"{pct_done:.0f}%"
        print(f"  Chunk {cid}: {cinfo['start']:,}-{cinfo['end']:,} ({remain:,} left) [{status}]")

    progress = [sum(c["done"] for c in state["chunks"].values())]
    lock = threading.Lock()
    start_time = time.time()

    def print_progress():
        while progress[0] < total:
            elapsed = time.time() - start_time
            if elapsed < 0.5:
                time.sleep(0.5)
                continue
            pct = progress[0] / total * 100
            speed = progress[0] / elapsed / 1024
            eta = (total - progress[0]) / (speed * 1024) if speed > 1 else 0
            sys.stdout.write(
                f"\r  {pct:5.1f}%  {progress[0] / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB  "
                f"{speed:.0f} KB/s  ETA {eta:.0f}s  "
            )
            sys.stdout.flush()
            time.sleep(0.5)

    printer = threading.Thread(target=print_progress, daemon=True)
    printer.start()

    # Only download unfinished chunks
    todo = []
    for cid, cinfo in state["chunks"].items():
        cur = cinfo["start"] + cinfo["done"]
        if cur < cinfo["end"]:
            todo.append((int(cid), cur, cinfo["end"]))

    with ThreadPoolExecutor(max_workers=min(threads, len(todo))) as executor:
        futures = {}
        for cid, start, end in todo:
            fut = executor.submit(
                _download_chunk, cid, start, end, final_url, dest,
                lock, progress, state, state_path
            )
            futures[fut] = cid

        for future in as_completed(futures):
            cid = future.result()
            print(f"\n  Chunk {cid} done")

    printer.join(timeout=0.5)
    elapsed = time.time() - start_time
    speed = total / elapsed / 1024 if elapsed > 0 else 0
    print(f"\r  100.0%  {total / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB  {speed:.0f} KB/s  Done!")

    # Reassemble
    print("[python] Reassembling...")
    with open(dest, "wb") as out:
        for i in range(threads):
            part_path = dest + f".part{i:02d}"
            if os.path.exists(part_path):
                with open(part_path, "rb") as f:
                    out.write(f.read())
                os.remove(part_path)

    os.remove(state_path)
    final_size = os.path.getsize(dest)
    print(f"DONE: {final_size:,} bytes ({final_size / 1024 / 1024:.1f} MB) in {elapsed:.0f}s ({speed:.0f} KB/s)")


# ── main ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print("Usage: python smart_dl.py <URL> <DEST> [THREADS]")
        print("  aria2c primary (if installed), Python fallback with resume")
        print("  Resume: just re-run the same command.")
        sys.exit(1)

    url = sys.argv[1]
    dest = os.path.abspath(sys.argv[2])
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    threads = max(2, min(threads, 32))

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    state_path = dest + ".dlstate.json"

    # ── Try aria2c ──
    aria2 = _find_aria2c()
    if aria2:
        print(f"[smart_dl] aria2c found → delegated ({threads} connections)")
        _download_aria2c(url, dest, threads, state_path)
    else:
        print(f"[smart_dl] aria2c not found → Python fallback ({threads} threads, resume OK)")
        try:
            _download_python(url, dest, threads, state_path)
        except KeyboardInterrupt:
            pct = 0
            if os.path.exists(state_path):
                try:
                    st = _load_state(state_path)
                    done = sum(c["done"] for c in st["chunks"].values())
                    pct = done / st["total"] * 100
                except:
                    pass
            print(f"\n\n[smart_dl] INTERRUPTED at {pct:.1f}% — re-run the same command to resume.")
            sys.exit(130)


if __name__ == "__main__":
    main()