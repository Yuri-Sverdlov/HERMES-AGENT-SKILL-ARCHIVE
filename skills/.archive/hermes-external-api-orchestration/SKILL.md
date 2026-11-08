---
name: hermes-external-api-orchestration
category: autonomous-ai-agents
description: When Hermes built-in delegation (delegate_task) is unsuitable — especially for adult/NSFW content blocked by Claude — use direct OpenRouter API calls to run multiple models in parallel.
---

# Hermes External API Orchestration

## When to use this skill
- `delegate_task` forces `claude-haiku-4-5`, which refuses explicit sexual content.
- You need to compare output from Grok + Gemini (or other models) on the same prompt.
- You want parallel generation from multiple providers without going through Hermes delegation.

## Core pattern
Call OpenRouter directly via the OpenAI-compatible client in a Python script. This bypasses Hermes' subagent system entirely.

## Recommended models (OpenRouter)

| Key         | Model slug                              | NSFW? | Notes |
|-------------|------------------------------------------|-------|-------|
| grok        | x-ai/grok-4.3                           | ✅    | Best for raw, character-driven adult prose |
| llama70     | meta-llama/llama-3.1-70b-instruct       | ✅    | Reliable, good style |
| llama33     | meta-llama/llama-3.3-70b-instruct       | ✅    | Newer, slightly stronger |
| mistral     | mistralai/mistral-large                  | ✅    | Good style and structure |
| mistral-med | mistralai/mistral-medium                 | ✅    | Faster, cheaper |
| gemini      | google/gemini-2.5-flash                  | ❌    | Returns empty response silently on NSFW |
| qwen-vl     | qwen/qwen-2.5-vl-72b-instruct            | ✅    | Vision + text, low censorship, good prose |
| qwen-vl-old | qwen/qwen-2-vl-72b-instruct              | ⚠️    | Older vision model, weaker prose than 2.5 |

**⚠️ Do NOT use `x-ai/grok-4`** — deprecated, returns 404. Use `x-ai/grok-4.3` only.

## Implementation
See `scripts/multi_model_writer.py` for a ready-to-use parallel caller that saves results to separate files and logs prompt history.
See `scripts/vision_writer.py` for image+prompt → single model (Grok 4.3 vision) writer with min/max word count input.
See `tools/vision_compare.py` for image+prompt → **two vision models** (Grok 4.3 vs Qwen2.5-VL 72B) — two output files for side-by-side comparison. Launch with `vision_compare.bat`.

## Key advantages over delegate_task
- Full control over which model is used
- No censorship from Claude safety filters
- Parallel execution of different models on the same prompt
- Easy to extend with more providers

## Pitfalls

- Requires `OPENROUTER_API_KEY` set via `$env:OPENROUTER_API_KEY="sk-..."` (PowerShell) or `setx` for permanent installation. Must restart terminal after `setx`.
- **`x-ai/grok-4` is deprecated** — always use `x-ai/grok-4.3` or it returns 404.
- **Gemini silently returns empty on NSFW** — no error, just `[ERROR] Empty response`. Do not rely on Gemini for adult content.
- **`background=false` in `delegate_task` is ignored** — subagents always run in background. Use the external script pattern instead for synchronous results.
- **`qwen/qwen-2-vl-72b-instruct` is a vision model** — bad choice for long prose. Use `qwen/qwen-2.5-72b-instruct` (text version) instead.
- Need to manage rate limits and token costs manually.
- Syntax errors when copying Python scripts into chat — always write the full file via `write_file` tool, not copy-paste through the UI.
- `max_tokens` ≠ word count: 1 Russian word ≈ 1.4 tokens. Expose `min_words` / `max_words` inputs and convert internally.

## Vision Writer (vision_writer.py)

When the user attaches images and wants model-generated prose based on them:
- `vision_analyze` tool is **not always available** in Hermes sessions — check before relying on it
- Use `tools/vision_writer.py` instead: sends base64-encoded images + prompt to a vision-capable model via OpenRouter
- Grok 4.3 supports vision input via `image_url` content blocks with `data:<mime>;base64,<b64>` URLs
- Script accepts image paths as CLI args or interactive input, then asks for prompt and min/max word count
- Output saved to `outputs/grok_vision_<timestamp>.md`

## Windows .bat launcher files — CRLF pitfall

**CRITICAL:** `write_file` tool always produces **LF** line endings. Windows CMD requires **CRLF**. A `.bat` file with LF endings produces errors like:
```
'1' is not recognized as an internal or external command
'EY' is not recognized as an internal or external command
```

**❌ DO NOT use `printf` in bash/terminal to write .bat files.** Paths containing `\v` (e.g. `tools\vision_writer.py`) or `\t` get interpreted as escape sequences (`\x0b`, `\x09`), corrupting the file silently:
```
python "G:\_My_Programming\HERMES-AGENT\tools\x0bision_writer.py"
```

**✅ CORRECT fix:** Write `.bat` files via a Python script with explicit `newline="\r\n"`:
```python
lines = [
    "@echo off",
    "chcp 65001 >nul",
    'python "G:\\_My_Programming\\HERMES-AGENT\\tools\\vision_writer.py"',
    "pause",
]
with open("tools/vision_writer.bat", "w", encoding="utf-8", newline="\r\n") as f:
    f.write("\n".join(lines) + "\n")
```

Save this as `tools/make_bats.py` and run it once. Future `.bat` updates go through this script.

**Key rules:**
- Use raw strings `r"..."` or double-escaped `\\` for Windows paths in Python strings
- Avoid `\v`, `\t`, `\b`, `\f` in any string that ends up in a bat path
- Verify with: `file script.bat` — must show `with CRLF line terminators`
- The `make_bats.py` pattern is already at `G:\_My_Programming\HERMES-AGENT\tools\make_bats.py`

## API key: $env: vs setx

- `$env:OPENROUTER_API_KEY="..."` — **session-only**, lost when PowerShell closes
- `setx OPENROUTER_API_KEY "..."` — **permanent**, but requires opening a new terminal to take effect
- Scripts launched via double-click `.bat` use the **system environment** — only `setx` works for them

## Script features (multi_model_writer.py v2.3)

- Prompts for `min_words` and `max_words` — converts to `max_tokens` automatically
- `MODEL_A` / `MODEL_B` constants at top of file — easy to swap without touching logic
- All results saved to `outputs/<model>_<timestamp>.md`
- All prompts logged to `prompt_history.md` with model names and file references
- `temperature=0.9` gives good variety; change per-call in `call_model()` for different results from same prompt