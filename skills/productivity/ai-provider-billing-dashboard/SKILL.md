---
name: ai-provider-billing-dashboard
description: "Build a local dashboard tracking balance/spend across AI providers (OpenRouter, Anthropic, ...). Which providers expose balance via API vs. need manual entry, the exact endpoints, and a stdlib-only localhost server pattern."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [billing, balance, openrouter, anthropic, dashboard, cost-tracking, api]
    related_skills: [hermes-model-switching]
---

# AI Provider Billing / Balance Dashboard

Use when a user wants to see remaining credit, spend, and top-up history across
their AI providers (OpenRouter, Anthropic, and more added later) in one place —
typically a small local web dashboard.

## FIRST: which providers actually expose balance? (probe before building)

Do NOT assume an API exists. The single biggest design fact: **providers differ
wildly in what billing data they expose.** Probe each one before promising
features. Known state (verify, it changes):

| Provider | Balance via API? | Endpoint / note |
|---|---|---|
| **OpenRouter** | ✅ YES | `GET https://openrouter.ai/api/v1/credits` → `{data:{total_credits, total_usage}}`. Remaining = total_credits − total_usage. Auth: `Authorization: Bearer <key>`. Also `GET /api/v1/key` gives per-key usage (daily/weekly/monthly). |
| **Anthropic** | ❌ NO balance endpoint exists | There is NO "remaining balance" API, even with an Admin key. Admin key (`sk-ant-admin...`, created in Console → Settings → Admin Keys, owner-only) only gives **spend** via `GET /v1/organizations/cost_report?starting_at=<ISO>` (header `anthropic-version: 2023-06-01`). A normal `x-api-key` returns 401 on org endpoints. → Remaining must be computed as (manual top-ups) − (spend). |
| OpenAI | ⚠ check | Historically no simple balance endpoint for prepaid; usage via dashboard/Admin. Probe before relying. |

**Consequence for the design:** the dashboard is a HYBRID — auto-fetch where an
API gives balance/spend, manual top-up ledger everywhere else. Build the manual
ledger from day one; it's not a fallback, it's required for Anthropic.

See `references/provider-billing-endpoints.md` for tested request/response
snippets and the exact probe commands.

## Architecture that worked (stdlib-only localhost server)

Chosen over a single static HTML file because secret API keys must NOT reach the
browser. Pattern:

- `server.py` — Python **stdlib only** (`http.server.ThreadingHTTPServer`,
  `urllib.request`). No pip installs → runs anywhere Python is. Binds
  `127.0.0.1` only (never exposed off-host). Serves `index.html`, plus JSON
  endpoints `/api/data` (GET, returns balances + payments), `/api/payment`
  (POST add), `/api/payment/delete` (POST). Keys read server-side from env vars
  first, then a Hermes `.env` path from `config.json` — keys stay in Python.
- `index.html` — fetches `/api/data`, renders provider cards + a top-up table
  with an add form. No secrets in the page.
- `payments.json` — the manual top-up ledger (provider/date/amount/note).
- `config.json` — points at the `.env` (default `~/AppData/Local/hermes/.env`)
  and documents the optional `ANTHROPIC_ADMIN_KEY` for auto-spend.
- `start.bat` (Windows) — double-click launch.

A ready-to-copy `server.py` is in `templates/billing_server.py` (already correct:
1d buckets, cents→dollars ÷100, two-wallets model, paginated+cached+backoff,
`allow_reuse_address`, graceful port-busy). A matching self-healing Windows
launcher is in `templates/start.bat` (kills stale port-holder + auto-opens
browser). The "add a new provider" extension point is a `fetch_<provider>(keys)`
function appended to the `build_data()` provider list.

## Design principles (carry these forward)

1. **Design for the missing key.** Anthropic spend only works with an Admin key
   the user may not have yet. Ship a working "slot": no key → manual mode
   (remaining = top-ups), key present → auto-spend. No rewrite needed when the
   key arrives later.
