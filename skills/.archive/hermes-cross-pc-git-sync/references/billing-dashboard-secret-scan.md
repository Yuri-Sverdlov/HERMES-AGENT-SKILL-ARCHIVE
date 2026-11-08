# Billing dashboard — secret-scan results (2026-06-26)

Folder: `G:/_My_Programming/HERMES-AGENT/HERMES-BILLING-DASHBOARD/`

Scanned before considering it safe to push to the (now private) hub repo.

## Files present
- `.gitignore` — ignores `.env`, `*.key`, `__pycache__/`, `*.pyc`.
  `payments.json` is listed but COMMENTED OUT ("uncomment if repo public").
- `config.json` — only `hermes_env_path` pointer + a comment. **No keys.** Safe.
- `payments.json` — real spend history ($10 Anthropic 2026-06-26, $12 OpenRouter).
  Personal financial data. Decide with user whether to track or gitignore.
- `index.html`, `server.py`, `start.bat`, `README.md`.

## server.py key handling — SAFE
`grep -niE 'sk-|api_key|secret|token|password' server.py` showed only:
- a `load_api_keys()` that reads from **env vars first, then ~/.../hermes/.env**;
- `wanted = ["OPENROUTER_API_KEY","ANTHROPIC_API_KEY","ANTHROPIC_ADMIN_KEY"]`.
No hardcoded secrets. Keys live in env / the hermes profile `.env`, never in code.

## `.env` files in tree
`find ... -iname '*.env' -o -iname '.env*'` → **none**. Good — secrets are not
inside the project dir.

## Verdict
Code is clean to push. Two decisions to surface to the user before commit:
1. `payments.json` — track (private repo) or gitignore (personal $$).
2. Confirm root `.gitignore` of the hub repo also blocks `.env`/`*.key` so a future
   stray key never reaches even a private repo.
