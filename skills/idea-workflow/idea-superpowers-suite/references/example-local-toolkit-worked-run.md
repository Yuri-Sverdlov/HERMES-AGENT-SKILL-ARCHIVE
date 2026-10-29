# Worked run: Full-mode plan → reusable local toolkit (ComfyUI model organization)

A real end-to-end Full-mode pass that demonstrates the workflow's stronger patterns.
Use as a reference for local-infra / data-organization projects where a **reusable
tool** (not a one-off script) is the deliverable, and where the agent has direct
access to inspect the target system.

## Shape of the project

- Goal: organize ~200 GB of scattered ComfyUI model files into one shared "engine"
  folder, laid out **by architecture**, with a dual manifest and a Python toolkit.
- Inputs: two printed LLM chats (prior planning done by a sandboxed model that could
  NOT see the disk) + direct disk access this session.

## What made this run good (transferable lessons)

1. **Inventory-first.** Before writing `01-design-doc.md`, scanned the real disk:
   111 files → 73 real models after excluding `.git/`, `site-packages/`,
   `custom_nodes/`, `__pycache__/`. Hashed only same-size candidates with SHA256.
   Result: 64.8 GB of *verified* duplicates, and one trap — two different files
   sharing the name `fluxunchained-dev-q4-0.gguf` (different hash). Name-based dedup
   would have deleted a unique file. **Lesson: dedup/identity decisions must key on
   content hash, never name+size alone.**

2. **Two-pass hashing under a full disk.** Disk was at 99%. Plan used `Move` within
   the same drive (instant, no extra space) and `copy→verify-hash→delete` only when
   crossing to another drive (idempotent, survives interruption). Never "copy
   everything into the new tree then clean up" when free space is tight.

3. **Interview answers became a decisions table** in the design doc (root paths,
   manifest format, archive location, dedup rule, priority). One row per resolved
   question — a fresh agent reads the table instead of re-interviewing.

4. **Manifest as future agent schema.** Chose BOTH formats: `models.yaml` as
   machine-readable source of truth + auto-generated `MODELS.md` for humans. The
   yaml is explicitly the data schema a later "hunter" agent will append to; manual
   fields (source/notes/clip_type) are preserved across regeneration by keying on
   sha256.

5. **Reusable toolkit, not scripts.** When the user wants repeatability + a
   foundation for a future automation agent, the implementation spec should define a
   small package with subcommands (here: `inventory / dedupe / migrate / manifest /
   validate`), each destructive op defaulting to `--dry-run` with an explicit
   `--apply` + y/N confirm, and every deletion/move logged to a report file.

## Package layout produced (Full mode, UI stage skipped)

```
<project>/_planning/ideas/<slug>/
  README.md
  01-design-doc.md
  02-implementation-spec.md
  03-agent-build-handoff.md
  04-spec-review.md
  appendix-inventory-full.md      # real scan table (size/type/location/sha256)
  appendix-dedup-plan.md          # per-group keep/delete decision
```

Note: `_planning/` lived inside the project's own shared folder so the spec ships
with the thing it describes.

## Spec-review verdict pattern

Ended at **PASS WITH CHANGES**: the toolkit was buildable immediately, but three
data-specific decisions ("which of the two same-named files is current?", "is the
9 GB fp16 variant still used?", "unknown-architecture files need manual attribution")
were listed as *must-resolve-during-migration*, not blockers to writing code. Good
model for separating "spec is ready" from "every data question is answered."

## Handoff nuance for local/interactive destructive work

The build handoff recommended: build the toolkit via the coding-agent path, but run
the actual destructive migration **interactively with the user**, confirming each
`--apply`. Autonomous end-to-end runs are inappropriate when 200 GB of the user's
files are on the line.

## Executing the migration (continued run — the "do it here" path)

The user chose to finish Project 1 in-session with the toolkit rather than in an
external IDE. Sequence that worked, each destructive step behind its own confirm:
`dedupe --dry-run` → confirm → `--apply` (freed 64.9 GB) → resolve the 3 data
questions → `migrate --dry-run` → confirm → `--apply` (65 files, instant Move within
drive) → `migrate --archive --apply` (SD1.5 + unused fp16 to a second drive via
copy-verify-delete) → `manifest sync` → connect via `extra_model_paths.yaml`.

### Fix the tool, never hand-patch its output

The first real `inventory` mislabeled things two ways: (a) it swept in non-models
(`.git/cursor/*.bin`, `site-packages/`, `custom_nodes/`, `__pycache__/`), and
(b) it left utility files (`upscale`, SAM, YOLO, `taesd*` preview-VAE) and
path-only-typed LoRA as `unknown`. The correct response was to extend the
classifier — exclusion path-parts, a "utility → shared architecture" rule,
architecture-by-parent-folder for LoRA, and a small explicit `MANUAL_ATTRIBUTION`
map for the handful of genuinely ambiguous files — then re-run. Do NOT hand-edit
the generated manifest to paper over classifier gaps: the manifest is regenerated,
so the fix has to live in the tool. Result: `unknown` went 51 → 0, and the rules
are reusable next time a model is added.

### Verify against the LIVE system, not the tool's self-report

"migrate reported OK: 65, errors: 0" is the tool's word. Independent confirmation:
started the actual app (ComfyUI) on a spare port and queried its `/object_info`
API — the models appeared in the loader dropdowns with their architecture-prefixed
paths (`sdxl\\...`, `flux2\\...`). Only then was the reorg declared done. General
rule for any "did the reorganization actually work" step: probe the consuming
system directly (its API, a fresh process, a re-scan) rather than trusting the
mutating tool's own success message. A DB-lock warning on startup was a red herring
— a second instance of the app was already running; the spare-port server still
came up and answered.

### Collision-safe placement for same-name/different-hash files

The two different `fluxunchained-dev-q4-0.gguf` files were both kept (user's call).
The migrator detects a target-path collision with a *different* sha256 and appends a
short hash suffix (`..._bf775167.gguf`) so neither overwrites the other. Keep this
guard in any move/migrate tool — same-name collisions with different content are
real, not hypothetical.
