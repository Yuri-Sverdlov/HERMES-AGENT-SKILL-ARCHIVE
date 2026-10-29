# Installing Hermes skills from SOURCES-ARCHIVE (TASK-007 recipe, 2026-08-26)

When a task asks to install skills exported from another PC (the
`SOURCES-ARCHIVE/` folder in the HERMES-AGENT repo), the canonical flow is:

## 1. Copy map (skill -> category folder)

Source: `SOURCES-ARCHIVE\skills\<skill>\` -> target `%LOCALAPPDATA%\hermes\skills\<category>\<skill>\`

| Skill | Category |
|---|---|
| playlist-downloader, video-url-extractor, video-extraction, multithread-downloader | media |
| screenshot-to-docx, whatsapp-yt-links, overview-projects-on-computer | productivity |
| robocopy-migration | software-development |

Copy **recursively** with all inner content (`references/`, `scripts/`).

- `robocopy-migration` is NOT listed in `SOURCES-ARCHIVE\README.md` — only in
  `robocopy-migration-skill.md`. Copy from `skills\robocopy-migration\`, never
  from the root `.md` draft.

## 2. Scripts

`SOURCES-ARCHIVE\scripts\smart_dl.py`, `aria2c.exe`, `create_docx_template.py`
-> `~/.hermes\` (NOT the skills dir).

## 3. Verification (run, don't read)

1. `hermes skills list` — new skills show as `local` / `enabled`.
2. Every target dir has `SKILL.md`.
3. BOM check — SKILL.md must be **BOM-less** (yaml front matter). First 3 bytes
   must be `2d 2d 2d` (`---`), not `ef bb bf`:
   ```bash
   b1=$(xxd -p -l1 f); b2=$(xxd -p -s1 -l1 f); b3=$(xxd -p -s2 -l1 f)
   [ "$b1$b2$b3" = "efbbbf" ] && echo "BOM! $f" || echo "OK $f"
   ```
4. `pip install -r SOURCES-ARCHIVE\requirements.txt` (python-docx, pillow,
   pytesseract, yt-dlp).
5. If a skill embeds a path-meta json (e.g. overview-projects `projects.json`),
   update only the `meta` field per the task (`top_folder` for the new PC);
   entries stay stale until a full rescan task.

## Pitfalls

- **`hermes skills list` truncates long names with `…`** — rows render as
  `multithread-download…`, `overview-projects-on…`. `grep` by the full name
  MISSES these rows (first grep showed 6-7 hits, all 8 were actually installed).
  Grep by category instead (`hermes skills list | grep -i media`), then confirm
  via file presence on disk. File presence is the ground truth, not the list.
- **Never overwrite a builtin skill.** If the target skill already exists as
  `builtin` (e.g. `computer-use` in skills root) and the archive copy differs
  (compare byte size + mtime), do NOT replace it — copy the archive SKILL.md to
  a backup name like `autonomous-ai-agents\computer-use-pc2\` and note in REPORT.
- **python vs pip interpreter mismatch on Yuri's PC:** `python --version` may
  report 3.11.9 while `pip` targets `Python310\site-packages` — packages read as
  "already satisfied" in 3.10. Note the discrepancy in REPORT; verify which
  interpreter actually runs the script before trusting the deps.
- **Tesseract OCR (rus) and cua-driver are per-PC optional installs** (for
  screenshot-to-docx and computer-use) — they are trailing items in REPORT, not
  blockers of the skill install.
- After install, the user must `/new` the Hermes chat to pick up new skills.