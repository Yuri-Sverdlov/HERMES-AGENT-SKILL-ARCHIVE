---
name: hermes-config-verification
description: >
  Answer "can this be fixed in Hermes settings?" by reading the installed source
  instead of guessing. Covers locating the live install, proving a config key is
  actually read (a key in DEFAULT_CONFIG with no reader is a no-op), finding
  hardcoded keybindings, and scoping version-specific findings so they don't
  harden into permanent claims. Use when the user asks whether a behaviour is
  configurable, reports a setting that "doesn't work", or wants a shortcut /
  toggle changed.
---

# Verifying Hermes behaviour before promising a setting

The user asks a yes/no question — *"это можно исправить в настройках?"*. The honest
answer requires three facts, and guessing any of them produces a confidently wrong
reply: (1) does the option exist, (2) is anything actually **reading** it in the
installed build, (3) is the behaviour hardcoded somewhere else. Read the source.

`hermes-agent` (bundled) is the operating guide and is protected — this skill is the
diagnostic companion for when it does not answer a specific "is X configurable".

## Locate the live install first

```bash
hermes --version            # version + upstream commit + project dir
```
It prints `Project: C:\Users\<user>\AppData\Local\hermes\hermes-agent` — that tree, not
the docs, is what your user is actually running. Docs describe the live/main branch and
routinely contain features the local build lacks (and vice versa).

| Path | What lives there |
|---|---|
| `hermes_cli/config.py` | `DEFAULT_CONFIG` — the config schema / all defaults |
| `cli.py` | interactive CLI, prompt_toolkit `KeyBindings` |
| `apps/desktop/src/` | Electron desktop app (React); rebindable hotkeys |
| `ui-tui/src/` | TUI; reads config via `app/useConfigSync.ts` |
| `website/`, `/docs` on the web | documentation (live, may be ahead) |

## The core check: schema hit ≠ wired option

A key appearing once, in `DEFAULT_CONFIG`, means only that it is *declared*. Proven
method:

```bash
grep -rn "the_option_name" <install>/ --include=*.py
# then the same across the non-Python surfaces:
grep -rn "the_option_name" <install>/apps <install>/ui-tui/src <install>/web/src
```

- **One hit, in `config.py` only → the key is a no-op in this build.** Setting it changes
  nothing. Say so explicitly rather than letting the user try it.
- Hits in TS/TSX (`useConfigSync.ts`, `gatewayTypes.ts`) mean the TUI owns that setting
  even though no Python reads it — the Python grep alone would have produced a false
  "dead option" verdict.
- Two or more hits across a reader + the schema = genuinely wired.

The `hermes-agent` skill's own rule applies: absence of a mention is not evidence of
absence — grep before saying no.

## Behaviour is often hardcoded, and that is the real answer

When the option is dead, find where the behaviour actually lives and describe it:

- CLI key semantics live in `cli.py` as `@kb.add('c-x')` handlers. Ctrl+C is
  interrupt/exit, not copy, by design; terminal-native chords (Ctrl+Shift+C) never reach
  prompt_toolkit because the emulator consumes them first.
- The desktop app's hotkeys are data, not code: `apps/desktop/src/lib/keybinds/actions.ts`
  is the single source of truth for every rebindable action, and
  `store/keybinds.ts` overlays stored overrides. Read `defaults:` there to answer "is this
  key bound at all?" — a key with no entry is handled by the OS/browser normally.
- Slash commands are the supported escape hatch when a chord is taken (e.g. `/copy [N]`).

## Report shape

State the answer in one line first, then a table (`surface | behaviour | configurable?`).
Close with what *would* change it: an upgrade, a real setting that does apply, or
"needs a code change". Offer the verification, do not just assert it.

## Pitfalls

- **Do not turn a version-specific finding into a permanent claim.** "Option X is dead"
  is true of the build you grepped and may be false after `hermes update`. Always record
  the version/commit you checked against, and re-verify after an update. Never phrase it
  as "Hermes cannot do X".
- **Answer before you dig.** The user asked a question, not for an archaeology report.
  Send a one-line answer or «проверяю, отвечу через N минут» before the first grep.
- **The docs site is not the install.** When they disagree, the install wins for "what
  does my user have", the docs win for "what is the current supported behaviour" — say
  which one you are quoting.
- **Check both Python and TS before declaring an option dead** (see core check above).
- Findings, tables and grep output for keyboard/copy behaviour:
  `references/keybindings-and-copy.md`.
