"""openrouter_balance.py - read a metered OpenRouter key's balance WITHOUT exposing the key.

    python openrouter_balance.py [--config <path>]

Reads `api.key` / `api.base_url` from a VideoLingo-style config.yaml (the fields may be
single- or double-quoted), calls GET /api/v1/auth/key and prints only non-secret fields:
label, is_free_tier, limit, usage, limit_remaining, rate_limit.

Why this shape:
  * Cost is the one quantity the dubbing pipeline never logs, so the provider balance is the
    only honest source. Run it BEFORE and AFTER a run and subtract.
  * The key is read from the config file, never taken as a CLI argument (would land in shell
    history / the process list) and never printed. Only its length is reported.
  * No absolute paths (DEV-NOTES 14.1). Console output is ASCII only (DEV-NOTES 4).

Typical use:
    <venv-python> openrouter_balance.py                 # baseline
    ... run the pipeline ...
    <venv-python> openrouter_balance.py                 # after; cost = limit_remaining delta
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path


def say(text: str) -> None:
    sys.stdout.write(str(text) + "\n")
    sys.stdout.flush()


def read_key(config_path: Path):
    """Return (api_key, base_url) from a VideoLingo config.yaml. Handles quoted values."""
    key = None
    base = "https://openrouter.ai/api/v1"
    in_api = False
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("api:"):
            in_api = True
            continue
        if in_api:
            if line and not line.startswith((" ", "\t")):
                break  # left the api: block
            stripped = line.strip()
            if stripped.startswith("key:"):
                key = stripped.split(":", 1)[1].strip().strip("'\"")
            elif stripped.startswith("base_url:"):
                base = stripped.split(":", 1)[1].strip().strip("'\"")
    if not key:
        raise SystemExit("ERROR: api.key not found in " + str(config_path))
    return key, base


def whoami(base_url: str, key: str) -> dict:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/auth/key",
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Read OpenRouter balance (no secrets printed)")
    ap.add_argument("--config", default=str(Path("config.yaml")))
    args = ap.parse_args()

    cfg = Path(args.config)
    if not cfg.is_file():
        say("ERROR: config not found: " + str(cfg))
        return 2

    key, base = read_key(cfg)
    say("config      : " + str(cfg.resolve()))
    say("base_url    : " + base)
    say("key length  : " + str(len(key)) + " chars (value NOT printed)")

    try:
        data = whoami(base, key)["data"]
    except Exception as exc:
        say("ERROR calling /auth/key: " + type(exc).__name__ + ": " + str(exc))
        return 3

    say("")
    say("label            : " + str(data.get("label")))
    say("is_free_tier     : " + str(data.get("is_free_tier")))
    say("limit (USD)      : " + str(data.get("limit")))
    say("usage (USD)      : " + str(data.get("usage")))
    say("limit_remaining  : " + str(data.get("limit_remaining")))
    say("rate_limit       : " + str(data.get("rate_limit")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
