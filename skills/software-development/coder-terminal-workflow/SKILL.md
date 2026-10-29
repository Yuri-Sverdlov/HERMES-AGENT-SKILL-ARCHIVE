---
name: coder-terminal-workflow
description: >
  Operating rules for Yuri's two-agent architecture: user (manager) directs
  architect (chat, e.g. DeepSeek V4 Pro) and coder (terminal, me). Covers the
  canonical file chain, REPORT discipline, BOM requirement, git rules, and
  role boundaries. Applies to ALL projects (POST-MAIL-AUTOMATION, Immergo, etc.)
  unless overridden by a project-specific skill.
---

# Coder Terminal Workflow

You are the **terminal agent (coder)** in a three-role system:

| Role | Who | Where | Does |
|------|-----|-------|------|
| **User (manager)** | Yuri | gives instructions directly | Manages both agents, decides what to work on |
| **Architect** | DeepSeek V4 Pro (or other chat model) | chat (Cursor/Kilo) | Writes TASK.md, reviews REPORT.md, updates PROJECT_LOG.md |
| **Coder (you)** | Hermes Agent in terminal | terminal | Executes TASK.md, fills REPORT.md, writes code |

The user speaks to you directly in the terminal. They may relay architect-created tasks or give their own. Always follow their instruction.

## Canonical startup sequence

When starting a new session on a project, read in this exact order:

0. **Load relevant skills** — scan the available skills list. If any skill matches or is even partially relevant to the task, load it with `skill_view(name)` and follow its instructions.
   - Always load `user-style-yuri` (communication calibration) and this skill (`coder-terminal-workflow`) at the start of every session with Yuri.
   - Load domain skills (github-*, home-accounting, etc.) based on the task.
1. `CONTEXT.md` — project memory: stack, roles, current focus
2. `AGENTS.md` — project-specific operating rules
3. `tasks/TASK.md` — the single active task (execute it)
4. **Execute the task** — write code, test, validate
5. Write results to `tasks/REPORT.md`

## REPORT.md discipline

- Format: what was done, what was checked, what didn't work
- One report per task, overwrites the previous — **except continuation tasks.** When the
  architect re-issues the SAME task as a «продолжение» (TASK.md says so explicitly, e.g.
  «Дописать в `tasks/REPORT.md`, не затирая блок про падение A»), **append a new titled
  section and leave the earlier blocks intact.** The old block is evidence for the reviewer,
  not scratch paper. Real case: VIDEO-TRANSLATE-BATCH TASK-003 kept the full run-A failure
  analysis and appended a separate `# ПРОДОЛЖЕНИЕ …` section (476 lines total).
- Encoding: match the project's existing canon files — read the BOM section below first.
- **Read the file with `read_file` right before overwriting it.** When the architect swaps in a
  fresh `tasks/REPORT.md` template between turns, `write_file` refuses with `stale_write_blocked`
  if the current contents were only seen through terminal `cat` — that does not count as a read by
  this task. One `read_file` call, then write.
- After writing, verify with `head -c 3 <file> | od -An -tx1` and compare against the
  neighbouring canon files (not against a fixed expectation).

### Collect EVERY question and request for the architect in ONE dedicated section (user-mandated 2026-09-12)

Yuri: *«Включил ли ты сюда все вопросы и пожелания для архитектора? Если нет, то сделай это,
чтобы я не дополнял его другими абзацами.»* The report must be self-contained for the
reviewer. Scattering your asks across the body is a defect, even when every fact is present.

- End every REPORT.md with a numbered section **`## Вопросы и пожелания архитектору`**,
  grouped: (1) требует решения — правки канона/задания, (2) открытые риски и факты для
  канона, (3) вопросы.
- Everything you would otherwise say to the user in chat goes in that block.
- **Report defects in the architect's own artifacts explicitly and do NOT silently fix them.**
  Real items from VIDEO-TRANSLATE-BATCH TASK-001: the TASK's own `check-env` command loses
  Cyrillic (`-NoProfile` skips the UTF-8 profile), `check-env.ps1`'s powercfg filter always
  prints an empty section, and the acceptance criterion demanded
  `torch.cuda.max_memory_allocated()` — which returns 0 for CTranslate2. All three went in as
  numbered items with a proposed fix; the scripts were left untouched because the TASK did
  not authorise editing them.
- **When a prescribed measurement method is unusable, do not silently substitute.** Report
  the prescribed method's real output *and* your substitute, and raise the discrepancy as a
  canon question. Silently swapping the number hides a broken acceptance criterion.
- Ask for the acceptance thresholds you will be judged on (which numbers, against what) if
  the TASK does not state them — guessing wastes a whole task cycle.

### Writing the report: don't emit RST double-backtick markup

Markdown renders `` `x` `` as inline code, but the RST-style ``` ``x`` ``` (easy to slip into
when the text is full of Windows paths) renders as literal backticks — 112 occurrences needed
fixing in one pass. Use single backticks. If you must repair a file post-hoc, do it
**fence-aware** (track ``` fences, skip their innards, else ``` ``` ``` collapses to ``` `` ```
and breaks the code blocks).

## UTF-8 BOM: check the project first, never apply blindly (corrected 2026-09-13)

The old form of this rule said *every* .md MUST start with `EF BB BF`, on the grounds that
Yuri's Markdown reader decodes BOM-less UTF-8 as Windows-1251 → mojibake. **That is not
universal, and stating it as universal produced a wrong instruction.**

Verified fact: in **VIDEO-TRANSLATE-BATCH** every canon file — `CONTEXT.md`, `AGENTS.md`,
`tasks/TASK.md`, `tasks/REPORT.md` — is UTF-8 **without** BOM (`head -c 3` → `23 20 30` = `# `).
Reports I wrote BOM-less were accepted by the architect three tasks in a row (TASK 001, 002,
GIT-001, 003), and the blank template the architect himself drops in is BOM-less too.

**Rule: match the neighbours, then decide.**

```bash
for f in CONTEXT.md tasks/TASK.md tasks/REPORT.md; do
  printf "%-20s " "$f"; head -c 3 "$f" | od -An -tx1 | tr -d ' \n'; echo
done
```

- Neighbours carry `efbbbf` → write with BOM.
- Neighbours carry `232030` / `2d2d2d` → write BOM-less, do not "fix" them.
- Genuinely mixed, or the project is new and has no precedent → ask, and never re-encode a
  file the architect owns as a side effect of an unrelated task.

