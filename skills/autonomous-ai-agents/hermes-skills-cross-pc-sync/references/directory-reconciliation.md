# directory-reconciliation (перенесено из отдельного скилла)

> Перенесено directory-reconciliation → hermes-skills-cross-pc-sync. Бывший отдельный скилл, вычищенный curator'ом; содержание сохранено здесь целиком.

# Directory Reconciliation

Reconcile two nearly-identical directory trees into a single canonical output. This is NOT a file-level merge (diff+patch) but a **per-file "which copy is best"** arbitration — you pick the winning version of each file and copy it to a target.

## When to Use

- You have two source directories with overlapping content and need one canonical snapshot
- One or both copies may have passed through cloud sync (Google Drive, Dropbox, OneDrive), file copies, or downloads that **reset file timestamps** — making modification time unreliable
- You're preparing a transferable snapshot from a "source computer" to a "destination computer"
- You need to merge a partial/older archive with a more complete one

**Don't use for:** git merges, diff-patch workflows, one-off comparison of 2-3 files (just diff them), or when timestamps ARE reliable and one side is simply the newer copy.

## Workflow

### 1. Inventory both directories

List all files recursively from both sources using relative paths:

```bash
# Get all files from each directory, relative paths
find "DIR1" -type f | sed 's|^DIR1/||' | sort > /tmp/files1.txt
find "DIR2" -type f | sed 's|^DIR2/||' | sort > /tmp/files2.txt
```

Or use `search_files` for smaller sets.

### 2. Classify files into three groups

Compare the two lists:

- **Shared** — files present in both directories
- **Only in A** — unique to source A
- **Only in B** — unique to source B

### 3. Hash-compare shared files (CRITICAL STEP)

**Do NOT trust timestamps** when either copy may have passed through cloud sync. Cloud providers (Google Drive, Dropbox, OneDrive) reset file modification times on download. Compare content hashes instead:

```bash
# For each shared file, compare md5 hashes
sha1= for f in "${shared_files[@]}"; do
  if [ "$(md5sum "$dir1/$f" | cut -d' ' -f1)" != \
       "$(md5sum "$dir2/$f" | cut -d' ' -f1)" ]; then
    echo "DIFF: $f"
  fi
done
```

This gives you:
- **Identical** — any copy is correct
- **Different content** — you must decide which version to keep

### 4. Arbitrate content-different files

When files have different content but the same relative path, decide which to keep:

- Compare complete content (diff), not just metadata
- Look for signs of regression: content removed, sections stripped, warnings deleted
- The "more complete" version wins (more sections, more explicit steps, more warnings)
- If one side is a known "old archive" and the other is the "live installed" version, prefer the live version
- For data files (logs, chats, exports): prefer the larger file (more data) or the one with more recent dates in the file CONTENTS (not timestamps)

### 5. Merge into target directory

```bash
# 1. Copy everything from one source as the baseline
cp -rf "DIR1/." "TARGET/"

# 2. Overwrite with winning versions of content-different files
cp -f "WINNING_SOURCE/path/to/differing/file" "TARGET/path/to/differing/file"

# 3. Copy unique files from source B that aren't in A
cp -f "DIR2/path/to/only-in-B-file" "TARGET/path/to/only-in-B-file"
```

### 6. Verify

Final verification:

```bash
# Verify count matches expectations
find "$TARGET" -type f | wc -l

# For specific files, verify they match the winning copy
md5sum "$TARGET/path/to/file"
md5sum "$WINNING_SOURCE/path/to/file"  # should match
```

## Common Pitfalls

1. **Timestamps lie after cloud sync.** Google Drive, Dropbox, OneDrive — all reset mtime to download time. Never use `stat` dates to decide which copy is newer. Content hash comparison is the only reliable arbiter.

2. **File size is not a hash.** Two files with the same size but different content are still different. Always hash first, then diff the content-different files.

3. **Encoding differences.** Same content may hash differently due to line endings (LF vs CRLF). Normalize first or check diff output carefully.

4. **Symlinks vs copies.** If one source uses symlinks and the other has real copies, `stat` won't help. Follow symlinks before comparing.

5. **Excluded files.** Define scope clearly before starting — are you comparing only SKILL.md, or all files in each skill directory? The answer changes the copy strategy.

## Verification

- [ ] Both source directories inventoried (relative paths)
- [ ] Shared files identified: N total
- [ ] Content-hash comparison completed: identical vs different
- [ ] Content-different files arbitrated: which side wins per file
- [ ] Unique files from each side catalogued
- [ ] Target directory built: baseline copy + overrides + extras
- [ ] Final hash check: target files match their winning source
- [ ] File count matches expectations
