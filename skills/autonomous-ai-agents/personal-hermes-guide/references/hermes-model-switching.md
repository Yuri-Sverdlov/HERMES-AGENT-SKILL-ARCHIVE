# hermes-model-switching (перенесено из отдельного скилла)

> Перенесено hermes-model-switching → personal-hermes-guide. Бывший отдельный скилл, вычищенный curator'ом; содержание сохранено здесь целиком.

# Hermes Model & Provider Switching

Use this when a user wants to switch the active model or provider in a running
Hermes session, or when model calls fail with provider/model errors like:

- `HTTP 404: model: <slug>` — the model isn't available on the current provider
- `Unknown provider '<x>'. Check 'hermes model' for available providers` — the
  provider slug was wrong (usually a typo or an embedded space)
- `live session sync failed: ...` — the in-session `/model` command was malformed

This skill governs the **in-session `/model` slash command** specifically. The
broader `hermes model` CLI picker and the provider/env-var table live in the
bundled `hermes-agent` skill — consult that for provider auth and key setup.

## FIRST: identify the interface — `/model` is NOT universal

Mid-session model switching works **differently per interface**. Pin this down
before giving instructions, or you'll send a user down a dead end:

| Interface | How to switch model mid-session |
|---|---|
| **CLI / TUI** (terminal) | the `/model --provider <slug> --model <id>` slash command (this skill) |
| **Desktop app / GUI** (embedded chat) | a **dropdown button in the bottom-right of the composer** showing the current model (e.g. `Opus 4 8 · Med ⌄`). Click it → pick provider → pick model. The `/model` slash command does NOT exist here. |

**Tell-tale that the user is in the GUI:** typing `/model` returns
**`No matches. Try /help`**. The desktop app's slash-command set is a small
allow-list and does not include `model`; switching is a UI affordance, not a
command. When you see this, stop pushing `/model` and point them at the
composer's model dropdown instead. Do NOT assume `/model` works — ask or infer
the interface first. (The screenshot signature: current-model pill + `⌄` next to
the mic / send buttons.)

## The `/model` slash command syntax

The in-session command takes a **provider slug** and a **model id**, each behind
its own flag:

```
/model --provider <provider-slug> --model <model-id>
```

Worked example (switch to DeepSeek V3 on OpenRouter):

```
/model --provider openrouter --model deepseek/deepseek-chat
```

Rules that matter:

1. **Provider slug is ONE token, no spaces.** It is the internal slug, not the
   human-readable display name. `OpenRouter` displays as "OpenRouter" in the
   `hermes model` picker but the slug is `openrouter`. A space (`open Router`)
   makes Hermes parse only the first word (`open`) as the provider and reject it
   as unknown.
2. **The model id needs the `--model` flag.** You cannot append the model to the
   provider flag or to a bare dash. `--deepseek/deepseek-chat` is wrong; it must
   be `--model deepseek/deepseek-chat`.
3. **Model id format is provider-specific.** OpenRouter ids are `vendor/model`
   (e.g. `deepseek/deepseek-chat`, `meta-llama/llama-3.3-70b-instruct`).
4. **No-arg `/model`** opens the interactive picker — recommend it to users who
   keep mistyping, since it avoids slug/flag errors entirely.

## Common failure → fix map

| Symptom | Cause | Fix |
|---|---|---|
| `Unknown provider 'open'` | space in slug (`open Router`) | use slug `openrouter` |
| model id ignored / "no model" | missing `--model` flag | add `--model <id>` |
| `Model names cannot contain spaces.` **on a command that looks correct** | an invisible Unicode whitespace char (non-breaking space U+00A0, or zero-width U+200B/U+FEFF) crept into the model id/slug via copy-paste | re-type the command by hand, OR run `scripts/clean_model_command.py` to scrub it, OR use bare `/model` picker |
| `HTTP 404: model: <slug>` | model not offered by current provider | verify model exists on the provider (see below), then switch provider+model together |
| switch "succeeds" but calls still fail | provider has no API key | confirm credential before switching (see below) |