- **Exception that survived unchanged: Hermes `SKILL.md` files MUST be BOM-LESS.** YAML front matter breaks the skill loader if a BOM is present. When installing skills into `%LOCALAPPDATA%\hermes\skills\`, verify first 3 bytes are `2d 2d 2d` (`---`), NOT `ef bb bf`.
- `write_file` tool does NOT add BOM — after writing, re-encode with Python:
  ```python
  with open(path, 'w', encoding='utf-8-sig') as f:
      f.write(content)
  ```
- Verify: `head -c 3 <file> | xxd | head -1` should show `efbbbf`.
- Files may be locked (open in reader) → retry with wait on PermissionError.

## Git discipline

- No commit/push without explicit instruction from user or TASK.md.
- **When git IS allowed, the task is NOT complete until you have actually done commit + push + verified the hashes.** Saying "Done" after code changes without performing the git operations is a workflow failure — the user will call you out on it. TASK.md headers explicitly say `Git: РАЗРЕШЕНО` or `Git: НЕ разрешён`. Obey literally.
- **TASK-N-post checkpoint pattern (recurring, LLM-KNOWLEDGE-BASE and similar architect-driven projects):** after every code task the architect writes a `TASK-N-post` git-checkpoint task INTO `tasks/TASK.md` (commit+push of the accepted code + canon + archive). This means: **after finishing a code task (TASK-N), RE-READ `tasks/TASK.md` before declaring "Done"** — the active task may have already been replaced by TASK-N-post. The user rejected a "Done. TASK-N completed" that ignored the pending post-checkpoint, with HEAD unchanged and dirty tree (`TASK-015` → never declared done until `TASK-015-post` was pushed). Sequence: finish code → re-read TASK.md → if post-checkpoint present, do the git steps → only then report Done with hashes.
- **REPORT.md for git-post tasks MUST show actual git output** — `git rev-parse HEAD`, `git ls-remote origin refs/heads/main`, `git push` output, `git status`. The user rejected a report that said "Done" without these. The hashes themselves are the deliverable.
- Git pull conflict with local untracked files: move them to `.backup_local/` first
  (per DEV-NOTES.md section 7), then pull.
- Branch: rename `master` → `main` to match remote if needed.

#### Two-commit TASK workflow (A = archive scope, B = fill report)

In projects where the architect prepares archive directories (`tasks/done/NNN-name/`) and updated canon files, the coder executes exactly **two commits**:

| Commit | Files | Message pattern | Purpose |
|--------|-------|----------------|---------|
| **A** | Scope from TASK.md (PROJECT_LOG, TASK, REPORT, done/NNN/) | `docs: archive accepted TASK-NNN, update PROJECT_LOG` | Push canon + archive to remote |
| **B** | `tasks/REPORT.md` only | `docs: fill REPORT-NNN after push` | Report the real hashes |

**Check the project's convention before applying this rule.** Some projects codify the
opposite: `git log --oneline` shows a standing series of `REPORT: git hash для TASK-N`
commits, and the TASK itself requires the report to carry `git log -1 --oneline` plus push
confirmation. There the two commits are **task work** and the **hash-fill follow-up** — follow
the log, not the general rule. Order: commit work → push → read `git rev-parse HEAD` and
`git ls-remote origin refs/heads/main` → patch the report's Git section with that real output →
commit `REPORT: git hash для TASK-N` → push. A report can never contain the hash of the commit
that carries it; the follow-up commit is the resolution, not a defect.

**Important — no third commit.** Where the architect explicitly forbids amend and fix-hash commits, get hash B in without a third commit. Strategy for getting exact hash B into the report:

1. Fill REPORT.md with known hash A and placeholder for hash B (e.g. `&lt;will be filled after commit B&gt;`)
2. `git add tasks/REPORT.md && git commit -m "docs: fill REPORT-NNN after push"` → note hash B
3. `git push origin main`
4. **Patch** REPORT.md on disk with exact hash B — do NOT commit the patch (it stays as working-tree dirty; the next task covers it)

This avoids both a third "fix hash" commit and leaving a wrong hash in the committed file. The architect sees the correct hash on disk when reading the report for the next task.

**Verification after two-commit workflow:**
```bash
git rev-parse HEAD                     # should match commit B hash
git ls-remote origin refs/heads/main   # must match
git status                             # clean (except REPORT.md hash fix if uncommitted)
git log --name-only --format="" <hash-A>..HEAD | grep -E '^(pages/|chats/|index\.md)' || echo 'PASS: no prohibited in commits'
```

## Push verification (commit → push → confirm)

After pushing, verify the push actually landed on remote. This is the canonical check — works with any auth method (HTTPS token, SSH), no `gh` required:

```bash
git rev-parse HEAD                     # local SHA
git ls-remote origin refs/heads/main   # remote SHA (real API call, not cached)
git status                             # should show "up to date with origin/main"
```

If the two SHAs match and status says up to date → push confirmed. If they differ, the push failed or you're on the wrong branch.

**A single `Could not resolve host: github.com` is a transient resolver hiccup, not an outage.**
In one session `git pull` failed with it while `curl -sI https://github.com` returned 200 and the
very next `git ls-remote` succeeded; the pushes before and after went through normally. Confirm
with a cheap independent probe (`curl -s -o /dev/null -w '%{http_code}' --max-time 10
https://github.com`, `nslookup github.com`) and re-run the git command (up to 3 attempts, short
sleep) before reporting a network problem. Never report a push as failed when the push output
itself printed `<old>..<new>  main -> main` — that line is the server's own confirmation.

**A long-lived approval prompt that times out is not a denial.** If a command comes back
`BLOCKED: … user has NOT consented …` because nobody answered the prompt, do not re-issue it and
do not shop for a different command that achieves the same effect. Do the parts of the TASK that
need no approval, then state plainly which git step is waiting on the user and why — Yuri usually
answers on the next turn, and the TASK's own git instruction then covers it.

This pattern is the companion to the "Always verify git state" preflight check below — that one checks before starting work, this one checks after pushing.

### Scope verification before commit

Before committing, verify that **only** the intended files are staged. This prevents accidental inclusion of generated files, chat data, or secrets:

```bash
git add <scope-files>          # add only what's in the TASK scope
git diff --cached --name-only  # list staged files
# Manually verify: no chats/, no pages/, no index.md, no .env, no ~$*
```

**Anti-pattern:** `git add -A` or `git add .` — these stage everything, including untracked generated files.

**The architect shares this working tree.** Their in-flight canon edits (`AGENTS.md`, `CONTEXT.md`,
`tasks/TASK.md`) and the user's dropped artifacts (an inspect dump, a screenshot) routinely sit
uncommitted next to yours. Add your scope files **by name**, leave theirs uncommitted, and name the
leftovers in the REPORT (`?? supabase/блоки (A)–(D)-SQL.txt` etc.) so the reviewer knows the dirty
tree is expected and not a botched scope.

**Quick check** (from TASK-009/010-pre):
```bash
git diff --cached --name-only | grep -E '^(chats/|pages/|index\.md|~\$|\.env)' && echo "FAIL: forbidden files staged" || echo "PASS: scope only"
```

This is especially important in two-agent workflows where the architect's archive directories (`tasks/done/NNN-name/`) and code changes must be committed together, but chat data and generated files must NOT.

