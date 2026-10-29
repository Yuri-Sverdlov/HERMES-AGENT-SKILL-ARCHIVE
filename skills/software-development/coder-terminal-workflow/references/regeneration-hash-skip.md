# Regeneration pipeline: hash-skip + pinned-block validation

A common pattern for compile/regenerate systems where LLM-generated content must coexist with user edits. Implemented for LLM-KNOWLEDGE-BASE in `compile.py` (TASK-008).

## Problem

Generated pages (from chat transcripts, DB records, or LLM summaries) need to be:
1. **Regenerated** when source data changes
2. **Preserved** when source data hasn't changed (skip to avoid churn)
3. **Protected** — user edits (`pinned` blocks) must survive regeneration without being silently overwritten

## Core pattern

```
                     ┌─────────────┐
                     │  Page .md   │
                     │  (on disk)  │
                     └──────┬──────┘
                            │ read
                            ▼
               ┌────────────────────────┐
               │  Extract frontmatter   │
               │  + pinned blocks       │
               └────────┬───────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
    ┌─────────────────┐  ┌───────────────┐
    │ Compute         │  │ Regenerate    │
    │ sources_hash    │  │ body via LLM  │
    │ (sha256 of      │  │ or placeholder│
    │  source bodies) │  └───────┬───────┘
    └────────┬────────┘          │
             │                   ▼
    ┌────────┴────────┐  ┌───────────────┐
    │ Compare with    │  │ Reinject      │
    │ stored hash     │  │ pinned blocks │
    └────────┬────────┘  └───────┬───────┘
             │ match             │
             ▼ skip              ▼
        ┌──────────┐    ┌──────────────────┐
        │ SKIP     │    │ Extract pinned   │
        │ file     │    │ from new body    │
        │ unchanged│    └────────┬─────────┘
        └──────────┘             │
                        ┌────────┴────────┐
                        ▼                 ▼
                  ┌────────────┐   ┌───────────────┐
                  │ Blocks     │   │ Blocks lost?  │
                  │ preserved  │   │ → ERROR       │
                  │ → write    │   │   file saved  │
                  └────────────┘   └───────────────┘
```

## Key components

### 1. Sources hash

Deterministic sha256 computed from source chat bodies:

```
Для каждого источника (sorted by session_id):
  source_ref + '\n' + sha256(body чата без frontmatter)
```

- Deterministic — same sources → same hash
- Changing one chat body → hash changes (triggers regeneration)
- Stored in page frontmatter as `sources_hash`

**Chat lookup by frontmatter, not filename.** Real chat files have names like `01_privetstvie.md` (slug-based, no id in name). The `session_id` lives in the YAML frontmatter (`session_id: "20260624_213530_2c5dd9"`). `_find_chat_file` must scan every `*.md` in the source dir, parse the frontmatter, and match on `session_id` — matching by filename stem is wrong for production data.

**Pitfall — TASK-010:** `_find_chat_file` originally searched by `session_id in f.stem` (filename-based). This worked for test fixtures whose names contained the id, but silently returned `None` for ALL real chats (id in frontmatter, not filename). The hash degraded to `sha256(empty)` — no error, just wrong. Fix: rewrite to iterate files, parse frontmatter, match `session_id` field.

**Text normalization for stable hashes (Windows).** Real chat files on Windows are CRLF. They also contain **lone `\r`** characters (not part of `\r\n` pairs). A naive `replace('\r\n', '\n')` leaves lone `\r` behind, which:
- Breaks frontmatter regex parsing (`^---\n` never matches a file starting with `---\r\n`)
- Breaks read→write→read idempotency: writing LF text back and re-reading gives different content because the first read normalizes CRLF→LF but leaves lone `\r`, then write preserves the lone `\r`, then second read... the text changes. Therefore hashes never stabilize (SKIP never fires, regeneration loops).

Fix — normalize EVERY `\r` to `\n`:
```python
text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
```
Order matters: CRLF first (else `\r\n` becomes `\n\n`), then lone `\r`.

### 2. Hash-skip

```
--all --changed:
  for each page:
    compute current sources_hash from page.sources
    if current_hash == page.sources_hash → SKIP
    else → regenerate
```

