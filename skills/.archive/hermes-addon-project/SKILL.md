---
name: hermes-addon-project
description: "Create standalone addon projects that extend Hermes Agent — using internal APIs, patching CLI, and setting up cron monitoring."
---

# Hermes Addon Project

Template for creating a self-contained addon/extension to Hermes Agent that:
- Uses Hermes internal APIs (SessionDB, InsightsEngine, usage_pricing)
- Patches `cli.py` to add new output to `/usage`
- Sets up cron jobs for periodic monitoring
- Ships as an installable project with its own config

## Project Structure

```
my-addon/
├── README.md
├── TASK.md
├── config.yaml            # User-editable config
├── core_module.py         # Main logic using Hermes APIs
├── monitor_script.py      # Cron-compatible check script
├── install.py             # Setup: patch + cron
├── patches/
│   └── patch_cli.py       # cli.py patcher
└── tests/
```

## Accessing Hermes Internal APIs

These modules are available from the Hermes installation at `~/AppData/Local/hermes/hermes-agent/`:

```python
from hermes_state import SessionDB
from agent.usage_pricing import estimate_usage_cost, CanonicalUsage
from agent.insights import InsightsEngine
```

### Getting Today's Cost

```python
from datetime import datetime, timezone

def _today_start_utc() -> float:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

db = SessionDB()
conn = db._conn
cursor = conn.execute("""
    SELECT id, model, input_tokens, output_tokens, cache_read_tokens,
           cache_write_tokens, billing_provider, billing_base_url
    FROM sessions WHERE started_at >= ?
""", (_today_start_utc(),))
sessions = [dict(row) for row in cursor.fetchall()]
db.close()
```

### Estimating Cost Per Session

```python
def estimate_cost(session: dict) -> float:
    usage = CanonicalUsage(
        input_tokens=session.get("input_tokens") or 0,
        output_tokens=session.get("output_tokens") or 0,
        cache_read_tokens=session.get("cache_read_tokens") or 0,
        cache_write_tokens=session.get("cache_write_tokens") or 0,
    )
    result = estimate_usage_cost(
        session.get("model") or "",
        usage,
        provider=session.get("billing_provider"),
        base_url=session.get("billing_base_url"),
    )
    return float(result.amount_usd or 0.0)
```

**IMPORTANT:** Run your scripts with the Hermes venv Python:
```bash
PYTHONPATH="$HOME/AppData/Local/hermes/hermes-agent" \
  "$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/python" \
  my_script.py
```

## Patching cli.py

### Finding the Right Insertion Point

1. Search for `def _show_usage` in `cli.py` to find the method
2. Identify the exact spot after session token usage block and before Account limits
3. Use `patch` tool with `old_string`/`new_string` — NOT sed/heredoc

### Patch Pattern

```python
# In the patcher script:
INSERT_AFTER = 'print(f"  Compressions:     {compressions}")'
INSERT_BEFORE = "# Account limits -- fetched off-thread"

TODAY_BLOCK = '''
        # ── My custom block ──
        sys.path.insert(0, r"{project_dir}")
        try:
            from my_module import my_func
            data = my_func()
            print(data)
        except Exception as exc:
            logger.debug("My-block error: %s", exc)
        finally:
            if r"{project_dir}" in sys.path:
                sys.path.remove(r"{project_dir}")
        # ── End my block ──
'''

# Apply: replace the gap between INSERT_AFTER and INSERT_BEFORE
marker = INSERT_AFTER + "\n\n        " + INSERT_BEFORE
replacement = INSERT_AFTER + TODAY_BLOCK + "\n        " + INSERT_BEFORE
content = content.replace(marker, replacement, 1)
```

**Always backup the original:** `shutil.copy2(cli_path, cli_path + ".orig")`

## Setting Up Cron Monitoring

### Copy Scripts

Cron scripts must live under `~/.hermes/scripts/` (relative path in `--script`):

```bash
mkdir -p ~/.hermes/scripts/
cp my_monitor.py ~/.hermes/scripts/
```

### Create Cron Job

```bash
hermes cron create "30m" \
  --name "my-monitor" \
  --deliver "origin" \
  --script "my_monitor.py" \
  --no-agent \
  --workdir "G:/path/to/project"
```

- `--no-agent`: run script directly, no LLM, deliver stdout verbatim
- `--deliver origin`: send output to the current chat session
- Empty stdout = silent run (no delivery)
- Non-empty stdout = delivered as message

### Cron Script Contract

