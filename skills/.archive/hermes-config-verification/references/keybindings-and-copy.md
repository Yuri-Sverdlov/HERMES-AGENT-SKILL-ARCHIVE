# Keybindings & copy — findings from the installed source

Checked against **Hermes Agent v0.17.0 (2026.6.19), upstream 9259d1e5**, install at
`C:\Users\<user>\AppData\Local\hermes\hermes-agent`. Version-scoped: re-verify after
`hermes update` before repeating any of this.

## The question that prompted this

Yuri: Ctrl+C while trying to copy restarted/session-exited instead of copying; "можно это
исправить в настройках Гермеса?"

## Findings

| Surface | Ctrl+C behaviour | Configurable? |
|---|---|---|
| CLI / TUI | `cli.py` `@kb.add('c-c')` — cancel active prompt → interrupt agent (1st press) → clear buffer → **exit** when the buffer is empty. 2nd press within 2 s = force exit. | no — hardcoded handler |
| Desktop app | not bound by default; the global keydown listener only acts when the combo resolves in `$comboIndex`, so an unbound Ctrl+C falls through to normal copy | yes — rebindable |
| Copying generally | terminal-native gesture (drag + Ctrl+Shift+C; the emulator eats it before prompt_toolkit sees it) or the `/copy [N]` slash command | — |

### `display.copy_shortcut` is declared but dead in v0.17.0

Config schema (`hermes_cli/config.py:~1713`):

```
"copy_shortcut": "auto",  # "auto" | "ctrl_c" | "ctrl_shift_c" | "disabled"
```

Exactly **one** occurrence across the whole install. No Python reader, nothing in
`apps/desktop/src`, `ui-tui/src` or `web/src`. Setting it changes nothing in this build.
Re-grep after an upgrade — this is precisely the kind of option that gets wired later.

### `display.mouse_tracking` IS wired (the useful lever)

Real, and handled only on the TS side — a Python-only grep gives a false negative:

- `ui-tui/src/app/useConfigSync.ts` — accepts bool (true⇒all, false⇒off) or
  `off | wheel | buttons | all`; legacy `tui_mouse` honoured only when `mouse_tracking`
  is absent.
- `ui-tui/src/config/env.ts`, `ui-tui/src/gatewayTypes.ts`, plus
  `tests/test_tui_gateway_server.py` round-tripping `('display.mouse_tracking', 'all')`.

Default `all` means the TUI captures mouse events, so ordinary drag-select does not reach
the terminal and the user reaches for Ctrl+C. `buttons` or `off` gives selection back.
Holding Shift while dragging bypasses app mouse capture.

### Desktop rebindable hotkeys are data

`apps/desktop/src/lib/keybinds/actions.ts` is the declared single source of truth:

```
{ id: 'session.new',   defaults: ['mod+n', 'shift+n'] }
{ id: 'keybinds.openPanel', defaults: ['mod+/'] }
{ id: 'session.slot.1..9',  defaults: ['ctrl+1'..'ctrl+9'] }
...
```

`store/keybinds.ts` overlays user overrides from `hermes.desktop.keybinds` and only
persists diffs vs. the shipped defaults. Non-rebindable ones are listed separately in
`KEYBIND_READONLY` (Enter / Shift+Enter / Escape / mod+enter / mod+l / mod+w...).
Note `comboAllowedInInput` — primary-modifier combos fire even while typing, which is how
a stray binding can look like "it acts on my keypress in the chat box".

## Useful greps

```bash
# is a config key read anywhere, or only declared?
grep -rn "copy_shortcut" <install>/ --include=*.py
grep -rn "copy_shortcut" <install>/apps <install>/ui-tui/src <install>/web/src

# what does the CLI bind by hand?
grep -n "kb.add('c-" <install>/cli.py

# every rebindable desktop action + its shipped default
grep -n "id: '" <install>/apps/desktop/src/lib/keybinds/actions.ts
```

## Answer given

Ctrl+C is not a copy shortcut in Hermes and was not configurable in that build; copy via
the terminal's own gesture or `/copy`; `mouse_tracking` is the real setting for the
selection problem; the desktop app is the one surface with a bindings editor (Ctrl+/).
Recommended checking `hermes update --check`, since the local build lacked options the
live docs describe.