### First commit / `git init` on a fresh project repo (VIDEO-TRANSLATE-BATCH GIT-001, 2026-09-13)

- `init.defaultBranch` on this PC is **`master`** — the TASK's `git branch -M main` is
  load-bearing, not decoration. Verify with `git symbolic-ref HEAD` (prints
  `refs/heads/main`), never with `git branch --show-current` alone before the first commit
  (`git rev-parse HEAD` errors out on an unborn branch — that error is normal, not a failure).
- **Secret-scan false positive that will always fire: the TASK's own scan command.**
  `git diff --cached | Select-String -Pattern 'sk-or-v1-|sk-ant-|ghp_|gho_|AKIA'` matches
  itself when the command is written verbatim into `tasks/TASK.md` (which it is). Diagnose it
  — `grep -rl -F` for each prefix separately, then show the matching line — instead of
  loosening the pattern or reaching for `--no-verify`. Same class of FP: `*_secret*` in
  `.gitignore`. Report both as resolved false positives.
- Prove the stop-list **by counts, not by absence of output**: `Select-String -Quiet` prints
  nothing when there is no match, which is indistinguishable from a broken check. Use
  `@(git ls-files | Where-Object { $_ -like 'Vendor/*' }).Count` and report `0`.
- Show *why* an excluded path is excluded: `git check-ignore -v <paths>` prints the exact
  `.gitignore` line + rule number per path. Stronger evidence than "it's in .gitignore".
- **The report you commit is the template, not your filled version.** The architect swaps in
  a blank `tasks/REPORT.md` before the git task, so the commit contains "Статус: НЕ НАЧАТО"
  and your filled report stays as an expected dirty working tree (`M tasks/REPORT.md`).
  State this explicitly in the report so the reviewer does not read it as a botched job —
  and confirm the previous report was archived (`tasks/done/NNN-REPORT.md`) so nothing is lost.
- Git *writes* for these tasks go through `pwsh -NoProfile -Command "..."` (AGENTS.md п.3,
  DEV-NOTES п.22), not bash. Multi-line commit messages break on the bash→pwsh quoting hop:
  write the message to a file inside the ignored dir (`logs/commit-msg.txt`) and use
  `git commit -F`.

### Writing a long REPORT.md — one big payload stalls the stream

A single `write_file`/`execute_code` call carrying a whole 15–25 KB report is large enough
that the tool call **never lands**: the stream times out mid-call and the file is not
written (the symptom is an error about the previous call being too large, or a silent stall).
Budget roughly **≤ 6 KB per call** and build the file incrementally:

1. `write_file` the skeleton (header + first two or three sections).
2. Append each further block with `patch` mode=replace, anchoring on the **last 2–3 lines of
   the current file** and re-emitting them plus the new text.

Check afterwards with `wc -l` that the file is the expected size, and re-read the tail — a
partially-applied append is worse than a failed one. The same budget applies to appending
sections to skills.

**Know the failure signature.** An over-long call does not always report "too large": the
stream can truncate the arguments mid-flight, so the error you actually get is a
**missing-required-field** complaint (e.g. `missing required field 'path'`) even though you
did intend to send it. If you see that error on a call whose payload was long, do NOT retry
the same payload — shrink it and put the required fields (`path` for `write_file`) first.
Three identical retries of an oversized payload all fail the same way; the fix is size, not
persistence.

### Git pull --rebase with conflict resolution

When syncing this repo with remote (common in two-agent architecture where architect pushes from another machine):

**Preflight (Windows, recurring):** a stale `.git/index.lock` is a common precondition on this machine — it fired in BOTH HERMES-ALL-IN-ONE and HERMES-AGENT in one session. Before the first git *write* command (`stash`, `commit`, `add`), if you see `error: Unable to create '.../index.lock': File exists`, clean it and retry:
```bash
rm -f .git/index.lock
```
This is a leftover from a previously crashed/interrupted git process, not a real concurrent writer. Rerunning the same command after removal works.

**Step-by-step:**

1. **Stash local changes** before pulling, especially if TASK.md/REPORT.md are modified:
   ```bash
   git stash push -m "pre-pull: <description>" --include-untracked
   ```
   `--include-untracked` captures _arhiv/ and other new files too.

2. **Pull with rebase** (preserves local commit order on top of remote):
   ```bash
   git pull --rebase origin main
   ```
   Two outcomes:
   - **Fast-forward** (`Updating <old>..<new>\nFast-forward`, no `CONFLICT` lines): remote was strictly ahead, no divergence. **Skip steps 3-4 entirely** and go straight to step 5 (stash pop). This is the common case when only the architect has pushed lately.
   - **Conflicts** in CONTEXT.md, PROJECT_LOG.md, tasks/TASK.md, tasks/REPORT.md: both sides diverged. Proceed to step 3.

3. **Resolve conflicts** per architect's decision. If architect says "accept remote":
   ```bash
   git checkout --theirs CONTEXT.md PROJECT_LOG.md tasks/TASK.md tasks/REPORT.md
   git add CONTEXT.md PROJECT_LOG.md tasks/TASK.md tasks/REPORT.md
   git diff --name-only --diff-filter=U   # verify no unresolved conflicts
   ```

4. **Continue rebase** — use `GIT_EDITOR=true` to avoid editor hang on Windows (git-bash opens vim/nano otherwise):
   ```bash
   GIT_EDITOR=true git rebase --continue
   ```

5. **Restore stash**:
   ```bash
   git stash pop
   ```

6. **Recover architect-updated TASK.md** if stash pop clobbered it (the architect may have updated TASK.md on disk after the stash was created). Re-read the TASK.md content from the conversation or restore from the architect's authoritative version.

7. **Verify**:
   ```bash
   git log --oneline -8
   git status
   ```

**Pitfalls:**

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Stale `.git/index.lock` | `error: Unable to create '.../index.lock': File exists` | `rm -f .git/index.lock` then retry the command |
| Cyrillic paths in `git rm` | `fatal: pathspec '...' did not match any files` on git-bash | Use glob-pathspec instead: `git rm --cached '~$*'` or `git rm 'часть-имени*'`. Git-bash/MSYS encodes non-ASCII paths differently than the filesystem; glob pattern matching works around it. For `git add`, never type the Cyrillic name at all — **stage the parent directory** (`git add supabase/`) and let `git status --short` show it escaped (`A  "supabase/\320\222...txt"`); those octal escapes are normal output, not an error. |
| Editor hang on `rebase --continue` | Command times out (30s+) | Set `GIT_EDITOR=true git rebase --continue` |
| Stash pop clobbers architect-updated TASK.md | TASK.md shows old version | Re-write TASK.md with the architect's authoritative version (from conversation context) |
| Rebase rewrites commit hash | `bf1f33b` becomes `486bd56` | Expected — rebase always rewrites. Content is preserved. Verify with `git show HEAD` |
| PC1 Session 8 entry lost in conflict | PROJECT_LOG.md missing PC1-specific setup notes | Recover with `git show <old-head>:PROJECT_LOG.md` and append to the end of PROJECT_LOG.md |

