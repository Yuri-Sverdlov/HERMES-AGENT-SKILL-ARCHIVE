# Telegram Gateway Setup — Verified Working Sequence (2026-07-24)

Session transcript from the first successful Telegram→Hermes wiring on PC1 (native Windows install). Use as a reference for re-doing this on a new machine.

## Goal
Connect a Telegram bot to Hermes Agent on Windows native. Bot accepts text + voice. Only the user (numeric ID 1366880510) can talk to it. Whitelist enforced. Voice messages transcribed and acted on.

## What worked (in order)

### 1. Create bot via @BotFather
- Open Telegram, message `@BotFather`
- `/newbot` → provide name and username (e.g. `@yurisv_bot`)
- Receive token: `8702434224:AAFZbQ9-...` (real format: `<digits>:<35 chars>`)

### 2. Find your Telegram numeric user ID
- Message `@userinfobot` from your own Telegram account
- It replies with your ID: `1366880510`
- **Username is not enough for whitelist** — need the numeric ID

### 3. Place token in .env
Native Hermes install on Windows reads from `C:\Users\Yuri\AppData\Local\hermes\.env`.

**Do NOT** put it in `C:\Users\Yuri\.hermes\.env` — different folder, Hermes ignores it.

Edit the file, add (uncommented):
```
TELEGRAM_BOT_TOKEN=8702434224:AAFZbQ9-...
TELEGRAM_ALLOWED_USERS=1366880510
```

On Linux/WSL the path is `~/.hermes/.env` (same key names).

### 4. Verify Hermes can see it
```
hermes --cli -z "is TELEGRAM_BOT_TOKEN set? say yes or no"
```
The agent reads from internal channel. If response is "no", check the path and that the line is uncommented (no leading `#`).

### 5. Register Telegram slash commands (optional, see warning)

The agent uses Telegram Bot API to register command list. This is a **menu placeholder only** — it does NOT wire handlers.

```python
import json, urllib.request
token = "..."  # read from .env
commands = [
    {'command': 'expense', 'description': 'Record expense'},
    {'command': 'budget',  'description': 'Set budget'},
    {'command': 'summary', 'description': 'Show summary'},
    # ...
]
req = urllib.request.Request(
    f'https://api.telegram.org/bot{token}/setMyCommands',
    data=json.dumps({'commands': commands, 'scope': {'type': 'all_private_chats'}}).encode(),
    headers={'Content-Type': 'application/json'}
)
urllib.request.urlopen(req, timeout=15)
```

**WARNING:** These commands appear in the bot menu but Hermes returns "Unknown command /expense" when user types them. They are visual placeholders, not handlers. Don't rely on them for actual workflow.

### 6. Restart the gateway (the tricky part)

`hermes gateway restart` is **blocked from inside the gateway process** (SIGTERM would kill the command itself). Two patterns worked:

**Pattern A (separate terminal):**
```powershell
Stop-Process -Name "hermes" -Force
hermes gateway run --replace
```

**Pattern B (detached from inside the same agent):**
```powershell
Start-Process -FilePath 'hermes' -ArgumentList 'gateway','run' -WindowStyle Hidden
```
Wait 4-5 sec, check `C:\Users\Yuri\AppData\Local\hermes\logs\gateway.log` for `✓ telegram connected`.

### 7. Verify
- `hermes gateway status` → `Gateway process running (PID: ...)`
- `hermes gateway list` → `✓ default (current)`
- `tail logs/gateway.log` → `✓ telegram connected`
- Send `/start` to bot in Telegram → bot responds with welcome or ignores it (this is normal — `/start` is a platform ping)
- Send "привет" → bot replies
- Send voice message → log shows STT cache + bot replies

## What didn't work / surprised us

1. **First try of `hermes gateway restart` from inside the gateway → blocked**. Error: "cannot restart from inside the gateway process."
2. **`Stop-Process -Name "hermes"` didn't kill the gateway** — it runs under a different process name. Used `Start-Process` to spawn a new one instead.
3. **`hermes gateway run --replace` from a `terminal()` call timed out at 60s** — because the call IS the gateway, which never returns. Solution: spawn detached, then verify via log.
4. **OpenAI key sent in chat was treated as compromised** — the moment any secret hits the chat history (DB, log, sync), it must be revoked. The user did this correctly.
5. **User initially placed token in `C:\Users\Yuri\.hermes\.env` (wrong folder)** — Hermes didn't see it. Moved to `C:\Users\Yuri\AppData\Local\hermes\.env`.

## The voice-to-action gap

We verified that voice messages DO get transcribed by STT (faster-whisper, works out of the box). But:

- "Купил кофе за 25 шекелей" → transcribed as "Opile Coff is at 25 shakily"
- Hermes did NOT auto-route to the custom `home-accounting` skill
- Instead it proposed writing a Python CSV script via `terminal`
- After Deny, the agent safety-refused (no further response)

**Conclusion:** For now, voice → meaningful action in Telegram requires either:
- A wrapper script that the user (or a forced Hermes prompt) invokes explicitly
- Or a custom slash command handler (not yet available in Hermes v0.17.0 out of the box)

CLI mode (`hermes --cli -z "..." --skills "home-accounting"`) is 100% reliable for testing the skill logic — that's how T1–T10 passed.

## Time spent
~1 hour total (Telegram bot creation → whitelist → gateway restart → text working → voice working).
