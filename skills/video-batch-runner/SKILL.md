---
name: video-batch-runner
description: Drive a list of N videos with manifest, resume, verify.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [batch, playlist, manifest, resume, idempotent, video, parallel]
    related_skills: [video-source-resolve, video-fetch]
---

# Video Batch Runner

**Stage 3 of 3.** Take a list of N video links from start to finish and be able
to **prove** it finished. Resolving links is `video-source-resolve`; per-host
commands and throttle diagnosis are `video-fetch`.

## When to Use

- The user pastes a list of 3+ video URLs, or says "скачай плейлист" / "download all these"
- A playlist page, or a link dump from Telegram/notes
- Any batch that **may outlive the session** — even 2 items
- Resuming a batch that was interrupted

**For a single URL**, use `video-fetch` directly; a manifest is overhead there.

## The rule

**A batch is not "N background processes". A batch is a manifest plus a loop
that can be re-run safely at any time.**

Re-running the exact same command must: skip what is already verified, retry
what failed, and never point two processes at one destination.

This exists because of a real loss: a 40-film batch was launched as bare
background `yt-dlp` processes with no state file. The session ended, the
processes died, and what remained was a directory of files of unknown integrity
— including a 45 MB stub — triaged afterwards by **guessing at file sizes**.
The failure was the missing manifest, not the downloader.

## Manifest

One JSON-lines file next to the output dir, one record per source URL:

```
{"id":"01","url":"https://...","dest":"01_title.mp4","status":"done","note":""}
{"id":"02","url":"https://...","dest":"02_title.mp4","status":"failed","note":"403 after 3 tries"}
{"id":"03","url":"https://...","dest":"03_title.mp4","status":"pending","note":""}
```

`status` ∈ `pending` | `running` | `done` | `failed` | `skipped`

- **`id` is assigned once**, at parse time, and never reused. It is the stable
  key and supplies both the log name (`dl<id>.log`) and the filename prefix,
  which preserves list order.
- **`url` is the page URL, never a signed CDN URL.** Signed URLs are time-boxed
  and IP-bound; resolution happens at download time, not at parse time.
- **`done` is written only after the verifier passes** — never on process exit
  code alone. A `yt-dlp` exit 0 with a truncated tail is exactly the case that
  burned us.
- **`skipped`** is for unreachable-by-design items (private/age-gated VK,
  deleted Yandex previews). Do not retry these; the error will not change
  without auth.

## Runner script

`scripts/batch_dl.py` implements this entire runbook — manifest, resume,
idempotency, verification, concurrency caps:

```bash
B="C:/Users/Yuri/AppData/Local/hermes/skills/media/video-batch-runner/scripts/batch_dl.py"

python "$B" init   --out F:/_DOWNLOADS/batch --urls-file dump.txt   # parse once
python "$B" status --out F:/_DOWNLOADS/batch                        # dry run
python "$B" run    --out F:/_DOWNLOADS/batch --concurrency 3        # idempotent
python "$B" verify --out F:/_DOWNLOADS/batch                        # final table
```

`init` prints **`recovered URLs: N`** — that is the count to state back to the
user before downloading. Pass host flags through with `--ytdlp-args "-N 8"`
(see `video-fetch`); YouTube is auto-capped at 2 concurrent regardless of
`--concurrency`.

Verified behaviour on this box:

| Test | Result |
|---|---|
| Glued dump (`…=AAAhttps://…=BBB`) + `==` separators | 4/4 URLs recovered, none swallowed |
| Re-running `init` on the same dump | `added: 0` — idempotent |
| Crash recovery (3 items left `running`) | intact → `done` (no re-download), truncated + missing → requeued |
| Truncated file claiming full duration | caught: `byte stream ends early … partial file` |
| 10 real downloads | 10/10 `OK`, no false positives |

Re-run `run` as often as you like: `done` items are skipped, `failed` are
retried, and items left `running` by a dead session are verified and requeued.

## Runbook (what the script does, for manual use)

**1. Parse the dump once.** Split on `==` and on embedded `https://`/`http://`
boundaries — link dumps routinely glue two URLs together with no separator:

```
…viewkey=6774e86e0f666https://rt.pornhub.com/view_video.php?viewkey=6a2fd68f165ac
```

**State the recovered count back to the user before starting.** Never feed a
mangled string to yt-dlp, and never silently drop the tail. After this step the
manifest is the source of truth — do not re-parse.

**2. Create the output dir once** and reuse it across batches
(`F:\_DOWNLOADS\<name>` on this box).

**3. Launch only `pending`/`failed` items**, 3–4 concurrently, each in its own
`terminal(background=true, notify_on_complete=true)` with a unique destination
and its own log:

```bash
yt-dlp <host flags from video-fetch> -o "$OUT/<dest>" "<page-url>" > "$OUT/dl<id>.log" 2>&1
```

