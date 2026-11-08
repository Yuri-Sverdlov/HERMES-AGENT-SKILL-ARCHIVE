# Session trace: reconciling two Hermes skill archives

Source of truth: `G:\_MY-PROGRAMMING_1\HERMES-AGENT\SOURCES-ARCHIVE` (Folder 1, 28 files) — known-good archive on local disk.
Second copy: `G:\_MY-PROGRAMMING_1\HERMES-AGENT\SOURCES-ARCHIVE скиллы компьютера 2` (Folder 2, 21 files) — downloaded from Google Drive.

## Initial mistake

I ran `stat --format="%Y"` on both directories and concluded Folder 1 was newer — every file had a later mtime. This was WRONG. The user corrected me: Folder 2 was downloaded from Google Drive, which resets mtime to download time. The timestamps were meaningless.

## Correct approach: content-hash comparison

```python
import os, hashlib
f1 = walk_rel("DIR1")
f2 = walk_rel("DIR2")
shared = sorted(set(f1) & set(f2))
diffs = []
for rel in shared:
    with open(f1[rel], 'rb') as a, open(f2[rel], 'rb') as b:
        if a.read() != b.read():
            diffs.append(rel)
```

Actually executed via bash:
```bash
python3 -c "
from hashlib import md5
import os
b1 = 'DIR1'; b2 = 'DIR2'
def walk(path):
    return {os.path.relpath(os.path.join(r,f), path): os.path.join(r,f)
            for r,_,fs in os.walk(path) for f in fs}
f1 = walk(b1); f2 = walk(b2)
shared = sorted(set(f1) & set(f2))
for rel in shared:
    with open(f1[rel],'rb') as a, open(f2[rel],'rb') as b:
        if a.read() != b.read():
            print(f'DIFF: {rel}')
# Also check unique files
print(f'Only in 1: {len(set(f1)-set(f2))}')
print(f'Only in 2: {len(set(f2)-set(f1))}')
"
```

## Results for this session

- **Shared files: 21** — 19 were identical. Only 2 differed: `README.md` and a WhatsApp chat file.
- **README.md**: Folder 1 version was more complete — listed all 6 skills incl. new additions. Folder 2 was outdated.
- **WhatsApp chat**: Diff was purely encoding/line-endings, content identical (1988 lines).
- **Only in Folder 1: 7 files** — included 3 entire skills not in Folder 2.
- **Only in Folder 2: 0 files** — Folder 2 was a strict subset.

## Arbitration result

Folder 1 won every conflict: it was more complete in every case where content differed, and had 7 unique files Folder 2 didn't. Copied Folder 1 → target.

## Second pass: reconcile archive vs current installed state

After building the merged archive, compared it against the live Hermes skills directory to ensure the archive reflected what was actually running on the computer:

- 7 of 10 skills were identical → kept as-is
- 3 skills (`computer-use`, `video-extraction`, `video-url-extractor`) had installed versions that were **newer/more complete** than the archive → overwrote with installed versions
- 4 scripts were all identical → no action

## Lessons learned

1. **Cloud-downloaded directories have meaningless timestamps** — ALWAYS hash-compare shared files, never stat-compare.
2. **Always run two passes:** source A vs source B (which is newer?), then merged result vs live installed state (is the archive up-to-date?).
3. **Content analysis beats metadata.** The archive's `video-extraction` SKILL.md had 9 fewer lines than the installed version — someone had regressed the archive by stripping multi-threading warnings and VK Video guidance. Content review caught this.