2. **Verify the balance live before claiming success.** Hit `/api/data` and
   confirm real numbers (e.g. OpenRouter remaining) — don't just start the
   server and declare victory.
3. **Be honest about Anthropic's limit.** Tell the user up front: even with the
   Admin key, "remaining" is always top-ups − spend, because Anthropic has no
   balance API. Set expectations so the manual ledger isn't seen as a bug.
4. **localhost only + .gitignore the secrets** (`.env`, optionally the real
   `payments.json`).

## Anthropic cost_report: pagination + a brutal rate limit (learned the hard way)

Two traps that will silently corrupt the spend number or get you 429'd:

1. **The response is PAGINATED.** `cost_report` returns `{data:[...], has_more,
   next_page}`. Reading only the first page gives a wrong (often $0) total. You
   MUST loop on `has_more`/`next_page`. Use `&limit=31` to pack ~31 daily buckets
   per page; over ~100 days that's ~4 pages.
   ⚠️ **`bucket_width` ONLY accepts `1d`.** `1month` (and anything but `1d`)
   returns HTTP 400 `invalid_request_error: "bucket_width: Input should be '1d'"`.
   An earlier version of this skill wrongly recommended `1month` — do NOT use it.
   Bound the window instead (e.g. last 100 days) to keep page count low.
2. **The endpoint rate-limits HARD (HTTP 429).** A handful of back-to-back
   diagnostic calls exhausted the limit for what felt like an hour — even 2-min
   waits still returned 429. This is org-billing throttling, not a code bug.
   Therefore the production fetch MUST:
   - cache the spend total in-process with a TTL (5 min worked) so the dashboard
     refresh button doesn't re-hit the API every click;
   - retry 429 with exponential backoff (e.g. 5s, 10s, 15s, 20s, then give up);
   - on giving up, degrade gracefully: show remaining = top-ups and a clear
     "429, try again later" note — never crash the server.
   The fixed `templates/billing_server.py` already does paginated +
   1d-bucket (`limit=31`, ~100-day window) + cents→dollars (÷100) + cached +
   backoff. While DEVELOPING, do NOT spam the endpoint
   to "verify" — one probe, then trust the code; extra probes burn the limit and
   leave you unable to demonstrate it working.

## Launcher hardening (stale-process & UX, learned this session)

A long-lived localhost server bites you on restart: a second `start.bat` (or any
re-launch) leaves the OLD process still bound to the port answering with STALE
code, while the new process silently fails to bind. Symptom seen: dashboard kept
showing a wrong number (`-$360`) from an old process + its 5-min cache even after
the code was fixed — the new server never took the port. Make the launcher
self-healing:

1. **Kill whatever holds the port before starting.** ⚠️ **Prefer PowerShell, not
   `netstat | findstr`.** The `netstat`/`findstr` one-liner SILENTLY found nothing
   in one user's environment (Git-Bash/cmd locale mismatch), so the old process
   survived and the new one couldn't bind — the classic "stale -$360 number won't
   go away" symptom. PowerShell `Get-NetTCPConnection` is reliable:
   ```bat
   powershell -NoProfile -Command "$p=(Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"
   ```
   (Keep the `netstat`/`taskkill` form only as a fallback for boxes without the
   NetTCP cmdlets.) Either way every launch becomes idempotent — a double-click
   can't pile up zombie servers. When DEBUGGING a "won't update" dashboard, kill
   ALL stale `python server.py` first: `Get-CimInstance Win32_Process -Filter
   "name='python.exe'" | Where-Object {$_.CommandLine -like '*server.py*'} |
   ForEach-Object { Stop-Process -Id $_.ProcessId -Force }` — several old copies
   from earlier launches can be hiding, each holding the port in turn.
2. **Auto-open the browser after a short delay** (server needs ~2-3 s to bind),
   in a detached shell so it doesn't block the server's foreground loop:
   ```bat
   start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%"
   ```
