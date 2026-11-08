---
name: hermes-cross-pc-git-sync
description: "Sync the user's Hermes work-files (personal guides, project code, configs) between his two Windows PCs via a single private GitHub repo. Covers: making the repo private before first push, secret-scan-before-commit discipline, monorepo layout (projects/ + guides/), and the Windows symlink-vs-junction constraint for keeping files in their home location while git-tracking them. Reach for this whenever the user wants something to 'follow him' / 'sync' / 'be on both computers'."
version: 1.0.0
author: agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [hermes, git, github, sync, two-pc, windows, junction, symlink]
    related_skills: [personal-hermes-guide, hermes-profiles-and-sessions, github-repo-management]
---

# Cross-PC Hermes file sync via private GitHub repo

The user (Yuri) runs Hermes on **two Windows PCs** as his primary tool. Anything
that helps him work — personal guides, project code, configs — does NOT auto-sync
(memory, skills, and the guide files are all local-per-machine). His chosen
mechanism is a **single private GitHub repo** acting as a hub:
`https://github.com/Yuri-Sverdlov/HERMES-AGENT`.

Two content types live in it:
1. **Project folders with code** (e.g. the billing dashboard).
2. **Standalone files** not tied to a project — markdown guides etc.

Workflow: PC-1 `git push` → PC-2 `git pull`.

## Pre-flight (do these BEFORE the first push — order matters)

1. **Verify tooling, don't assume.** `git --version`, `gh --version`,
   `gh auth status` (confirm logged-in account + `repo`/`workflow` scopes),
   `git config --global user.name/user.email`. He's `Yuri-Sverdlov`,
   identity `Yuri Sverdlov / yurispp@gmail.com`.
2. **Check repo state**: `gh repo view <owner>/<repo> --json visibility,isEmpty,defaultBranchRef`.
   A brand-new GH repo is often `isEmpty:true` and may be **PUBLIC by default**.
3. **🔴 Make it PRIVATE before pushing anything.** His hub holds personal guides,
   configs, and `payments.json` (real spend history). One command:
   `gh repo edit <owner>/<repo> --visibility private --accept-visibility-change-consequences`
   then re-verify `visibility:PRIVATE`. If you can't, tell him to do it himself
   before any push.
4. **🔴 Secret-scan EVERY folder before committing it.** Never push blind. For the
   billing dashboard specifically: read `config.json`, `payments.json`, and
   `grep -niE 'sk-|api_key|secret|token|password' server.py`. Confirm code reads
   keys from env (not hardcoded). Check `find <dir> -iname '*.env' -o -iname '.env*'`.
   Ensure a `.gitignore` glues `.env`, `*.key`, `__pycache__/` — and decide with
   him whether `payments.json` should be ignored (it's personal financial data).

## Actual layout (set up 2026-06-26, A2 chosen — see below)

```
G:\_My_Programming\HERMES-AGENT\   ← git repo root, remote = Yuri-Sverdlov/HERMES-AGENT (PRIVATE)
├── guides/                        ← Guide-to-Hermes*.md (3 files, UTF-8 BOM)
├── projects/                      ← code projects live here
│   └── HERMES-BILLING-DASHBOARD/  ←   (moved here 2026-06-26 via git mv)
├── *.md                           ← misc deploy/quickstart notes
├── .gitignore                     ← .env, *.key, *.pem, secrets, __pycache__/
└── README.md                      ← incl. PC-2 setup + daily git cycle
```
Code projects go under `projects/`; standalone guides under `guides/`. Moving the
dashboard there required killing its running server first — see the locked-dir
section below.

## Keeping files in their home location while git-tracking them (Windows reality)

He wants his guides to stay reachable at their familiar `~/` path AND be inside
the repo. The naive answer is a symlink — but on **stock Windows that fails**:

- **File symlinks require Developer Mode (or admin).** Tested 2026-06-26:
  `mklink file link` → "You do not have sufficient privilege"; MSYS
  `MSYS=winsymlinks:nativestrict ln -s` → "Operation not permitted". Dev Mode was
  OFF. So a true file-level symlink that preserves the EXACT path
  `~/Guide-to-Hermes.md` needs the user to flip *Settings → Privacy & security →
  For developers → Developer Mode = On* on **each** PC.
- **Directory junctions need NO admin and work across drives.** Tested:
  `cmd //c "mklink /J <linkdir> <targetdir>"` succeeds without privilege, resolves
  C:→G: cross-drive, and **git sees the files inside the junction** (`git add`
  tracks them). The cost: the path gains a subfolder — you get
  `~/hermes-guides/Guide-to-Hermes.md`, not the bare `~/Guide-to-Hermes.md`.

**Two viable plans — A2 was CHOSEN and is now LIVE (2026-06-26):**
- **A1 — enable Developer Mode**: keeps the exact `~/Guide-to-Hermes.md` path, so
  `personal-hermes-guide` skill + memory need NO changes. Cost: a Windows toggle
  on both PCs; depends on that toggle staying on. (NOT chosen.)
- **A2 — directory junction (no toggles) ← DONE**: real files moved into
  `repo/guides/`, junction `~/hermes-guides` → `G:\_My_Programming\HERMES-AGENT\guides`
  created. Guide path is now `~/hermes-guides/Guide-to-Hermes.md`; the
  `personal-hermes-guide` skill and memory were updated to match. PC-2 still needs
  its own junction (the command is in README + scripts/make-guides-junction.sh).

See `references/billing-dashboard-secret-scan.md` for the concrete scan results
and `scripts/make-guides-junction.sh` for the PC-2 junction command.

## Moving a project folder into projects/ while its server is running (locked-dir)

When reorganizing the repo (e.g. `git mv HERMES-BILLING-DASHBOARD projects/...`),
the move can fail with `fatal: renaming ... failed: Permission denied` because a
**running process holds the folder**. The billing dashboard's `server.py` (port
8765) is the usual culprit, but so is the `start.bat` `pause` prompt's `cmd.exe`,
an open Explorer window, or an editor with the folder as its project root.

