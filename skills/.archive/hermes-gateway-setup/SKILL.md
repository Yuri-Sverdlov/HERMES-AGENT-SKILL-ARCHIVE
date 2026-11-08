---
name: hermes-gateway-setup
description: Setup and troubleshoot Hermes Agent messaging gateways (Telegram, Slack, Discord, WhatsApp, Teams, Google Chat). Covers token placement in .env, whitelist configuration, gateway restart without self-kill, voice message STT routing, and the critical lesson that Hermes does NOT auto-route voice/text to skills — slash commands are placeholders unless wired to a real handler. Use when setting up any new gateway, debugging "bot ignores my voice message", or wiring a custom Telegram command.
version: 1.0.0
platforms: [windows, linux, macos]
---

# Hermes Gateway Setup

Reference for setting up and troubleshooting messaging gateways in Hermes Agent (NousResearch). Covers Telegram primarily, plus the general pattern for Slack/Discord/Teams/WhatsApp/Google Chat.

## When to Use

- User says "set up Telegram bot", "connect Hermes to Telegram", "Telegram-бот не отвечает"
- User wants to add Slack/Discord/Teams/WhatsApp
- Voice messages reach the bot but transactions / actions are NOT recorded
- User asks about whitelist / allowed_users / security
- After `hermes gateway restart` fails with "cannot restart from inside gateway process"
- Slash commands like `/expense`, `/budget` registered via setMyCommands but bot says "Unknown command"

## Critical Lesson: Skill Routing is NOT Automatic

**Hermes does NOT auto-route voice or text messages to a specific skill based on content.** When a user sends "купил кофе за 25 шекелей" via Telegram:

1. STT transcribes the audio
2. Hermes receives the transcription as a regular message
3. Hermes **autonomously chooses** which tool/action to use
4. If multiple skills match (e.g. built-in `expense-tracker` AND custom `home-accounting`), Hermes picks **whichever it prefers** — usually the one with more training data

This means:
- A perfectly written SKILL.md with detailed triggers may still be ignored
- `hermes skills list` showing "enabled" does NOT mean the skill will be used
- The bot may instead fall back to writing a Python/CSV script via `terminal` (often the "default behaviour" for ambiguous tasks)

### Mitigation patterns

1. **Use explicit skill invocation in CLI mode**: `hermes --cli -z "..." --skills "home-accounting"` — guaranteed routing
2. **Wire slash commands to actual handlers** — `setMyCommands` alone creates placeholders, not handlers
3. **Make the skill's `description` field specific and disambiguating** so Hermes prefers it over built-ins
4. **Test in CLI first**, then validate in Telegram — don't assume CLI behaviour matches gateway behaviour
5. **If Hermes writes its own CSV/Python script** for an accounting task, that's a signal the skill wasn't auto-selected — Deny and retry with explicit instruction

## Token Placement: Where Does the .env Live?

Hermes reads `.env` from the **profile root**, not the current working directory. The path depends on install type:

| Install type | .env path | Config path |
|---|---|---|
| **Native Windows (PC1)** | `C:\Users\Yuri\AppData\Local\hermes\.env` | `%LOCALAPPDATA%\hermes\config.yaml` |
| **WSL2 (Ubuntu)** | `~/.hermes/.env` | `~/.hermes/config.yaml` |
| **VPS (Linux)** | `~/.hermes/.env` | `~/.hermes/config.yaml` |

**Common mistake**: user puts token in `C:\Users\Yuri\.hermes\.env` (a different folder Hermes does not scan). Always confirm with `hermes --cli -z "is TELEGRAM_BOT_TOKEN set? say yes or no"` — the agent reads it via internal channel, so answer reveals presence.

**After editing .env, the gateway must be restarted** to pick up new values. The process will not auto-reload.

## Gateway Restart Without Self-Kill

`hermes gateway restart` is **blocked from inside the gateway process** (SIGTERM would kill the command itself). Two safe patterns:

### Pattern A: External shell (recommended)

From PowerShell or a separate terminal (not the one running the gateway):
```powershell
Stop-Process -Name "hermes" -Force -ErrorAction SilentlyContinue
# OR by PID:
Stop-Process -Id <pid> -Force
# Then start fresh:
hermes gateway run --replace
```

The `--replace` flag tells the new gateway to take over the singleton lock and replace the old one.

### Pattern B: Detached process from inside

When `hermes` blocks the restart command, spawn a detached process:
```powershell
Start-Process -FilePath 'hermes' -ArgumentList 'gateway','run' -WindowStyle Hidden
```
Wait 4-5 seconds, check `gateway.log` for `✓ telegram connected` or similar.

### Why this matters