## The "invisible space" trap (looks-correct command rejected)

Hermes validates the model id with `any(ch.isspace() for ch in requested)`
(`hermes_cli/models.py`). Python's `str.isspace()` is **Unicode-aware**, so it
fires not just on a literal space but on a **non-breaking space (U+00A0)**,
**zero-width space (U+200B)**, **BOM (U+FEFF)**, narrow/figure spaces, etc.
These are invisible on screen but routinely injected when copy-pasting from
chat apps, PDFs, or rendered web pages.

Symptom: the user pastes a command that is character-for-character correct to
the eye, and still gets `Model names cannot contain spaces.`

Three fixes, fastest first:

1. **Re-type the command by hand** (don't paste) — kills the hidden char.
2. **Bare `/model`** — the interactive picker avoids typed ids entirely.
3. **Sanitizer script** — `scripts/clean_model_command.py` strips every
   invisible/Unicode-whitespace char and prints (and on Windows, copies to the
   clipboard) a clean command ready to paste:

   ```bash
   python scripts/clean_model_command.py "/model --provider openrouter --model deepseek/deepseek-chat"
   # or:  python scripts/clean_model_command.py openrouter deepseek/deepseek-chat
   # or:  echo "<pasted dirty command>" | python scripts/clean_model_command.py
   ```

   Note: an external script CANNOT type into the live in-session `/model`
   command for the user — it can only hand back a guaranteed-clean string to
   paste. There is no way to fully automate the in-session switch from outside
   the session; the picker (`/model`) is the closest thing to one-step.

## Verify a model exists on the provider BEFORE switching

A 404 means the model id isn't served by that provider. Don't guess — query the
provider's model list. For OpenRouter:

```bash
# Does the exact id exist, and does it support tool use (critical for Hermes)?
curl -s https://openrouter.ai/api/v1/models | python -c "
import sys,json
d=json.load(sys.stdin)
want='deepseek/deepseek-chat'
m=next((x for x in d['data'] if x['id']==want), None)
print('present:', bool(m))
if m:
    print('context:', m.get('context_length'))
    sp=m.get('supported_parameters',[])
    print('tool use:', 'tools' in sp and 'tool_choice' in sp)
"
```

Hermes drives everything through tool calls, so **prefer models whose
`supported_parameters` include `tools` and `tool_choice`** — a model without
tool support will behave poorly as a Hermes backend even if it loads.

> 💰 **Cost/quality right-sizing.** When the user wants the *best-value* model
> (not just any working one) — common once Hermes becomes a primary tool and the
> Opus default gets expensive — see `references/model-cost-quality.md`. It has a
> live price-probe script (in/out $ per 1M, context, tool support) and a
> task-class → model-class strategy (budget / mid / top / max).

To list all ids from one vendor (handy when the user has a stale/renamed id):

```bash
curl -s https://openrouter.ai/api/v1/models \
  | python -c "import sys,json;[print(m['id']) for m in json.load(sys.stdin)['data'] if m['id'].startswith('deepseek/')]"
```

## Verify the provider credential is configured

A clean switch still fails at request time if the provider has no key. Check the
credential pool in `auth.json` (path is profile-aware; default
`~/AppData/Local/hermes/auth.json` on Windows, `~/.hermes/auth.json` on POSIX):

```bash
cd "$(dirname "$(hermes config path 2>/dev/null)")" 2>/dev/null || cd ~/.hermes
python -c "
import json
d=json.load(open('auth.json',encoding='utf-8'))
pool=d.get('credential_pool',{}).get('openrouter',[])
print('openrouter creds:', len(pool))
for c in pool:
    print('  auth_type=%s source=%s last_status=%s' % (c.get('auth_type'), c.get('source'), c.get('last_status')))
"
```

`last_status: ok` + a populated `source` (e.g. `env:OPENROUTER_API_KEY`) means
the key is live and the switch will work. If the pool is empty, the user needs
to set the provider's API key (see the provider/env-var table in the
`hermes-agent` skill, e.g. `OPENROUTER_API_KEY`) before switching.

