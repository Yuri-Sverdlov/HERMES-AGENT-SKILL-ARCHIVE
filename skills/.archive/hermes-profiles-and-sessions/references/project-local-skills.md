# Attaching a project-local skill to Hermes (external_dirs)

Use when a skill belongs to a SPECIFIC project (it references that repo's
`tasks/`, `app/`, `AGENTS.md`, etc.) and you want Hermes to recognize it WITHOUT
copying it into `~/.hermes/skills/`. This keeps the skill living inside its own
project (tracked by the project's git, portable with the repo, no duplication).

## When to use this vs. a normal skill

- **external_dirs (this recipe):** the skill is part of a project repo and should
  travel with it. Example: an "immergo-coder" charter that only makes sense
  inside the Immergo project.
- **Normal `~/.hermes/skills/`:** general-purpose skills not tied to one repo.

`external_dirs` are **read-only** to Hermes — skill *creation* always writes to
the local dir. Local skills take precedence on name collisions.

## Recipe

1. Put the skill in the project under `.hermes/skills/<skill-name>/SKILL.md`:
   ```
   <PROJECT>/.hermes/skills/<skill-name>/SKILL.md
   ```
   - Write SKILL.md as **plain UTF-8, NO BOM** — it has a YAML frontmatter
     (`---` first line); a BOM breaks the frontmatter parse. (This is the one
     place the user's "always BOM" rule does NOT apply — that rule is only for
     his human-read .md guides, not machine-parsed skill files.)

2. Register the project's skills dir in config (NOTE the path is the
   `.hermes/skills` dir, the parent of the skill folder):
   ```bash
   hermes config set skills.external_dirs "<PROJECT>/.hermes/skills"
   ```

3. Verify Hermes actually sees it via `skill_view`:
   ```
   skill_view(name="<skill-name>")   # should return content + skill_dir pointing into the project
   ```

## Pitfalls (both hit and solved this session)

- **`hermes config set` mangles a JSON array into a STRING.** Passing
  `'["G:/.../.hermes/skills"]'` stored the literal string `'["..."]'`, which the
  loader then iterates CHARACTER BY CHARACTER (`[`, `"`, `G`, ...), resolving each
  char as a bogus path. FIX: pass a **plain bare path string**, not JSON:
  ```bash
  # WRONG: hermes config set skills.external_dirs '["G:/proj/.hermes/skills"]'
  # RIGHT:
  hermes config set skills.external_dirs "G:/proj/.hermes/skills"
  ```
  The loader accepts a single string and wraps it in a list itself
  (`if isinstance(raw_dirs, str): raw_dirs = [raw_dirs]`). For MULTIPLE dirs,
  edit `config.yaml` as a proper YAML list via `hermes config edit` instead.

- **`hermes skills inspect <name>` and `hermes skills list` do NOT show external
  skills.** Those CLI commands only scan the hub + local `~/.hermes/skills/`.
  This is NOT a failure — the skill still loads. Verify with `skill_view`
  (the agent's real load path / prompt builder), which DOES read external_dirs.

- **The agent cannot edit `config.yaml` directly** (security guard refuses writes
  to the Hermes config). Use `hermes config set` / `hermes config edit`.

- **Path resolution:** entries expand `~` and `${VAR}`; relative paths resolve
  against `HERMES_HOME`, not cwd. Use absolute paths for project dirs.

## Quick verification snippet (run via execute_code/terminal)

```python
import yaml, os
from pathlib import Path
cfg = yaml.safe_load(open(os.path.expanduser('~/AppData/Local/hermes/config.yaml'), encoding='utf-8'))
v = cfg['skills']['external_dirs']
raw = v if isinstance(v, list) else [v]
for e in raw:
    p = Path(os.path.expanduser(os.path.expandvars(str(e).strip()))).resolve()
    print(p, '| is_dir:', p.is_dir())
    if p.is_dir():
        for sub in p.iterdir():
            print('   ', sub.name, '-> SKILL.md:', (sub/'SKILL.md').exists())
```
If you see the path iterated character-by-character, the value was stored as a
string-of-JSON — re-set it as a bare path.
