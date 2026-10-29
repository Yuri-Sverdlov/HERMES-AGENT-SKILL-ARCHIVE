---
name: robocopy-migration
description: "Migrate folders between disks via robocopy: copy, verify file counts, scan and patch hardcoded paths."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [robocopy, migration, windows, paths, disk, backup]
    related_skills: [overview-projects-on-computer]
---

# Robocopy Migration

Migrate folders between Windows disks using robocopy with verification, path scanning, and batch path rewriting.

Created 2026-08-25 in session MIGRATION-G-F (PC2): 5 batches, >700 GB, >250k files (G: -> F:).

## When to Use

- User says: migrate folder to another disk, robocopy copy, fix paths after move.
- After DEV-NOTES disk rebuild (G: WORK vs H: ARCHIVE) — patch configs in migrated trees.

## Workflow

### 1. Copy — robocopy

```powershell
robocopy "SRC" "DST" /E /COPY:DAT /R:1 /W:1
```

- Exit code 0-7 = success (0 = nothing to copy, 1+ = copied)
- Exit code 8+ = error, stop
- Large folders (+1 GB): add `/MT:16`, run in background with long timeout
- If DST exists — robocopy is idempotent (updates in place)

### 2. Verify — file count src = dst

```powershell
$src = (Get-ChildItem "SRC" -Recurse -File).Count
$dst = (Get-ChildItem "DST" -Recurse -File).Count
"SRC -> src=$src dst=$dst match=$($src -eq $dst)"
```

Do not count migration complete without match=True. On mismatch — re-run robocopy.

### 3. Scan — find hardcoded source-disk paths

Write a **temporary `.ps1` file**, not inline `pwsh -Command` — nested quotes break.

Text extensions filter:
```powershell
$_.Extension -match '\.(py|ps1|bat|json|env|md|txt|yml|yaml|cfg|ini)$'
```

Search: `Select-String -SimpleMatch -Quiet`, dedupe: `Sort-Object -Unique`.

### 4. Patch — single files

For one file — `patch(mode='replace')`:
```
G:\AI\OLD_FOLDER\... -> F:\NEW_FOLDER\...
```

**Rule:** do not change paths to folders not yet migrated.

### 5. Mass replace (200+ files) — use Python

See `references/batch-path-rewriter.md`. Do not use PowerShell one-liners or subagents for large scans.

### 5a. Special case: install_path.txt

```powershell
Get-ChildItem $root -Recurse -Filter 'install_path.txt'
```

### 5b. ComfyUI config cascade

Copy order matters: SHARED -> PORTABLE -> COMFY_UI.

| File | What to patch |
|------|---------------|
| `COMFYUI-SHARED/tools/comfy_shared/config.py` | SHARED_ROOT, WORKING_COMFYUI, SCAN_ROOTS |
| `COMFYUI-SHARED/extra_model_paths.yaml` | base_path (slashes: G:/AI/... -> F:/...) |
| `COMFYUI_PORTABLE/ComfyUI/extra_model_paths.yaml` | Any G:/AI/COMFYUI-SHARED refs |
| `COMFY_UI/extra_models_config.yaml` | Legacy COMFY_UI path regex replace |

### 6. Dual-path pitfall

Same folder name may exist at disk root AND nested inside another migrated tree. Replace **specific to general** (nested path first, then root).

### 7. Control scan

After mass replace — narrow scan on operational files (.bat, .ps1, .py, .yaml, .yml, .env). Expect **0 hits** on stale paths.

### 8. Historical README lines

Lines like `- **From:** G:\AI\...` in migration history — do not patch (not live paths).

## Pitfalls

- `$_Extension` vs `$_.Extension` — typo breaks scans; prefer Python for multi-folder work
- Case-sensitive replace: `g:\AI` vs `G:\AI` — verify after patch
- `Format-Table` may be blocked by rm-rf hook — use `Out-String`
- Large files (22 GB): robocopy needs timeout=600+ or background
- Max 2 parallel robocopy with /MT:16 — disk saturation
- Never delete originals via agent (`rm -rf` blocked) — Explorer only
- Do not migrate `.venv` — recreate on target PC
- Dedupe scan results: `Sort-Object -Unique`

## REPORT structure

1. Copy results (exit codes)
2. Verification table (src/dst/match)
3. Path scan results
4. Special cases
5. Final verdict

Empty stdout + exit 0 is NOT proof of success.
