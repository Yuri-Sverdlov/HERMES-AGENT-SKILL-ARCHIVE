# Stop conditions — when to halt and ask Yuri

Exhaustive list of situations where the agent MUST stop the current action, surface the issue in 1-2 lines, and wait for explicit confirmation before proceeding. Ordered by severity.

## S0 — Security / secrets (HARD STOP)

**Trigger:** Yuri pastes, types, or includes in a code block any string that looks like a credential.

**Patterns to watch:**
- `sk-...`, `sk-ant-...`, `sk-proj-...` (OpenAI, Anthropic, OpenRouter, Moonshot, Kimi, etc.)
- `ghp_...`, `gho_...`, `ghu_...`, `ghs_...`, `ghr_...` (GitHub PATs)
- `xox[abp]-...` (Slack)
- `AIza...` (Google API key)
- `eyJ...` (JWT, 100+ chars of base64)
- `***` (Telegram bot tokens: `123456:AAFZ...`)
- `AAA...` or `BBB...` patterns of 35+ base64-url chars
- Anything explicitly labelled "API key", "token", "secret", "password" in context

**Action:**
1. One-line warning only — no analysis, no restatement.
2. Do NOT echo, log, commit, or include the secret anywhere.
3. Tell Yuri the rotation URL (where to revoke: platform.openai.com, github.com/settings/tokens, @BotFather, etc.).
4. Ask Yuri to put the new secret directly in the right `.env` file, not in chat.
5. Do not proceed with the original task until rotation is confirmed.

**Anti-pattern:** "I see you sent sk-proj-6Y-VVNP1LOIbWqld-... — I'll use that to set up STT..." (NEVER).

## S1 — Irreversible / destructive action (CONFIRM FIRST)

**Trigger:** any of the following without explicit "do it" confirmation.

- `git push` to a non-local branch
- `git push --force` or any force-push
- `rm -rf` on a non-temp path
- `DROP TABLE` / `DROP DATABASE`
- Deleting files outside `node_modules`, `__pycache__`, `.git`, `dist`, `build`
- Modifying system files (`/etc/`, `C:\Windows\`, registry)
- Closing or terminating a long-running service
- Publishing to npm, PyPI, Docker Hub
- Sending a real email, message, or HTTP request to a non-test endpoint

**Action:** Show what will happen in 1-2 lines, ask "делаем?", wait.

## S2 — Blocked by missing setup (ASK, DON'T GUESS)

**Trigger:** tool, path, or service that the agent assumes exists but is not present.

Examples:
- `sqlite3` CLI not in PATH → use Python `sqlite3` module, don't install
- `pytest` not installed → write standalone test runner, don't `pip install` without asking
- Path mismatch (native vs WSL) → ask Yuri which one applies, don't guess
- API key missing in `.env` → tell Yuri exactly which env var to set, don't ask for the value in chat

**Action:** State what's missing, propose a workaround, ask "так пойдёт?" before running anything that modifies the system.

## S3 — Ambiguity in instruction (ASK, DON'T INFER)

**Trigger:** Yuri's instruction is unclear or could mean 2+ different things.

Examples:
- "перенеси в облако" — which project? which cloud? from which PC?
- "обнови" — update what, to which version?
- "почини" — which file, which error?
- "сделай как в прошлый раз" — no past context available, or 2+ matches

**Action:** List the interpretations in 1-2 lines each, ask Yuri to pick. Do NOT pick the most likely one and proceed.

## S4 — Output exceeds expectations (ASK BEFORE EXPANDING)

**Trigger:** Yuri asked for X, but to do X properly the agent needs to also do Y, Z.

Examples:
- Yuri asks "set up Telegram bot" → to do this, agent also needs to add the user ID to whitelist, configure STT, set up systemd, etc. → ask before doing those.
- Yuri asks "export emails" → to do this, agent also needs to set up OAuth, install dependencies, etc. → ask first.

**Action:** State the full scope in 3-5 bullets, ask "всё делаю или только X?".

## S5 — Output smaller than expected (REPORT, DON'T SILENTLY TRUNCATE)

**Trigger:** Yuri asks for "all of X" but agent only found some.

Examples:
- "find all chats about X" → found 1, but a deeper search might find more.
- "list all files" → got 20, but 200 exist.

**Action:** Report what was found, mention that the search may not be exhaustive, ask "углубить поиск?".

## S6 — Test failure (REPORT, DON'T PATCH WITHOUT PERMISSION)

**Trigger:** A test fails or a tool returns an error.

**Action:**
1. Report the failure in 1-2 lines (what failed, what was the error).
2. Propose 1-2 fix options, NOT just "I'll fix it".
3. Ask Yuri to pick, then proceed.

**Anti-pattern:** "Test failed. Patching... Done." (silently rewrites code without confirmation).

## S7 — Cross-PC confusion (ASK, DON'T ASSUME)

**Trigger:** Yuri references another PC, sync, or remote state.

Examples:
- "на втором ПК" → which second PC? PC1 + PC2? different repo?
- "проверь на сервере" → which server, accessed how?

**Action:** Ask which project / which PC / which access method. Use `git remote -v` to ground the question.

## S8 — Long task in progress (REPORT EACH STEP, DON'T BATCH)

**Trigger:** task will take > 2 minutes or > 3 sub-steps.

**Action:** Report progress every 1-2 minutes. Don't disappear into a 10-minute execution and surface only at the end.

---

## Quick decision tree

```
User message received
  │
  ├─ Contains secret pattern? ──── YES ──→ S0 (HARD STOP, warn, wait)
  │
  ├─ Asks for irreversible action without "do it"? ── YES ──→ S1 (ask)
  │
  ├─ Blocked by missing tool/path/key? ── YES ──→ S2 (propose workaround, ask)
  │
  ├─ Instruction ambiguous? ── YES ──→ S3 (list interpretations, ask)
  │
  ├─ Scope larger than user asked? ── YES ──→ S4 (propose full scope, ask)
  │
  ├─ Result smaller than user asked? ── YES ──→ S5 (report, offer deeper search)
  │
  ├─ Encountered test failure / error? ── YES ──→ S6 (report, propose fixes, ask)
  │
  └─ Otherwise: proceed, but if task > 2 min ──→ S8 (report progress)
```