3. **Second line of defence in `server.py`:** set `allow_reuse_address = True`
   on the server class, and wrap `serve_forever()` to catch `OSError`
   (WinError 10048 = port busy) → print a friendly "already running, open
   http://localhost:PORT or close the other window" instead of a raw traceback.
4. **Stale cache caveat:** if the server caches provider data in-process (TTL),
   a *running* old process keeps serving the cached old value; killing+restarting
   (step 1) is what actually clears it. A browser Ctrl+F5 only fixes a stale
   *page*, not stale *server* state.

## Pitfalls

- 🚨 **Keep `start.bat` ASCII-only — Cyrillic (or any non-ASCII) in a `.bat`
  breaks cmd.exe.** A launcher with Russian comments/echo lines produced a
  cascade of `'indstr' is not recognized`, `'нды...' is not recognized`,
  `'ost:' is not recognized` errors: cmd reads the file bytes before `chcp`
  takes effect and mis-tokenizes the mangled text as commands. `chcp 65001`
  inside the file does NOT save you. Write all `.bat` comments and `echo`
  messages in plain English ASCII; put any localized text in the served HTML,
  never in the batch file.
- **Serve it; never open `index.html` as a `file://` double-click.** The page
  fetches `/api/data` from the local server, so opening the bare file shows an
  endless "Loading…" with a dead refresh button (the user's exact symptom). The
  fix is always: run `python server.py` (or `start.bat`), then browse to
  `http://localhost:<port>` — the address, not the file path.
- Don't probe with a guessed env-var name. Read the real key source from
  `auth.json` `credential_pool[provider][].source` (e.g. `env:OPENROUTER_API_KEY`)
  or the Hermes `.env`, then use that exact name.
- OpenRouter `total_credits` is lifetime deposited, `total_usage` is lifetime
  spent — remaining is the difference, not `total_credits` alone.
- Anthropic org endpoints reject the normal API key with 401
  `authentication_error` — that's the wrong key type, not a bad key; you need the
  Admin key.
- Anthropic cost_report `results[].amount` is a STRING (e.g. `"3.353475"`) — cast
  to float before summing.
- 🚨 **Anthropic cost_report `amount` is in CENTS, not dollars.** Divide by 100.
  Skipping this inflates spend 100× (one session showed $37,059 where the real
  figure was ~$370). Sanity-check: independently sum tokens via
  `GET /v1/organizations/usage_report/messages` and price them by hand
  (Sonnet ≈ $3/M in, $15/M out, $0.30/M cache-read, $3.75/M cache-write) — the
  hand estimate should match `cost_report_sum/100`, confirming the cents unit.
- 🚨 **`cost_report` is TOTAL org usage, NOT API-balance drawdown — they are
  TWO DIFFERENT WALLETS.** It includes Claude Code / Max-plan subscription usage,
  which is billed by the plan, not deducted from the prepaid API balance. So
  `remaining = top_ups − cost_report` is WRONG and can go absurdly negative.
  Correct model: API-balance remaining = manual top-ups (Anthropic gives no
  balance API); show `cost_report` spend as a SEPARATE "usage (reference, by API
  prices)" line, not subtracted from the balance. This is the "Variant 2 / two
  wallets" layout. The dollar value of subscription usage (what tokens *would*
  cost at API rates) is much higher than the flat subscription fee the user
  actually pays — label it clearly so the user isn't alarmed.
- **`group_by[]=model` is NOT valid** on cost_report (returns 400); valid
  group_by values are `description`, `workspace_id`. To see which org a key
  belongs to / investigate "whose spend is this", use Admin endpoints:
  `/v1/organizations/me` (org id+name), `/v1/organizations/users` (members+roles),
  `/v1/organizations/workspaces`, `/v1/organizations/api_keys`. An Admin key is
  org-scoped, so "unfamiliar org" spend is usually the user's own org (e.g. a
  Claude Code workspace), confirmable via `/me` + `/users`.