- `taskkill /F /PID <pid>` from inside the gateway → BLOCKED with "cannot restart from inside"
- `hermes gateway stop` from inside → also blocked
- `hermes gateway run --replace` from inside the same `terminal()` call → COMMAND TIMEOUT (the call IS the gateway, it never returns)

Always use a separate terminal or detached `Start-Process`.

## Whitelist / Allowed Users

The `TELEGRAM_ALLOWED_USERS` env var is a **comma-separated list of Telegram user IDs** (numeric, not usernames). To find your own ID:

1. DM `@userinfobot` on Telegram
2. It replies with your numeric ID like `1366880510`

Then in `.env`:
```
TELEGRAM_ALLOWED_USERS=1366880510
```

**Username is not enough** — `@yurispp` won't work for whitelist. Need the numeric ID.

**Security implication**: anyone NOT in the list gets denied silently. The log shows `Ignoring /start platform ping for session ...` for blocked users.

## Voice / STT Setup

Hermes v0.17.0+ has **STT (speech-to-text) built in** via the `faster-whisper` Python library. It is **NOT** listed in `hermes tools` CLI but is enabled by default for messaging platforms.

### Providers (priority order)

1. `local` (faster-whisper) — default, no API key needed, ~150 MB model download on first use
2. `groq` — free tier, fast
3. `openai` — paid, requires `VOICE_TOOLS_OPENAI_KEY`
4. `mistral`, `xai`, `elevenlabs` — alternatives

### Install local STT
```bash
pip install faster-whisper
```
First use downloads the model. Configure model size in `~/.hermes/config.yaml` under `stt.model`.

### Verify it works
Send a short voice message ("привет") to the bot. If transcription appears in logs:
```
[Telegram] Cached user voice at C:\Users\Yuri\AppData\Local\hermes\audio_cache\audio_*.ogg
```
…then STT is working.

## Disabling Built-in Skills (the right way)

