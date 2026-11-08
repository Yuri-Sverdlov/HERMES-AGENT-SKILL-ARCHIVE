---
name: hermes-profiles-and-sessions
description: "Organize work in Hermes like projects: profiles as isolated workspaces, session naming with prefixes, switching with the -p flag, creating empty session stubs, and attaching a project's own skill via skills.external_dirs. Covers the profile-vs-session two-level model and the state.db layout."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, profiles, sessions, organization, projects, state-db]
    related_skills: [hermes-agent, personal-hermes-guide]
---

# Hermes Profiles & Session Organization ("projects")

Use this when a user wants to organize their Hermes chats like the "projects /
folders" feature of ChatGPT/Claude apps, switch between isolated workspaces, or
manage/seed sessions.

## The key truth: no nested "folders", but two real levels

Hermes has **no visual project folders** and **no sub-profiles** (profiles are
flat — no nesting). But two mechanisms compose into the same effect:

| Level | Mechanism | Role |
|---|---|---|
| Top | **Profile** (`hermes profile ...`) | Isolated workspace: its OWN memory, skills, config, and session store. Like a separate "office". |
| Sub | **Session title prefix** (`[TAG] ...`) | Sub-topic inside a profile. Found via search/browse. Like a filename tag. |

So the "hybrid" a user usually wants = **a few real profiles** + **prefixed
session names inside each**. Don't pitch "sub-profiles" — they don't exist.

When to make a new PROFILE vs. just a prefix:
- New profile ONLY when memory should genuinely be SEPARATE (e.g. creative
  writing vs. technical work — mixing their memory is harmful).
- Same profile + prefix when topics share context (e.g. "dashboard" and "guides"
  are both technical → one profile, two prefixes). Don't spawn a profile per
  small topic; that becomes a maintenance burden.

## Switching profiles — the `-p` flag, NOT an env var

The profile is selected by the **`-p` / `--profile` flag**, resolved internally
via `HERMES_HOME`. Setting `HERMES_PROFILE=<name>` does **NOT** switch the
profile — it is silently ignored and you'll see the DEFAULT profile's sessions,
which looks like "my stubs disappeared". Always verify with the flag:

```bash
hermes -p creative sessions list      # sessions in profile 'creative'
hermes -p creative chat               # chat inside 'creative'
hermes sessions list                  # default profile (no flag)
```

`hermes profile create <name>` also writes a wrapper `~/.local/bin/<name>.bat`
(Windows) whose entire body is `hermes -p <name> %*` — i.e. the alias just
front-loads `-p`. That wrapper dir may not be on PATH (the create command warns);
add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` to use the bare alias.

## Profiles also solve cross-machine transfer

`hermes profile export <name>` packs a whole profile (memory + skills + config)
into an archive; `hermes profile import` unpacks it on the second computer. A
"project" thus becomes portable in one command — relevant for multi-PC users.

## Attaching a project's OWN skill to Hermes (without copying it)

When a skill belongs to a specific project repo (it references that repo's
`tasks/`, `app/`, `AGENTS.md`), keep it INSIDE the project and register the
project's `.hermes/skills` dir in `skills.external_dirs` — don't copy it into
`~/.hermes/skills/`. The skill then travels with the repo's git and stays a
single source of truth. Two non-obvious traps bite here: `hermes config set`
stores a JSON array as a literal string (pass a BARE path, not JSON), and
`hermes skills inspect/list` don't show external skills even though they load
fine (verify with `skill_view`). Full recipe + pitfalls:
`references/project-local-skills.md`.

## Creating empty session stubs (placeholders with prefixes)

Starting a chat to make a session costs an API call (and needs keys the new
profile may lack). To seed EMPTY labelled placeholders cheaply, insert rows
directly into the profile's `state.db`. Full recipe & schema notes:
`references/session-stubs.md`.

Always verify stubs via the real CLI (`hermes -p <name> sessions list`), not just
a raw DB query — that confirms Hermes actually recognizes them.

## Pitfalls

- A freshly created profile has **no API keys** until `hermes -p <name> setup`
  (or it inherits keys from the shell env). Tell the user before they try to chat.
- A new profile's `state.db` does NOT exist until first use — create it (see the
  reference) before inserting stubs, or the insert path won't exist.
- Don't rebuild the `state.db` schema by hand: it has FTS5 virtual tables and
  triggers. Copy the existing default `state.db`, then DELETE FROM messages /
  sessions to get a correct empty schema. (Details in the reference.)
- `sessions` FTS indexes are over `messages`, not `sessions`, so inserting
  zero-message session rows is safe and won't corrupt the FTS index.