```python
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from my_core import check_condition

result = check_condition()
if result["triggered"]:
    print(result["warning_message"])  # delivered to chat
    sys.exit(1)
# else: silent exit 0 — nothing delivered
```

## Config Pattern

```yaml
# config.yaml — next to the scripts
daily_budget: 2.0
warn_at_percent: 75
check_interval_minutes: 30
```

## Install Script Pattern

```python
# install.py — applies patch + creates cron
import subprocess, sys, os, shutil

HERMES_SCRIPTS = os.path.expanduser(r"~/AppData/Local/hermes/scripts")

# 1. Copy scripts
os.makedirs(HERMES_SCRIPTS, exist_ok=True)
shutil.copy2("my_module.py", os.path.join(HERMES_SCRIPTS, "my_module.py"))

# 2. Apply CLI patch
subprocess.run([sys.executable, "patches/patch_cli.py", "apply"])

# 3. Create cron job
subprocess.run(["hermes", "cron", "create", "30m",
    "--name", "my-monitor",
    "--deliver", "origin",
    "--script", "my_monitor.py",
    "--no-agent",
])
```

## Pitfalls

- **cli.py from `main` branch ≠ installed version.** If you restore cli.py from GitHub `main`, it may differ from the installed pip version. Always backup before patching.
- **Backup corruption.** `patch.py` restore logic must copy FROM backup TO original, not the reverse. Test the revert path.
- **sys.path pollution.** Always clean up inserted paths in `finally` block.
- **Cron script path.** Must be relative to `~/.hermes/scripts/`. Absolute paths outside that dir fail.
- **Hermes venv Python.** Don't use `python3` from PATH — use the Hermes venv Python at `~/AppData/Local/hermes/hermes-agent/venv/Scripts/python`.
- **PYTHONPATH.** Add `~/AppData/Local/hermes/hermes-agent` to PYTHONPATH for Hermes imports.

## Verification

```bash
# Test the core module directly
PYTHONPATH="$HOME/AppData/Local/hermes/hermes-agent" \
  "$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/python" \
  -c "from my_module import my_func; print(my_func())"

# Test cron script
PYTHONPATH="$HOME/AppData/Local/hermes/hermes-agent" \
  "$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/python" \
  my_monitor.py --json

# Check cron job
hermes cron list

# Check CLI syntax after patch
python -c "import py_compile; py_compile.compile('path/to/cli.py', doraise=True)"
```

## Windows Bat-File for Quick Checking

When the user wants a double-click convenience shortcut:

```batch
@echo off
title My Addon Report
color 0A

set "HERMES_DIR=%USERPROFILE%\AppData\Local\hermes\hermes-agent"
set "PYTHON=%HERMES_DIR%\venv\Scripts\python.exe"
set "PYTHONPATH=%HERMES_DIR%"
set "SCRIPT_DIR=%~dp0"

"%PYTHON%" "%SCRIPT_DIR%show_report.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error. Check paths.
    pause
)
```

The Python script (`show_report.py`) must end with `input()` to keep the window open:

```python
print("Нажми Enter для выхода...")
input()
```

User can create a desktop shortcut pointing to the `.bat` file.

## GUIDE.md — User Guide for New Users

After building the project, create a `GUIDE.md` that covers:

1. **Purpose** — why this project exists
2. **Functionality** — what each component does
3. **Visual examples** — what warnings look like in terminal vs chat
4. **How to use the bat file** — double-click instructions
5. **Configuration** — how to change settings
6. **Project structure** — file-by-file explanation
7. **FAQ** — common questions
8. **Future extensions** — ideas for later

This is separate from README.md (brief) and TASK.md (implementation plan).

## Treat .md files as Windows-native

Yuri's Markdown reader decodes BOM-less UTF-8 as Windows-1251 → mojibake.
**Every `.md` file must be saved with UTF-8 BOM (utf-8-sig).**

`write_file` tool writes BOM-less UTF-8. After writing any .md:

```python
# Verify and fix BOM
with open(path, 'rb') as f:
    first3 = f.read(3)
if first3 != b'\xef\xbb\xbf':
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write(content)
```

Or use `execute_code` to write with `encoding='utf-8-sig'` from the start.

## Config auto-read from script directory

The monitor script should read `config.yaml` from its own directory:

```python
import os
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.yaml")

def load_config():
    import yaml
    defaults = {"daily_budget": 2.0, "warn_at_percent": 75}
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            defaults.update(yaml.safe_load(f) or {})
    return defaults
```