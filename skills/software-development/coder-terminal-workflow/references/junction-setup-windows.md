# Junction setup on Windows from git-bash

When the coder runs in git-bash (MSYS) and needs to create/repair directory junctions on Windows, `cmd //c mklink /J` often fails with quoting/escaping issues (`Invalid switch` or `The network path was not found`).

## Reliable approach: pwsh

```bash
pwsh -Command "New-Item -ItemType Junction -Path 'C:\Users\Yuri\hermes-guides' -Target 'G:\_MY-PROGRAMMING_1\HERMES-AGENT\guides' -Force"
```

`-Force` replaces an existing junction/symlink at the path without error.

## Stale junction after disk rebuild (recurring)

When the disk layout changes (e.g. after `G:` was rebuilt 2026-08-15), existing junctions under `~/hermes-guides` may point to dead paths. Symptoms:

- `ls -la ~/hermes-guides` shows a symlink/junction to a non-existent path
- `cmd //c mklink` fails with `The network path was not found` (the old target no longer exists, but the stale link still resolves as "network path")
- The junction was created by `git clone` or the old bootstrap and was never updated

**Fix sequence:**
1. Check existing junction: `ls -la ~/hermes-guides` (shows the link target)
2. Remove: `unlink ~/hermes-guides` (in git-bash) or `Remove-Item` via pwsh
3. Create new: `pwsh -Command "New-Item -ItemType Junction -Path 'C:\Users\Yuri\hermes-guides' -Target 'G:\_MY-PROGRAMMING_1\HERMES-AGENT\guides' -Force"`
4. Verify: `ls -la ~/hermes-guides && ls ~/hermes-guides/` (should show guide files)

## Why not cmd //c

In git-bash (MSYS2):
- `cmd //c` passes the command to cmd.exe, but MSYS path translation interferes
- Backslashes get mangled: `"C:\Users\Yuri\hermes-guides"` may be translated to `C:UsersYurihermes-guides` (missing separators)
- Quotes are stripped or reinterpreted before reaching cmd.exe

`pwsh` as a native Windows executable receives arguments correctly from git-bash's environment. pwsh 7+ is installed on this machine (`winget install --id Microsoft.PowerShell`).

## Check also

For cross-PC sync and the git side of junction setup, see `hermes-cross-pc-git-sync` skill.