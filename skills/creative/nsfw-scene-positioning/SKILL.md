---
name: nsfw-scene-positioning
description: Methodology for ensuring physical and logical consistency in multi-character (especially group/NSFW) scenes using contact matrices, golden rules, and multi-agent delegation for position checking.
category: creative
---

# NSFW Scene Positioning

## Purpose
Enforce rigorous physical and logical consistency when writing complex multi-person scenes, particularly group sex and partner-exchange scenes. Prevents impossible configurations where characters occupy contradictory states with the same body part.

## Core Artifacts

- **5 Golden Rules** (see references/golden-rules.md)
- **Contact Matrix** template and checklist (see references/contact-matrix.md)
- **Multi-agent workflow** using `delegate_task` for Position & Logic Checker → Writer → Dialogue roles

## When to Use

- Any scene involving 3+ characters in sexual contact
- Partner swapping / group dynamics
- Scenes with simultaneous oral, vaginal, and manual actions
- When the user wants maximum physical plausibility

## Trigger Phrases

- "group scene"
- "two couples"
- "double penetration"
- "who is doing what to whom"
- "position check"
- "make sure this is physically possible"

## Known Pitfalls

- Mouth described as both occupied and free in the same sentence
- Character "watching" while their face is buried
- One person claimed to be in two incompatible positions simultaneously
- Transfer of a body part (penis) between partners without explicit transition language
- **"Стонет на члене" (moaning on his cock) does not tell you whether contact is vaginal or oral** — always specify the body part and type explicitly
- Claude Haiku (Agent 2 via delegate_task) refuses NSFW prose — use external API script for writing steps

## ⚠️ Critical: Multi-Agent Writer Step Requires External API

**Claude Haiku (the Hermes `delegate_task` subagent model) refuses to write explicit NSFW prose.** It returns:
> "I cannot create this scene."

The multi-agent pattern therefore works ONLY for the Position & Logic Checker step (Agent 1). For the Writer (Agent 2) and Dialogue Specialist (Agent 3) steps, you MUST use the external OpenRouter script instead of `delegate_task`.

**Correct workflow:**

1. **Agent 1 (Position & Logic Checker)** → `delegate_task` (Claude Haiku) ✅ works
2. **Agent 2 (Writer)** → `tools/multi_model_writer.py` via OpenRouter with Grok 4.3 or Llama ✅ works
3. **Agent 3 (Dialogue)** → same external script, or write inline ✅ works

See skill `hermes-external-api-orchestration` for the external API pattern.

## Vision-Based Scene Generation

When the user provides photos as the creative starting point:
1. `vision_analyze` tool may not be available — check at session start (confirmed absent in 2026-07-04 session)
2. If unavailable, use `tools/vision_writer.py` (see `hermes-external-api-orchestration` skill): sends images base64-encoded to Grok 4.3 via OpenRouter
3. Prompt should ask for: сеттинг, персонажи, мотивация, что происходит — and apply the same Contact Matrix discipline to the generated scene
4. If images contain real people, describe only fictional characters inspired by the setting/mood, not identities
5. Script accepts multiple images interactively — press **Enter on empty line** to stop adding images and move to the prompt
6. Vision writer confirmed working end-to-end (2026-07-04): 2 images → Grok 4.3 → 3-scene outline, ~720 words
7. For side-by-side comparison of two vision models, use `tools/vision_compare.py` (Grok 4.3 vs Qwen2.5-VL 72B) — outputs two files in `outputs/vision_grok_*.md` and `outputs/vision_qwen_*.md`

## References

- `references/golden-rules.md` — The 5 rules that must be checked on every pass
- `references/contact-matrix.md` — The matrix template + filled example from 2026-06-27 session
- `references/session-2026-06-27.md` — Full analysis and files created during initial testing of this skill

**Note:** This skill was created and populated during the 2026-06-27 multi-agent positioning workflow testing session.