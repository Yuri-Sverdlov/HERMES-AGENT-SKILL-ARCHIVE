# Model cost / quality comparison for Hermes backends

Use this when a user asks "which model is best value", "what's cheaper than my
current model", or wants to right-size their model to the task (a common ask
once Hermes becomes a primary tool and Opus-by-default gets expensive).

## The core idea: match model class to task class

Hermes ships with a strong default (e.g. Claude Opus) so it works great out of
the box — but Opus is the most expensive tier. For ~80% of tasks (search,
reports, chat, light analysis) a model 20–200× cheaper performs nearly as well.
Strategy: keep a cheap "workhorse" as the daily driver, switch up to a top model
(via GUI dropdown / TUI/CLI `/model`) only for genuinely hard work.

| Class | When | Examples (Hermes-suitable, all support tools) |
|---|---|---|
| 🟢 Budget | search, chat, summaries, simple Q&A | DeepSeek V3.2, Llama 3.3 70B, GPT-5 mini |
| 🟡 Mid | reports, analysis, big documents, reasoning | Gemini 2.5 Flash (huge ctx), GLM-4.6, DeepSeek R1 |
| 🔴 Top | hard code, multi-step agentic chains | GPT-5, Gemini 2.5 Pro, Claude Sonnet 4.5 |
| 🔴🔴 Max | when everything cheaper failed | Claude Opus (most expensive, $$$) |

## How to build a LIVE, accurate price table (don't quote from memory)

Prices change; pull them from the provider API. For OpenRouter:

```bash
curl -s https://openrouter.ai/api/v1/models | python -c "
import sys,json
d=json.load(sys.stdin)
want = ['deepseek/deepseek-chat','deepseek/deepseek-v3.2','deepseek/deepseek-r1',
 'google/gemini-2.5-flash','google/gemini-2.5-pro','openai/gpt-5','openai/gpt-5-mini',
 'anthropic/claude-sonnet-4.5','anthropic/claude-opus-4.1','meta-llama/llama-3.3-70b-instruct',
 'z-ai/glm-4.6','x-ai/grok-4']
m={x['id']:x for x in d['data']}
rows=[]
for w in want:
    x=m.get(w)
    if not x:  # fuzzy fallback for renamed/versioned ids
        c=[k for k in m if k.startswith(w.rsplit('-',1)[0])]
        x=m.get(c[0]) if c else None
    if not x: print('MISSING',w); continue
    p=x.get('pricing',{}); sp=x.get('supported_parameters',[])
    rows.append((x['id'], float(p.get('prompt',0))*1e6, float(p.get('completion',0))*1e6,
                 x.get('context_length',0)//1000, 'tools' in sp and 'tool_choice' in sp))
rows.sort(key=lambda r:r[1]+r[2])
print(f'{\"model\":42}{\"in/1M\":>8}{\"out/1M\":>8}{\"ctxK\":>7}  tools')
for i,pin,pout,ctx,t in rows:
    print(f'{i:42}{pin:8.3f}{pout:8.3f}{ctx:6}K  {\"yes\" if t else \"NO\"}')
"
```

Key columns to surface to the user: **in/1M, out/1M, context length, tool
support**. Sort by total price so the cheap-to-expensive gradient is obvious.

## Pitfalls / caveats to state every time

- **Tool support is mandatory for Hermes.** A model whose `supported_parameters`
  lacks `tools`+`tool_choice` will behave poorly as a backend even if cheaper.
  Always show the tools column and steer away from `NO`.
- **OpenRouter prices ≠ direct-provider prices.** Anthropic/OpenAI direct, or
  Nous Portal, may differ. Present the table as a *ratio/orientation* guide, not
  an exact bill.
- **"Quality" in any such table is a general proxy.** The honest follow-up is a
  live A/B: run the user's actual task on 2–3 models and compare output+speed.
  Offer this rather than treating the table as final.
- Versioned ids get pulled/renamed (e.g. `...-v3-0324`). If a wanted id is
  MISSING, list the vendor prefix to find the current name (see
  hermes-model-switching SKILL.md "verify a model exists").