Pattern benefits:
- Idempotent — running twice in a row does nothing
- Efficient — only re-process pages whose source data actually changed
- Explicit — SKIP output proves the skip happened (no silent no-op)

### 3. Pinned-block validator

```
User edits guarded by <!-- pinned --> ... <!-- /pinned --> markers.

regenerate():
  1. Extract pinned blocks from old page (by content fingerprint)
  2. Generate new body (preserving pinned blocks via reinjection)
  3. Extract pinned blocks from new body
  4. lost = old_blocks - new_blocks
  5. if lost → ERROR: pinned block lost, file NOT overwritten
  6. else → write, status = 'pinned-mixed' (has pinned) or 'generated'
```

Critical safety property: **loss is detected before write**. If the LLM/pipeline drops a pinned block, the error fires and the file on disk stays intact.

#### Block key: sha256, not content prefix

Block identity is keyed by `hashlib.sha256(content)[:16]` (first 16 hex chars of content hash), **not** by `content[:40]` (first 40 raw characters). Rationale:

- `content[:40]` is fragile: whitespace normalization, trailing spaces, or character encoding differences between two runs produce different raw prefixes, causing false "block lost" errors.
- sha256 is deterministic on the exact content bytes — identical content always produces the same 16-char key.
- 16 hex chars (64 bits of hash) provide amply enough collision resistance for the number of blocks per page (typically 1-5).

#### Pinned-block anchor: `section="..."` attribute (solves drift)

**Problem (TASK-015):** The original `reinject_pinned` used a content-heuristic to place blocks under sections: `section[:20].lower() in content.lower()`. This nearly always failed — user notes rarely contain the section name as a substring. Blocks fell to the end of the body with a `WARNING: pinned block unplaced` on every regeneration, causing alert fatigue.

**Solution:** Add an explicit `section="SectionName"` attribute to the pinned marker:

```
<!-- pinned section="Сводка" -->
This is a note about Сводка. It always stays here.
<!-- /pinned -->
```

**Reinjection priority (new in TASK-015):**

| Priority | Condition | Action | Warning? |
|----------|-----------|--------|----------|
| 1 | `section="..."` attribute present **and** name is a valid section | Place block under `## {section}` | No |
| 2 | No `section` attribute (legacy) | Content-heuristic: `section[:20].lower() in content.lower()` | No if matched, Yes if not |
| 3 | `section="..."` but name is not in section list | Fallback to end of body | Yes (`WARNING: pinned block unplaced`) |

**Key design decisions:**

- **Regex change:** `PINNED_RE` extended to capture optional `section="..."`:
  ```python
  r'<!--\s*pinned\s*(?:section="([^"]+)")?\s*-->\n(.*?)\n<!--\s*/pinned\s*-->'
  ```
  group(1) = section name (or None), group(2) = block content.

- **Backward compatible:** Old-format blocks without `section=` continue to work via the legacy content heuristic. No existing pages need updating.

- **Ident ignores section attribute:** The block identity key (sha256 of content) is computed from content only, excluding the `section=` attribute. Changing the section name (e.g. moving a block from "Сводка" to "Хронология") does NOT change the block's identity — it's still the "same" block, just re-anchored.

- **Group index update trap:** When `PINNED_RE` gains a new group, all code that references `m.group(N)` must be rechecked. The content group shifted from `m.group(1)` to `m.group(2)`. Missing this renumbering causes silent extraction of the section name instead of the block content (TASK-015 caught this by selftest).

**Pitfall — regex group renumbering:** When adding an optional capture group to an existing regex, every reference to `m.group(N)` in the codebase must be verified. `PINNED_RE` gained `section="(name)"` as group(1), pushing content from group(1) to group(2). `extract_pinned_blocks` and `reinject_pinned` both needed updating. A search for `m.group(1)` in the affected file caught this before tests ran.

#### Anti-drift: unplaced pinned blocks generate WARNING

When `reinject_pinned` can't match a pinned block to any section (no `section=` attribute and content doesn't contain any section name), it falls back to appending the block to the end of the body. This is **not an error** (the block is preserved), but it **is a drift signal** — the block detached from its original context.