Mark an item `running` **before** launch, so a crashed session leaves a trail.
Do **not** chain with `&&` — that runs sequentially. Log numbering continues
across batches in the same dir, so don't reuse names.

**Concurrency:** 3–4 generally; **2 max against YouTube** (it rate-limits hard
and will kill the whole fan-out).

**4. Poll in one loop**, not one process handle at a time:

```bash
for i in 01 02 03; do tail -2 "$OUT/dl$i.log"; done
ls -la "$OUT"/*.part
```

`process(action='wait')` is clamped to ~60–180 s and returns "still running"
without telling you anything the log doesn't. With `--no-progress` the log
carries no speed info — stat the `.part` twice ~30–60 s apart and diff sizes.

**5. Verify, then mark.** On each completion run the verifier and set
`done`/`failed` from **its** verdict:

```bash
python "C:/Users/Yuri/AppData/Local/hermes/skills/media/video-fetch/scripts/verify_media.py" "$OUT/<dest>"
```

Completion notifications arrive as separate turns after the fact. Acknowledge
each in one line; do **not** re-print the whole table each time one lands.

**6. Final report** built from verifier output:

| # | File | Size | Resolution | Duration | Status |
|---|---|---|---|---|---|

Then, separately, `failed` and `skipped` items with their reasons. Clean up
`dl*.log` when everything is accounted for.

## Non-negotiables

1. **Unique destination per item.** Two processes on one `.part` produce
   `WinError 32` (file locked) on rename. Never relaunch an item that is
   `running` — check the manifest, not the directory listing.
2. **Verify before `done`.** Presence ≠ completeness. Size ≠ completeness.
3. **Never judge integrity by a size threshold.** "<100 MB = truncated" ships
   false verdicts both ways: it condemns a legitimately short clip (a real
   58.8 MB / 600 s file verifies clean on this box) and passes a truncated
   500 MB file. The verifier's packet walk is the real test — a file cut to a
   third keeps its original header, so container duration still reads full and a
   tail-seek check **exits 0 and passes**.
4. **Report measured values.** Give the user ffprobe's resolution and duration,
   not the quality you hoped yt-dlp picked.
5. **Before killing a slow item, diagnose it.** Stat the `.part` twice 30–60 s
   apart. If it is growing it is throttled, not stalled — read the signed URL's
   `rate=`/`burst=` params (see `video-fetch`) instead of discarding progress.
6. **Clean HLS restarts.** A killed HLS download leaves
   `*.mp4.part-Frag<N>.part` beside the `.part`. Remove both for a clean retry;
   a clean run beats resuming fragmented HLS.
7. **Background-first, always.** Even a single throttled item eats the 300 s
   foreground timeout and dies, taking yt-dlp with it.

## Resuming an interrupted batch

1. Read the manifest. Items left `running` are the crash victims.
2. For each, run the verifier on its destination:
   - passes → mark `done` (the process finished before the session died)
   - fails → delete the partial + `.part-Frag*` artifacts, mark `pending`
3. Re-run the loop. `done` items are skipped automatically.

**If no manifest exists** (a batch predating this skill), reconstruct what you
can: run the verifier over the whole output dir, treat passes as `done`, and ask
the user for the original list to recover the missing items. Do **not** guess
completeness from file sizes.

## Pitfalls

1. **No manifest.** The original sin — see the 40-film loss above.
2. **Signed URL in the manifest.** Tokens expire in minutes and bind to an IP.
   Store page URLs; resolve at download time.
3. **Re-parsing the dump on resume.** IDs shift and destinations collide. Parse
   once; the manifest is authoritative afterwards.
4. **Marking `done` on exit code.** yt-dlp can exit 0 on a truncated tail.
5. **Chaining with `&&`.** Sequential, not parallel.
6. **4+ parallel jobs against YouTube.** Rate limiting kills them all. Cap at 2.
7. **Silently dropping the tail of a glued URL list.** Always state the
   recovered count first.
8. **MSYS paths as script arguments.** `/f/_DOWNLOADS/...` is invisible to
   Python (`file does not exist`). Use `F:/_DOWNLOADS/...` for script args, even
   though MSYS paths work in the shell itself.

## Verification

- [ ] Recovered URL count stated to the user before any download started
- [ ] Manifest exists, one record per input URL, unique `id` and `dest`
- [ ] Every item ends in a terminal state (`done`/`failed`/`skipped`) — none left `running`
- [ ] Every `done` backed by a passing `verify_media.py` run
- [ ] Re-running the command is a no-op for `done` items (idempotency proven)
- [ ] No `.part` / `.part-Frag*.part` leftovers in the output dir
- [ ] Final table reports measured size/resolution/duration, with failed+skipped listed separately