## Use-case → Model guide

Beyond just *how* to switch, you need to know *which* model to switch to for
the task the user is trying to do. Different models have dramatically different
profiles for censorship, vision capability, cost, and prose quality. Make a
choice before running `/model`.

### Decision table

| If the user wants to… | Recommended model(s) | Rationale |
|---|---|---|
| generate or edit **uncensored NSFW prose** (18+ narrative, explicit language, erotic description) | **Grok 4.3** (`x-ai/grok-4.3` on OpenRouter), **Mistral Large** (`mistralai/mistral-large-2411`), **Llama 3.1-70B** (local via llama.cpp, abliterated) | Grok has the lightest censorship of any major hosted model. Mistral and abliterated Llama are alternatives. **Avoid** Claude, Gemini, GPT-4o — they block or water down NSFW. |
| **see and describe images / video frames** (vision analysis of user-provided visuals) | **Grok 4.3** (vision native), **GPT-5.5** on OpenRouter (vision if enabled) | Grok sees images directly in the session. If the user shares frames/screenshots, Grok can describe them in detail. |
| **BOTH vision + NSFW content generation** (see a video/porn clip, describe the scenes, then write a literary erotic story from those descriptions) | **Grok 4.3** — single model, no workarounds needed | This is the killer combo. Grok sees the frames *and* writes the story without censorship. No multi-model-writer, no delegation chains, no workarounds. One `/model --provider openrouter --model x-ai/grok-4.3` and the entire pipeline is solved. |
| get the **best value / lowest cost** for routine chat tasks | **DeepSeek V4 Flash** (`deepseek/deepseek-v4-flash`), **Llama 3.1-70B** (cheap hosted or local) | These are fast and cheap. But check censorship level — DeepSeek has moderate NSFW filtering. |
| get the **highest quality prose / deep reasoning** | **Claude Opus 4** (if available), **GPT-5.5** | Best for literary quality but both censor NSFW heavily. Use for the *safe* parts of the story, then switch to Grok for explicit scenes. |

### Strategy for mixed-content work (e.g. a literary story with explicit scenes)

1. Draft the narrative arc, character psychology, and non-explicit scenes on the
   best prose model (Opus / GPT).
2. Export the draft as a file.
3. Switch to Grok 4.3 (`/model --provider openrouter --model x-ai/grok-4.3`).
4. Have Grok read the draft and write the explicit scenes in matching tone.
5. Stitch together.

This two-model pipeline preserves literary quality for the framework while using
Grok's minimal censorship for the NSFW payload.

## End-to-end recipe

1. Identify the desired provider slug (lowercase, no spaces) and model id.
2. Confirm the model exists on that provider and supports tools (curl probe).
3. Confirm the provider credential is present (`auth.json` credential pool).
4. Tell the user the exact command:
   `/model --provider <slug> --model <id>`
5. If they keep mistyping, point them at bare `/model` for the picker.

## Pitfalls

- **`/model` is interface-specific.** It works in CLI/TUI but NOT in the desktop
  GUI, which uses a composer model dropdown. `No matches. Try /help` after typing
  `/model` = GUI; redirect to the dropdown. Confirm the interface before advising.
- The display name in the `hermes model` picker is NOT always the slug. When in
  doubt, grep `config.yaml` / the picker output for the lowercase one-word form.
- Don't conclude "the model is dead" from a 404 — it usually means *that
  provider* doesn't serve it; another provider may. Re-run the curl probe.
- A transient 404 on a model that was previously available can mean the provider
  pulled or renamed it (e.g. versioned ids like `...-v3-0324`). List the vendor's
  ids to find the current name.