Every fallback emits:
```python
print(f"WARNING: pinned block unplaced: {ident}", file=sys.stderr)
```

This is treated as a warning (not ERROR): the page regenerates successfully, but the user is alerted that the block's context placement needs review.

**Note:** With the `section=` anchor, this warning should become rare — most blocks should have an explicit anchor. The warning still fires for legacy blocks without anchors that can't be matched by content heuristic.

### 4. Body generation (placeholder)

Template body with 4 fixed sections:
```
## Сводка
## Хронология решений
## Ключевые артефакты
## Открытые вопросы
```

Each section is a heading + placeholder (`TODO: LLM generation (TASK-009)`).
Pinned blocks are reinjected into their originating section (matched by keyword overlap or explicit anchor) or appended to body end.

### 5. Source resolution and warning pattern (non-silent failure)

When `sources_hash` is computed, each source reference (`pc1:hermes:session_id`) is resolved to a real file path. If resolution fails (chat file not found), the system must NOT silently skip — that would make the hash permanently incomplete and the page never regenerates when new sources appear.

**Rules:**

1. **`h.update(source_ref)` ALWAYS** — every source contributes to the hash, even if its file can't be found. This means two runs with the same sources list produce the same hash regardless of resolution success (deterministic), but the hash is INCOMPLETE (missing body content from unresolved sources).

2. **Unresolved source → WARNING** — `print(f"WARNING: source not found: {src}", file=sys.stderr)` for each failed resolution. Not `continue` without output. This makes silent hash degradation visible.

3. **`_compute_all_hashes` returns `(hash, warning_count)`** — a wrapper that accumulates warnings. The CLI (`cmd_all`, `cmd_page`) checks `warning_count > 0` and exits with code 1 after processing all pages. This flags the problem without crashing mid-run.

4. **Empty snippets are invalid** — `sha256(b"").hexdigest()` (`e3b0c442...`) must NEVER be the sources_hash of a real page. If a page has sources but none resolve, that's an error state, not a valid skip condition.

**Implementation template:**
```python
def _compute_all_hashes(sources, chats_dir):
    h = hashlib.sha256()
    warning_count = 0
    for src in sorted(sources):
        h.update((src + '\n').encode('utf-8'))  # ALWAYS
        chat_file = resolve(src, chats_dir)
        if chat_file is None:
            print(f"WARNING: source not found: {src}", file=sys.stderr)
            warning_count += 1
            continue
        body_hash = chat_body_hash(chat_file)
        h.update(body_hash.encode('utf-8'))
    return h.hexdigest(), warning_count
```

**Pitfall:** The first version of `compute_sources_hash` silently `continue`-ed on unresolved sources, with no WARNING. This meant a page with even one broken source reference would quietly compute a hash that could never change (only `source_ref +\n` contributed, no body content). The page would SKIP forever, never regenerating, and nobody would notice. Always emit WARNING on resolution failure.

## Implementation (compile.py)

See full source at `G:\_My_Programming\LLM-KNOWLEDGE-BASE\compile.py`.

Key functions:
| Function | Role |
|----------|------|
| `compute_sources_hash(sources, chats_dir)` | Deterministic sha256 over source bodies (+ WARNING on unresolved) |
| `_compute_all_hashes(sources, chats_dir)` | Wrapper returning `(hash, warning_count)` for CLI |
| `extract_pinned_blocks(body)` | Regex-based extraction of `<!-- pinned -->` regions (keyed by sha256[:16]) |
| `reinject_pinned(body, blocks)` | Reinsert pinned blocks into section (explicit anchor > content heuristic > fallback) |
| `regenerate(page_path, chats_dir)` | Full pipeline: hash-check → generate → validate → write |
| `cmd_all(chats_dir, changed_only)` | Batch mode with hash-skip and warning exit code |

## When to use this pattern

- Any system that **generates artifacts from source data** with possible later regeneration
- Any system that allows **user edits to survive regeneration** (pinned blocks, manual annotations)
- Any system with **many artifacts where only a subset changes** (hash-skip for efficiency)
- Any system where **pinned blocks need drift-resistant placement** (use `section=` anchor)

Not needed for: one-shot generation, fully-automated pipelines where user edits are forbidden, or projects with <5 artifacts.