## Console output

- Use ASCII-safe replacements: `->` not `→`, `<=` not `≤`, straight quotes only.
- The terminal environment may be cp1252; non-ASCII `print()` can crash.
- Inside Python, set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` (already set on this PC).

### Running a `.ps1` with Cyrillic from the bash terminal tool (verified 2026-09-12)

`pwsh` writes to a redirected pipe in the console's ANSI codepage (cp1252 here), so every
Cyrillic string in the script's `Write-Host` comes out as `?` and the captured log is
useless ("ASCII text"). **Set the output encoding inside the pwsh invocation, before
dot-calling the script:**

```bash
cd <project-root> && pwsh -NoProfile -Command '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8; & "./scripts/foo.ps1"' 2>&1 | tee logs/foo.log
```

`-NoProfile` means the user's UTF-8 profile (DEV-NOTES §12) does NOT apply — that is why
the override has to be explicit. TASK.md may give the plain
`pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\foo.ps1` form; if the log comes
out as `?`-filled, this is the fix, not a script bug. Report the deviation.

- **Don't fight this with `chcp`.** Running `chcp.com 65001` first does not help the
  `-NoProfile` case; the `[Console]::OutputEncoding` line does.
- **A script that internally shells out to a legacy console tool loses its matches.** If
  a `.ps1` filters output like `powercfg /query ... | Select-String '<Cyrillic pattern>'`,
  the UTF-8 override makes the child's OEM-encoded output decode wrong and the filter
  silently matches nothing — the section prints empty, which looks like "no data" rather
  than "filter broke". Re-check such a value directly:
  `pwsh -NoProfile -Command 'powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE' | grep -a 0x`
  Report the empty section as a defect of the script; do not silently edit the architect's
  script unless the TASK asks for it.

### MSYS mangles leading-slash arguments — run those via `pwsh -Command`

Git-bash/MSYS rewrites arguments that start with `/` into Windows paths, so
`powercfg /query SCHEME_CURRENT ...` from the bash terminal tool fails with
`Неправильные параметры - используйте параметр "/?"`. Same class as the Cyrillic-path
`git rm` pitfall above. Wrap such commands in `pwsh -NoProfile -Command '...'` or quote
the slash-argument.

#### Stopping a background server: kill the listening PID via pwsh, not `process kill`

`process(action='kill')` on a `npm run dev` / server background session can hang for the
whole tool timeout (420 s observed) **while the server keeps answering** — the npm wrapper
holds the shell, not the child that owns the port. Don't re-issue it; stop the process that
listens on the port:

```bash
PID=$(netstat -ano | grep ':5173' | grep LISTENING | awk '{print $NF}' | head -1)
pwsh -NoProfile -Command "Stop-Process -Id $PID -Force"
curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 http://localhost:5173/   # 000 / curl exit 7 = port free
```

- `taskkill /F /PID <n>` **cannot** be called straight from this bash tool: MSYS mangles the
  slash flags (`ERROR: Invalid argument/option - '//PID'`), and `cmd //c "taskkill ..."` does
  not execute anything — cmd starts interactively and prints its banner instead. The
  `pwsh -Command ... Stop-Process` form is the one that works.
- Confirm the port stopped answering before telling the user the server is down. A kill that
  "succeeded" in the tool result but leaves HTTP 200 is not a stopped server.

#### Pass `workdir` on every terminal call — the persisted cwd may be another project's

The terminal session's cwd survives across calls **and sessions**, so the first command of a
session can fail with `cd: /g/...: No such file or directory` for a directory that was never
part of this task. Pass `workdir=<project root>` explicitly instead of relying on the stored
cwd; if a `cd` errors like that, re-issue the same command with `workdir` rather than
debugging the path.

### Background-process stdout is block-buffered — empty output is NOT a hang

When you launch a long-running Python script as a **background process** (`terminal background=true`) and inspect it via `process poll/log`, an empty `output_preview` does **not** mean the script is stalled. Python block-buffers stdout when it is piped (not a TTY): `print()` accumulates in the buffer and only flushes on buffer-full/exit. So a heavy job (e.g. first download + CUDA init of a ~3 GB model) can sit visible-but-empty for a minute+ then dump everything at once — or the process is killed (`kill_all`) before you ever see a line.

**Real case (STT-WHISPER-LOCAL, 2026-09-08):** a GPU prewarm/diag script ran 150+ s "silently"; I nearly misjudged it as a hang and killed it. It was buffering. Adding `-u` (or `env:PYTHONUNBUFFERED='1'`) made output stream line-by-line and the result appeared immediately.

**Rules:**
- Launch diagnostics with `python -u <script>` (unbuffered) whenever you need to watch progress in a background process.
- Before declaring "stalled," cross-check with a side signal that can't be buffered: `du -sh <cache>` growing, `nvidia-smi` VRAM/util, `Get-Process -Id <pid>` CPU ticking. Growing cache/CPU = working, silence is just the buffer.
- `process(action='wait')` clamps its timeout to 60 s even if you pass a larger value — poll in a foreground `sleep N` loop instead for longer waits, but don't leave a long `sleep` running in the background (it can trigger `kill_all` of sibling background procs on interruption).
- **Foreground `sleep` over 180 s is the same trap (confirmed 2026-09-12).** A foreground `sleep 290` hit the tool's 180 s cap, surfaced as `[Command timed out after 180s]`, and that interruption **killed a running background download job** — `process(action='list')` came back empty and the job's next queued file never started. It is not the sleep itself that is dangerous, it is *any* interruption while a long sleep is in flight. **Keep foreground sleeps at `<= 150 s` and re-poll in a loop.** Symptom: a background job that was visibly progressing is silently gone, with no `DONE rc=` line and no partial/control files for the remaining items. Recovery is just relaunching the leftover work — aria2c resumes from its `.aria2` control file, so nothing already downloaded is lost.

### Long jobs: post measured status unprompted (user-mandated 2026-09-12)

A pipeline that runs 10–30 minutes in silence earns «Долго нет сообщений» and «Что сейчас
происходит?» — Yuri sent both in one session, and each interruption aborting a
`[Command interrupted]` foreground sleep can take a sibling background job down with it.

- Do NOT park inside one long blocking `sleep`. Poll in increments of **≤ 150 s** and emit a
  status line each time: which step is running, elapsed, and the last meaningful log line.
- Status = measured progress, not "still running": step markers (`>>> STEP START`), seconds
  per stage, VRAM/util, files appearing on disk. A number is a status; an adjective is not.
- When Yuri asks «что происходит?» / «расскажи» — lead with current state (what the process
  is doing right now, elapsed, last log line), then continue working. Do not answer with a
  plan for what you are about to do.