When your custom skill competes with a built-in (e.g. your `home-accounting` vs Hermes' bundled Vietnamese `expense-tracker`) and Hermes keeps picking the wrong one, the **right** fix is NOT to delete the competitor. Use the `skills.disabled` list in `config.yaml`.

### How to disable

In `C:\Users\Yuri\AppData\Local\hermes\config.yaml` (or `~/.hermes/config.yaml` on Linux/WSL/VPS):

```yaml
skills:
  disabled:
  - expense-tracker        # frontmatter name of the skill to hide
```

The key is the **frontmatter `name`**, not the folder name. To find it:
```bash
grep -E "^name:" "%LOCALAPPDATA%\hermes\skills\<folder-name>\SKILL.md"
```

Then restart the gateway (`hermes gateway run --replace` from a separate shell) so the new config is loaded.

### Why not delete the folder?

- `hermes skills uninstall <name>` refuses on built-in skills with: `Error: '<name>' is not a hub-installed skill (may be a builtin)`. It only works for skills installed via `hermes skills install` (hub-installed skills that have a lock entry).
- Manual `rm -rf` of the folder works but `hermes update` may restore it.
- The supported, reversible way is `skills.disabled` in `config.yaml`. Survives updates, can be reverted by removing the entry.

### Auto-archive of unused built-ins

`config.yaml` may also contain `curator.prune_builtins: true`. When enabled, the **curator** (a background maintenance agent) auto-moves built-in skills that haven't been used for a while into `~/.hermes/skills/.archive/`. Hub-installed and local skills are never auto-archived. This is gentler than deletion — archived skills can be restored by moving them back.

### Verifying the disable took effect

```bash
hermes skills list | grep -i expense
# should NOT show the disabled name; your custom skill should be the only one
```

The Hermes skill-discovery code (around `tools/skills_tool.py::_find_all_skills`) skips any name in `skills.disabled` at the start of iteration, so disabled skills are never even offered to the model for selection.

## Slash Commands: Placeholders vs Real Handlers

`setMyCommands` via Telegram Bot API only sets the **command list in the bot menu**. It does NOT register handlers in Hermes.

When user types `/expense 25 cafe`, Telegram sends the message to Hermes. Hermes then needs to:
1. Recognise `/expense` as a slash command
2. Route it to a skill or custom handler
3. Execute the action

Out of the box, Hermes's slash command handling is **limited to its built-in commands** (e.g. `/start`, `/help`, `/status`, `/cancel`, plus a few platform-specific ones). Custom slash commands like `/expense`, `/budget`, `/summary` will return `Unknown command /expense. Type /commands to see what's available.`

### Workaround until custom handlers are wired

- Test functionality via `hermes --cli -z "..." --skills "skill-name"` in terminal
- Use Telegram for general conversation and "Ок, делай!" patterns where the agent invokes `terminal` to run a script
- Don't rely on custom slash commands

### Hermes's auto-registered slash command (per skill)

Each installed skill gets **exactly one** auto-registered slash command: the **slug of its frontmatter `name`**. For a skill `name: home-accounting`, the slash command is `/home-accounting` — Hermes loads the skill and passes the rest of the message as a prompt. Source: `agent/skill_commands.py::scan_skill_commands` (around line 400).

This is the only way custom-slash-like behaviour is wired today. So for `home-accounting`, `/home-accounting купил кофе за 25 шекелей` will load the skill with that text as the user message.

## Common Pitfalls

1. **`.env` in wrong location** — Hermes ignores `C:\Users\Yuri\.hermes\.env`. Use `%LOCALAPPDATA%\hermes\.env`.
2. **Token in chat** — once posted in chat, treat as compromised. Revoke via @BotFather → `/mybots` → API Token → Revoke, generate new, store directly in `.env`.
3. **Username instead of user ID** for whitelist — need numeric ID from @userinfobot.
4. **Forgetting to restart gateway** after editing `.env` — gateway caches config at startup.
5. **Trying to restart from inside the gateway** — use separate shell or `Start-Process` detached.
6. **Assuming `hermes skills list` "enabled" means "will be used"** — Hermes picks skills autonomously, may ignore yours.
7. **`tasklist | grep hermes`** — fails on Windows because grep treats it as binary. Use `powershell Get-Process` instead.
8. **Setting `OPENROUTER_API_KEY` but expecting OpenAI models** — OpenRouter routes to OpenAI, but the key format and pricing differ. Use `VOICE_TOOLS_OPENAI_KEY` for direct OpenAI (e.g. Whisper).
9. **Whisper transcription is noisy** — short phrases like "купил кофе" can come out as "Opile Coff is at 25 shakily". Always save `raw_text` for audit, don't rely on STT being clean.
10. **`hermes skills uninstall <name>` for built-ins** — refuses with "is not a hub-installed skill (may be a builtin)". Use `skills.disabled: [name]` in `config.yaml` instead. Manual `rm -rf` works but `hermes update` can restore.
11. **Disabling via folder name instead of frontmatter name** — the disabled list keys on `name:` from frontmatter, not the directory. Disable the wrong name and your competitor stays routable.
12. **Custom slash commands via `setMyCommands`** — populates only the Telegram UI menu, not the Hermes command router. To get a real command per skill, use `/<skill-name>` (the auto-registered one).
13. **No `sqlite3` CLI on Windows native install** — `hermes` runs under Python 3.11.9 but doesn't put `sqlite3.exe` on PATH. Use `python -c "import sqlite3; ..."` for ad-hoc queries against any Hermes `.db` (finance.db, state.db, etc.).

## Voice → Action Pipeline (the hard truth)

For a "voice message records an expense" workflow to work end-to-end, you need:

1. ✅ STT transcribes audio → text (works, but noisy)
2. ❌ Hermes auto-routes text to `home-accounting` skill (does NOT happen reliably)
3. ❌ Slash command `/expense` works (placeholders only)
4. ✅ Hermes invokes a Python script via `terminal` to write to SQLite (works, but script is auto-generated and not maintainable)

**Pragmatic solution**: write a `record_expense.py` wrapper script, have the user (or a thin Hermes prompt) invoke it explicitly. Don't rely on the "magical" voice-to-skill pipeline.

## Verification Checklist

After gateway setup:
- [ ] `hermes gateway status` shows `Gateway process running (PID: ...)`
- [ ] `hermes gateway list` shows `✓ default (current) — PID ...`
- [ ] Log shows `✓ telegram connected` (or platform equivalent)
- [ ] `TELEGRAM_ALLOWED_USERS=<your_id>` in `.env` (numeric ID)
- [ ] Send `/start` to bot → log shows `Ignoring /start platform ping for session agent:main:telegram:dm:<your_id>` (this is correct, not an error)
- [ ] Send regular text "привет" → bot replies
- [ ] Send voice message → log shows STT cache + bot replies
- [ ] `.env` file has `chmod 600` (Linux) or restricted ACL (Windows)
- [ ] `hermes config` shows the platform as enabled

## Related

- `email-processing` — for IMAP/SMTP-style integrations (different gateway)
- `coder-terminal-workflow` — for `hermes --cli` mode and architect/coder split
- `hermes-agent-skill-authoring` — for writing SKILL.md files that have a chance of being auto-selected (specific `description` field, explicit triggers, slash command listing)
- `cost-model-today` — uses the same `.env` location pattern for API keys