Diagnostic + fix sequence (do NOT kill python blindly — Hermes itself is a
python.exe and you must not kill it):
1. **Find listeners on the app's port, not all python:**
   `netstat -ano | grep ':8765' | grep LISTENING | awk '{print $NF}' | sort -u`.
   There are often SEVERAL orphaned copies from past `start.bat` runs.
2. **Kill ONLY those PIDs, guarded by an image-name check:**
   for each PID `tasklist //FI "PID eq $p" | grep -i python && taskkill //PID $p //F`.
   This guarantees you never kill a non-python (or you can additionally exclude
   the big-RAM python that is Hermes).
3. **Freeing the port is NOT enough.** The lock is frequently a *directory cwd
   handle*, not a file lock. Tell-tale: every individual file opens fine
   (`for f in dir/*; do (exec 3<>"$f") ...`) yet even an in-place
   `mv dir dir_x` fails — that means a process has the dir as its current
   directory, OR an Explorer window / editor is parked in it.
4. After port is free, a short **retry loop** sometimes wins (lock releases as
   the process finishes dying): `for i in 1..6; do mv ... && break; sleep 5; done`.
5. If the lock persists, the holder is almost always an **open Explorer window**
   on that folder, a leftover **cmd.exe at `pause`**, or an **editor** with it as
   project root — ask the user to close those (closing just the *terminal window*
   does NOT kill the detached server process; verify with netstat afterward).
6. Lock-proof fallback that needs no culprit hunt: **copy** the contents into the
   new `projects/<name>/`, then make git see it as a clean rename without touching
   the locked files on disk:
   `git rm -r --cached <oldpath>` (drops old path from index, leaves disk files),
   then `git add projects/<name>` — git reports `R old -> new` (history follows),
   commit + push. **The repo is now fully correct and synced even though the old
   locked folder still sits on disk as untracked (`?? oldpath/`)** — git ignores
   it, it does not affect sync or the other PC. Stop fighting the lock; just tell
   the user the leftover empty folder will clear on its next reboot (or after they
   close the holding app), and that they must now launch the app from the NEW path.
7. A lock can narrow to ONE file (e.g. `index.html` held by an open **browser tab**
   viewing the dashboard) — `for f in dir/*; do (exec 3<>"$f")...; done` pinpoints
   which file is still held. A browser tab is a common, easy-to-miss holder.

Use `git mv` (not plain `mv`) so history follows the folder. `start.bat` using
`cd /d "%~dp0"` is path-relative, so the move does NOT break launching — but grep
for hardcoded absolute paths in `*.py`/`*.bat`/`*.md` before/after and fix README.

## Pitfalls

- The repo defaulting to PUBLIC + a future accidental `.env` commit = instant key
  leak. Private repo is the safety net; the root `.gitignore` is the lock.
- `payments.json` holds real spend figures — treat as personal even in a private repo.
- Don't feed bash `/g/...` paths to file tools on Windows (spurious `g` segment) —
  use native `G:/...`. (Same gotcha documented in `personal-hermes-guide`.)
- Whichever plan: the symlink/junction must be recreated on EACH PC — it is NOT
  carried by git. Give the user the exact command for the second machine.
- If A2 chosen and guides move, re-point BOTH the `personal-hermes-guide` skill
  paths AND the memory entry that names `~/Guide-to-Hermes.md`.