- **Background completion notifications can arrive stale or out of order.** In one session a
  notification for the FIRST (already-failed) attempt landed long after the second attempt
  had succeeded. Before reacting, match the notification's `session_id`/command against the
  job you are actually tracking, and check the log file's current tail rather than trusting
  the payload.

### When a tool call fails, explain it in plain language (user-mandated 2026-09-13)

A tool call that stalls or is rejected mid-writing is invisible to Yuri — he sees only that
nothing happened. His reaction was «Я не понял, что произошло.» The fix is a short, plain
paragraph, and it must **separate your tooling mistake from the task state**:

- One or two sentences on what actually happened ("my call was too big for the stream, the
  file was not written; I split it into two calls").
- Then the task status as a table — explicitly saying the task itself was unaffected if it
  was ("the git work is done, only the report write failed").
- Then resume. Do not answer a "what happened" question with a plan.

### When idle, answer with state + what is pending on the user

«Как дела? Отвечай.» means: give the status now, not a narrative. Format that worked: a small
table of what is done / what is running (say "ни одного процесса не крутится" when true),
then a numbered list of what is waiting on the USER, ordered by importance. Never a
description of what you are about to do.

### Spending the owner's metered budget is a decision point, not a retry

When the task runs against a **limited, paid** resource (an API key with a hard limit, a
metered quota), a failure that is *not* on the axis under test is a stop-and-ask, not a
re-run:

- Re-running costs money the owner budgeted for something else; three identical failures cost
  three times and teach nothing new.
- Ask first: repeat the run / accept the partial result / change the code. All three are the
  architect's or owner's call.
- Do NOT tune parameters or edit vendor code to "get past" a failure unless the TASK says so —
  capture it as a measured result instead.
- Before proposing a re-run, price it: exact spend so far, expected spend per attempt, and
  the fraction of the remaining budget.

### Reading text files on Windows (CRLF + lone `\r`)

Windows-saved text files (chat exports, .md, .txt) often contain BOTH `\r\n` pairs AND **lone `\r`** characters (a `\r` NOT followed by `\n`). A naive `replace('\r\n', '\n')` leaves the lone `\r` behind, which silently breaks:

- **Regex parsers** expecting `\n` separators — e.g. frontmatter delimiters `^---\n` never match, `extract_frontmatter` returns `{}`.
- **Read→write→read idempotency** — writing LF-normalized text back and re-reading yields different content, so computed hashes never stabilize (SKIP never fires, regenerations loop forever).

Fix — normalize EVERY `\r` to `\n`, not just CRLF pairs:
```python
text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
```
Order matters: CRLF first (else CRLF becomes double `\n\n`), then lone `\r`.

**Verify idempotency in selftests:** read → write → read must return identical text. This exact bug surfaced in TASK-010: `replace('\\r\\n','\\n')` alone passed frontmatter parsing but broke roundtrip stability (hash changed after restore), because real chats contain lone `\\r` in the body.

**CR characters make terminal output lie — use hex, not repr.** When debugging a line that contains `\\\\r`, printed output is misleading: `print(repr(line))` shows `'OPENROUTER_API_KEY=***\\\\r'` while `line.endswith('\\\\r')` returns False and the actual bytes after `=` are `os.get...`. The `\\\\r` resets the cursor, so what you see on screen is not the string. Whenever two checks contradict (repr vs endswith vs grep), dump bytes: `line.encode().hex()` or `print([hex(ord(c)) for c in line[-5:]])`. This was the loop trap in TASK-011 (privacy_guard.py) — 4+ attempts re-reading the same line before the hex dump showed the truth.

**`Path.relative_to()` raises ValueError on Windows across different drive letters.** When test code on C: calls `page_file.relative_to(HERE)` where HERE is on G:, Python raises `ValueError: paths don't start with the same drive`. Crashes `cmd_all` when a test temp dir is on a different drive than the project root. Fix: use `str(page_file)` (absolute path) or `os.path.relpath(page_file, HERE)` (cross-drive safe) instead of `Path.relative_to()`. TASK-023: test 10 failed silently because of this — stdout was empty, the test printed "valid=False".

## Blocker escalation (Rule of Three)

When you make 3+ attempts on the same root cause without progress — same error, same function, same hypothesis — **STOP and escalate to the user/architect.** Do not attempt fix #4 without input.

**Signal:** you're about to try the same fix with slightly different parameters, or you're deep in terminal output analysis without a clear next hypothesis.

**Action:** state the blocker in 1-3 lines:
- What you tried (3 attempts)
- What the actual problem is
- One clear question for the architect

**Example** (from TASK-011, privacy_guard.py debugging loop):
> "Зациклился на отладке `\r` в терминале. Проблема: паттерн KEY=value матчит `OPENROUTER_API_KEY=***` (3 ложных срабатывания). Вопрос: как быть — ужесточить паттерн, добавить allow-файл, или принять 3 хита на 4241 строку?"

**Do not** restate the full debugging history or show all 3 attempts. The user/architect has context from the conversation.

**Rationale:** The user explicitly told me: "Мне кажется, ты в каком-тупике и ходишь по кругу. Если у тебя есть вопросы, дай их задай архитектору, он свежим взглядом посмотрит." This is a first-class workflow rule, not a one-off remark.

### Architect's anti-loop rule: separate diagnosis from fixing, then time-box it (2026-09-08)

The recurring root cause of "хожу по кругу" is **mixing two different questions**: (a) *understand the root cause* and (b) *make it work now*. The architect mandated:

1. **Split them explicitly.** Diagnosis and fixing are different tasks. Do ONE at a time; state which you're doing.
2. **Give diagnosis a hard budget (~5 min) for "quick truth".** Inside the budget use cheap decisive probes (real engine run, `nvidia-smi`, config dump). If the cause isn't obvious in ~5 min, **stop diagnosing and fix pragmatically** — a working artifact "any price" beats an incomplete root-cause essay.
3. **Push the root-cause to a separate backlog task**, don't hold the main task hostage to it.
4. **Remove unnecessary entities (the architect's "лишняя сущность").** In STT-WHISPER-LOCAL, a *working* engine test harness masqueraded as part of the app; the architect cut it ("убери лишнюю сущность") and the stable path was the plain engine + clean restart, exactly as on the working PC2. When one machine differs from a working reference, suspect added cruft.

### Don't trust stack/tech terms that arrive mid-truncation

`[System: previous response truncated]` can inject stray tokens into the conversation narrative (e.g. "pytorch/ggml" that were never in the stack — whisper-local is pure CTranslate2). Before parroting a claimed technology, **confirm it against the actual repo / AGENTS.md / CONTEXT.md**, not against the conversation's corrupted text. If a term matches nothing in the codebase, say so and move on — don't build a fix around a phantom dependency.

## Selftest verification pattern

When a TASK requires internal tests (`--selftest` flag in the script itself, not via pytest), follow this pattern:

- **Isolation:** tests run in `tempfile.TemporaryDirectory` — never touch real project data
- **Output format:** each test prints `OK | <test-name>` on pass, `FAIL | <test-name>: <reason>` on failure
- **Final line:** `N/N passed`
- **Exit code:** 0 if all pass, 1 if any fail
- **No silent success:** tests must print substantively — empty output with exit 0 is treated as failure (per DEV-NOTES §9)

This format is both machine-parseable and human-readable:
- Architect can `grep` for `FAIL` vs `OK`
- `N/N passed` gives instant go/nogo
- Exit code gates CI-like workflows

**Rationale:** TDD (see `test-driven-development` skill) covers *when* to write tests. This covers *how* to structure self-contained selftests in projects without pytest framework: zero dependencies, runnable with `python <script> --selftest`.

**Implementation template:**
```python
def selftest():
    import tempfile
    from pathlib import Path
    total = passed = 0
    with tempfile.TemporaryDirectory(prefix="selftest_") as tmpdir:
        tmp = Path(tmpdir)
        total += 1
        if some_condition:
            passed += 1
            print(f"OK | test-name: description")
        else:
            print(f"FAIL | test-name: reason")
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1
```

**Pitfalls:**
| Pitfall | Fix |
|---------|-----|
| Tests pass but printed nothing | Add `print()` inside each test branch — DEV-NOTES §9 bans silent success |
| Integer division on `N/N` | Use `f"{passed}/{total}"` — both are ints, string formatting avoids truncation |
| Temp dir is project-specific | `tempfile` on Windows writes to `%TEMP%` — clean, no cross-contamination |
| `total` counter double-counted | When a test section has N assertions, each needs its own `total += 1` BEFORE the check. Extra `total += 1` with no corresponding `print()` inflate the count silently (real bug in TASK-008: 5/8 passed while all 5 printed OK). Best practice: `total += 1` immediately before *each* `if/else` branch that prints `OK |`/`FAIL |`, never anywhere else. |
| Lookup function changed, old fixtures silently fail | TASK-010: chat lookup moved from filename to frontmatter (session_id); tests with filename-only fixtures returned empty hash and 'hash unchanged' failed (7/8 passed). When a resolution/lookup function changes, update ALL fixtures to the new schema (id in frontmatter) and re-check every dependent test. |
| Function now emits WARNING to stderr, polluting test output | Capture stderr with io.StringIO for tests that check warning output; restore after each assertion. Pattern: `stderr_cap = io.StringIO(); old = sys.stderr; sys.stderr = stderr_cap; fn(); sys.stderr = old; assert 'WARNING' in stderr_cap.getvalue()`. Used in TASK-011 for broken-source and pinned-drift tests. |
| Regex group renumbering after adding optional capture group | When you add a new optional capture group to an existing regex, every m.group(N) reference shifts. Search the entire file for m.group( and verify each index. m.group(0) (full match) is safe, but m.group(1) becomes m.group(2), etc. TASK-015: PINNED_RE gained a section group, and extract_pinned_blocks silently extracted the section name instead of the content. |
| execute_code read_file returns line-numbered format | read_file(path) returns "content" with "LINE_NUM|LINE_CONTENT" per line. text.replace(old, new) silently fails because old_string lacks the line-number prefix. Use terminal with cat/read to get raw content, or write a standalone script to a temp file and run via terminal. |
| `patch` tool fails with Cyrillic/UTF-8 strings in old_string | The `patch` tool (mode='replace') fails to find old_string when it contains Cyrillic characters, even when the exact text is confirmed in the file. This is a tool limitation with non-ASCII matching. Workaround: use terminal with a short Python inline script to do the replacement. Write the script to a temp file first to avoid bash quoting issues with `-c`. |
| `patch` new_string double-escapes backslash sequences (`\\\\n`) | Replacing a Python source literal that itself contains `\\n` (backslash+n, e.g. `'TODO: ...\\n'` → `'Author note ...\\n'`) via the patch tool writes `\\\\n` (double backslash) into the file — the fixture now yields literal backslash+n instead of a newline. TASK-018-post: fixture replacement silently broke this way. Reliable fix: byte-level replace via a Python script written to a temp file — `raw.replace(b'X.'+bytes([0x5c])+b'n', ...)` — then verify with `grep -n ... | cat -A` (shows backslashes literally). Shell `-c` and sed both mangle `\\n`; write the script to a file and run it. |
| `patch` indentation corruption on CRLF files (Windows) | Multi-line `patch` on CRLF files introduces 8->16 space indentation corruption because the tool's line-matching misaligns with CRLF line endings. The old_string match succeeds but the new_string is inserted at a deeper indent. Workaround: fix indentation with `sed -i 'start,stop s/^                /        /' file.py` after the patch, or use `write_file` for the entire function instead of patching. Recurring in LLM-KNOWLEDGE-BASE TASK-021/023 on compile.py and lint_frontmatter.py. |

### ⚠ NEVER use `patch` on a file that contains secrets — the diff echoes them in full

**Real incident, VIDEO-TRANSLATE-BATCH TASK-003 (2026-09-13).** Changing one line of
`VideoLingo/config.yaml` (the translation model name) with the `patch` tool returned a
unified diff whose context lines included the adjacent `api.key: 'sk-or-v1-…'` line —
**in cleartext**, into the tool output, the session transcript and the session DB. Yuri's
rule for keys ("may send one — warn immediately, ask for rotation") had to be invoked on my
own accident, mid-task.

Why it is easy to miss: Hermes secret-redaction is **not consistent across tools**. The same
key, in the same session, came back masked from `grep`/`read_file` (`sk-or-…b32a`) but
unmasked from `patch`'s diff. Redaction is a safety net, not a guarantee — never rely on it.

Rules:
- **Before patching, ask: does this file hold a secret?** Typical: `config.yaml`, `.env`,
  `*.yml` with an `api.key`/`token`, anything a TASK marks «не коммитить».
- For such files, don't touch them with `patch`/`write_file` at all if avoidable. Options,
  best first: (a) ask the owner to make the change; (b) change it with a script that reads,
  substitutes and writes **without printing** — only ever `say()` the field *length* or a
  boolean like `is_placeholder`; (c) if you must patch, patch a file region that provably
  cannot contain the secret (a different file, or a section far from the key block).
- Reading a secret-bearing file to *verify* a value is fine — mask it:
  `len(value)`, `value[:6] + '...'`, `is_placeholder(value)`. Never `print(value)`.
- **If a secret ever reaches the transcript: say it first, in the same reply, at the top.**
  Name what leaked, what the exposure window was, ask for rotation, and stop touching that
  file. Do not bury it under task status — the owner must be able to act before reading on.
- Prefer self-verifying probes that never transport the secret: a script that reads the key
  from the config itself and calls the provider's own endpoint (e.g. OpenRouter
  `GET /api/v1/auth/key`) reports limit/usage/remaining without the key ever crossing the
  chat boundary.

See `references/regeneration-hash-skip.md` for a real-world example of this pattern in a compile/regenerate system. See `references/test-filter-skip-isolation.md` for how to write a selftest that proves a skip/filter guard actually works (TASK-023).

## Live-auth and external-state checks: settle the credential path BEFORE promising them

A TASK that asks for «живые проверки входа» (live login/logout/F5 checks) needs a password
you must never type yourself and must never accept in chat — only the vault tools may put a
password into a page.

- Check `browser_vault_list` for the origin (`localhost:5173`, the site host) **before**
  starting such a check, and state in your first status what happens if it comes back empty.
- If it is empty, `browser_vault_save_login` on the login page is the only sanctioned path
  (Hermes prompts the user in a masked UI field). If it returns `save_declined`, stop asking
  for this turn and report — do not retry, do not look for the password elsewhere.
- Report the blocker with two workable options: the user saves the login in Hermes
  (Settings → Passwords & Logins) so you can fill it next session, or the user runs the steps
  and pastes the observed results as text. Never offer to receive the password in chat.
- **A `save_declined` stands for the session, not just the turn.** Once the masked prompt was
  declined, do not re-issue it on the next task's turn — it reads as nagging. Mention the vault
  once as an *option* in the answer/REPORT and otherwise proceed.
- **When the TASK pre-blesses the split («сценарий вошедший может подтвердить пользователь»), prove
  the half you can prove yourself instead of reporting the whole feature unverified.** Anonymous /
  guest behaviour is fully checkable from the terminal: an empty-state line the code renders only for
  a zero-row result proves the read really reached the table (a failed request would render the error
  branch instead), and the *absence* of the form proves the auth gate. Report that half with the
  captured DOM text and console (0 errors), then hand the signed-in half over as a numbered checklist
  where every step carries its expected observable — never as «проверьте вход» in one line.
- A password already sitting in an *accepted* REPORT (a throwaway test account) is **not**
  permission to retype it — the rule is about the tool boundary, not about secrecy.
- **If the user pastes a password / verification code into the chat anyway**, don't echo it, don't
  use it, and say so in two lines: the password is not needed at *any* step of the task, and if it
  was the real one they should rotate it (Supabase → Auth → Users, or «Забыли пароль»), because
  the transcript persists. Then re-offer the vault as an option, not a request.
- **A file the user points at as «там логин и пароль» is not a vault.** Do not read it, and never
  echo or reuse the values: a credential file is the same tool-boundary problem as a chat paste,
  only with the secret parked in the repo (possibly in a gitignored file like `Мой аккаунт.txt`).
  Answer in two lines — passwords are not taken from files or chat, and if he wants you to run
  signed-in checks, the login goes into the Hermes vault; nothing else changes. «Ты можешь
  пользоваться, когда я дам разрешение» still leaves the vault as the only path you can act on,
  and it is fine to say that the checks stay with him in the meantime.

**A TASK's claims about external state are assertions, not facts.** «Аккаунт подтверждён»,
«RLS включён», «токен валиден» — verify against the real artifact (dashboard screenshot, SQL
output, an actual request) and report the contradiction, instead of building the next steps on
an inherited belief. One screenshot contradicting a TASK line is worth more than the whole
chain of work built on it.

**When a TASK gates later items on input only the user can supply** (SQL Editor output, a
paste, a dashboard toggle), do the items that do NOT depend on that input in the same session
and say exactly which ran and which wait. Idling for the whole task wastes the cycle; silently
inventing the missing input is worse. State the gate in one line so the user knows what to do next.

## SQL / Supabase migrations are deliverables, not scripts you run

The database side of a coder task has its own always-on rules (full recipe:
`references/supabase-schema-and-migrations.md`):

- **You never apply DDL.** You write `supabase/migrations/000N_*.sql` + an audit file, give the
  user exact SQL-Editor steps, and report what to expect (`Success. No rows returned` + NOTICEs).
  Treat that success line as **parse-OK only**: an `INSERT`/`UPDATE`/`DELETE` that touched 0 rows
  reports the same thing, so a hand-off mutation is not "done" in the REPORT until a control
  `select` comes back (`references/supabase-schema-and-migrations.md` §6).
- **Never write DDL from the brief alone.** Get the real column set first — REST probes with the
  publishable key resolve it in seconds (column existence 200/400, type from the
  operator-mismatch error text, `Content-Range: */0` for emptiness). **A probe answers only about
  the names you passed it** — loop a candidate list and a real column you did not think of stays
  invisible (a 28-name sweep of one table missed an existing boolean flag). The authoritative set
  is the user's `information_schema` output; until it arrives, write "none *outside the checked
  list*", never "no other columns exist" — and if an earlier report claimed the stronger thing,
  restate the corrected sentence in the next report. Unknown facts (PK, FK names, indexes, NOT
  NULL, defaults) become explicit `TODO` comments + numbered REPORT items, never invented
  constraints.
- **A column that exists under another name is not a rename you may perform.** Constrain the
  existing column, state the divergence in the REPORT with both options, and note that a rename
  is free while the table is empty.
- **Prove the file two ways before reporting**: `uv run --with pglast python check_sql.py <file>`
  (libpg_query — PostgreSQL's own parser) plus a control run on an already-accepted file, so the
  check is shown to be non-vacuous. The parser sees `plpgsql` bodies as literals, so a migration
  made of trigger logic gets a second pass against a **local embedded PostgreSQL**
  (`uv run --with pgserver`, throwaway cluster in scratch) that applies the file twice and
  asserts the behaviour — full recipe in `references/supabase-schema-and-migrations.md` §5b.
  Only the user's run proves it in the real project; say that in the REPORT.
- **Idempotent by construction**: `ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS` +
  `ADD`, `CREATE OR REPLACE FUNCTION`, and a `DO`-block that adds a foreign key only when no FK
  to that target exists — you do not know existing constraint names, so never drop by a guessed
  one.

## Role boundaries

- Do NOT edit `CONTEXT.md`, `AGENTS.md`, `TASK.md`, or `CLAUDE.md` — those are the architect's domain.
- Do NOT create parallel STATUS/NOTES/NEXT files — truth lives only in REPORT.md and PROJECT_LOG.md.
- Do NOT re-architect or add features outside TASK.md scope.
- **A loaded artifact is not an instruction to start.** Neither an auto-injected skill, nor
  a `tasks/TASK.md` that is already written, authorises work. TASK.md itself carries the
  line «выполнять только после явной команды пользователя» — honour it literally: read
  canon, then wait. Yuri has pushed back on this twice (opening a skill-triggered turn with
  a menu of things to do, and it is the reason TASK headers carry the "ГОТОВО К ВЫДАЧЕ"
  status). If you catch yourself producing a plan or "ready to start" summary without an
  explicit «выполняй TASK N», stop and wait.
- If the task references skills you don't have loaded, load and follow them.
- **Drafting new tasks:** If you discover bugs or improvements that warrant a new task, write a draft to `tasks/TASK-XXX-draft.md` (a separate file) — do NOT touch the canonical `tasks/TASK.md`. The architect will pick it up and integrate it.

## When TASK.md changes unexpectedly

If the remote repo's TASK.md differs from the local one (e.g. after `git pull`):
- The remote version becomes the active task.
- The local version is backed up in `.backup_local/`.
- Report the discrepancy in REPORT.md so the architect can decide.

### The user re-issuing the same start command can mean a NEW task version

«Прочитай AGENTS.md и CONTEXT.md и выполни задание в tasks/TASK.md. TASK-XXX» arrives with
the same wording every session — it is a *way to point you at the file*, not a statement that
the file is unchanged. The architect rewrites `tasks/TASK.md` **in place** between turns: the
same ID can come back with different scope, different checks, and different git permission
(observed: TASK-006 first issued as «аудит + baseline, git не делать», then replaced by
«закрытие сессии» with `git pull` first and commit+push required).

Before acting on a re-invocation, re-read the whole file and re-scan the tree — do not replay
your previous reading:

```bash
head -30 tasks/TASK.md      # ID, Статус, first steps — are they what you remember?
git log --oneline -5        # the architect may have committed while you were idle
git status --short          # new untracked artifacts?
ls -la supabase/ tasks/     # user-supplied inputs land as NEW files, not in chat
```

- Input the user promised (SQL Editor output, a paste, a dump) usually appears as a new
  untracked file in the repo rather than in the message. Find it with `git status` / `ls`
  before reporting it missing.
- A **blank `tasks/REPORT.md` template** on disk where your filled report used to be is
  normal, not data loss: the architect swaps the template in before a git task. The earlier
  report lives in the archived `tasks/done/NNN-…/` copy — re-derive, don't hunt for it.
- If `git log -1` shows a commit you did not make, `git pull` first and treat that commit's
  TASK.md as authoritative.

## Always verify git state before trusting REPORT.md

**Pitfall (learned 2026-07-24):** REPORT.md may describe an "intended" state (e.g. "18 files staged, ready to commit") that was already superseded by a commit the user made manually in another session. Trusting REPORT.md as ground truth leads to re-doing work that was already done.

**Mandatory verification at session start of a task that mentions staging/committing/pushing:**

```bash
git status                     # what's actually modified/untracked
git log --oneline -1           # what's actually the last commit
git ls-remote origin refs/heads/main   # what remote actually has
git rev-parse HEAD             # local HEAD
```

If `git log -1` already shows a commit with the message TASK-XXX describes, and remote SHA matches local HEAD → **TASK is already closed**. Update REPORT.md to record the actual commit SHA and state, and ask the user what to do next (don't re-run the same steps).

## Response style — Yuri's preference (verified 2026-07-24)

Yuri explicitly said: *"опять много слов"* (too many words again) when reviewing long answers. He repeated the preference across multiple turns in a single session. This is a **first-class style signal**, not a one-off complaint.

**Default response length: short.** When in doubt, prefer terseness.

### Concrete rules

- **Lead with the answer.** Skip preamble like "Sure, I'll help you with that" or "Let me think about this."
- **Tables > prose** for any list of 3+ items. Tables scan faster.
- **No "as I mentioned" / "as we discussed"** filler. If the user remembers it, don't repeat it.
- **No ASCII art** unless explicitly requested.
- **No recap of previous turns** at the start of each response. The user has scrollback.
- **Code blocks are fine to be longer** — Yuri is technical, dense code is welcome. But explanations around code should be 1-2 lines max.
- **One question per turn**, never a numbered list of 3+ questions.
- **State uncertainty directly:** "I don't know" > a paragraph explaining why I might not know.
- **When the user asks a direct question, ANSWER IT BEFORE INVESTIGATING.** Yuri asked
  «посмотри, реально ли это исправить в настройках?» and got ten tool calls of source
  archaeology before any answer; his reply was «Ты не ответил на мой вопрос». If the question
  is answerable from what you already know, answer in one line and only then verify. If it
  genuinely needs digging, send «проверяю, отвечу через N минут» first — silence reads as
  ignoring the question.

### When to break the rule

- User explicitly asks for a "full breakdown" / "подробный разбор" / "explained simply"
- Teaching a new concept that needs scaffolding
- When short is impossible without losing critical detail (e.g. error transcripts)

### Recovery when the user says "слишком много слов"

Acknowledge briefly ("сокращаю") and switch to short mode for the rest of the session. Don't ask for confirmation of new style — just do it.

**The sharper variant of the same complaint (recurring, user-stated as a standing deal):**
«Я понимаю, ты стараешься сделать работу качественно, но объяснение — это избыточная информация
для меня» + «давай договоримся: я показываю, что сделал, ты говоришь, что мне делать — кратко,
без долгих объяснений почему и зачем». He is not asking for less accuracy, he is rejecting the
*mechanics* prose. So on any turn that hands work back to him:

1. **Status first, 1–2 lines**: what is applied/verified and what is still open — no history.
2. **His next steps as a numbered list**, each step being one copy-pasteable command/query plus
   its expected output («ожидаю 1 строку с <email>»). No paragraph on *why* the step exists.
3. Keep the reasoning for `tasks/REPORT.md` (the architect reads it) and for the turn where he
   explicitly asks «почему» / «объясни подробно».

When he *does* ask a mechanics question ("что означает этот SELECT с JOIN"), answer it fully —
that is a request, not the default. The default is steps + expected output.

## References

- `G:\\AI\\DEV-NOTES\\DEV-NOTES.md` — canonical dev environment notes (all projects)
- Project-level AGENTS.md — per-project overrides
- `references/hermes-skills-install.md` — installing skills from `SOURCES-ARCHIVE` (TASK-007 recipe): copy map, BOM-less SKILL.md check, `hermes skills list` name-truncation pitfall, never overwrite builtins, python-vs-pip mismatch
- `references/junction-setup-windows.md` — creating/repairing directory junctions from git-bash (pwsh vs cmd //c, stale-junction-after-disk-rebuild)
- `references/browser-ui-checks.md` — verifying a Vite/React page without Playwright: dev-server startup, capturing console/JS errors with a CDP collector injected *before* navigation, DOM assertions, counter baselining, stopping the server, and checking the deployed SPA (deep-link 404 vs `vercel.json` rewrites, a root that 200s but crashes for missing `VITE_*` host env vars, stale-deploy detection by bundle hash)
- `references/supabase-schema-and-migrations.md` — Postgres/Supabase work without Dashboard access: REST column/type/emptiness probes, idempotent delta patterns, FK-existence guard, the Supabase rate-limit trigger, pglast verification of a migration before hand-off, local embedded-PostgreSQL verification of trigger/RLS/RPC semantics (auth.users + anon/authenticated roles, `set role` for RLS, sentinel-wrapped steps), and admin-RPC ACL hygiene