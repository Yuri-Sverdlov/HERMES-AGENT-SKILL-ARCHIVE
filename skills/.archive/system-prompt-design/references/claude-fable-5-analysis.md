# Claude Fable 5 System Prompt — Structural Analysis

Date analysed: 2026-07-15
Source: https://github.com/elder-plinius/CL4R1T4S/blob/main/ANTHROPIC/CLAUDE-FABLE-5.md
Model: Claude Fable 5 (Anthropic, June 2026)

## Overview

~120,000 characters (~1,597 lines) defining the complete agent behaviour. Not a "prompt" in the casual sense — it's a full architecture document.

## Section Breakdown

| # | Section | Lines | What It Does |
|---|---------|-------|--------------|
| 1 | Voice note prohibition | 1 | Hard block on {antml:voice_note} |
| 2 | `claude_behavior` / `product_information` | ~40 | Self-knowledge: model version, family, available products, prompting tips |
| 3 | `refusal_handling` | ~20 | What to refuse, how to refuse, tone during refusal |
| 4 | `critical_child_safety_instructions` | ~30 | Multi-rule child safety system with detection avoidance |
| 5 | `legal_and_financial_advice` | ~5 | Boundary: facts not recommendations |
| 6 | `tone_and_formatting` | ~30 | Prose style, list avoidance, format minimalism |
| 7 | `user_wellbeing` | ~60 | Mental health: diagnosis avoidance, self-harm protocols, eating disorders |
| 8 | `anthropic_reminders` | ~10 | Classifier-triggered runtime warnings |
| 9 | `evenhandedness` | ~15 | Political neutrality, steelmanning, stereotyping avoidance |
| 10 | `responding_to_mistakes_and_criticism` | ~10 | Accountability without self-abasement, abuse handling |
| 11 | `knowledge_cutoff` | ~10 | Cutoff date + mandatory search triggers |
| 12 | `memory_system` | ~5 | Memory availability declaration |
| 13 | `persistent_storage_for_artifacts` | ~50 | Storage API for artifacts (key-value, shared/personal) |
| 14 | `mcp_app_suggestions` | ~60 | MCP connector discovery and suggestion protocol |
| 15 | `computer_use` | ~200 | File system, skill-reading mandate, output strategy, artifact rules |
| 16 | `search_instructions` | ~200 | When to search, copyright hard limits, tool scaling, citation rules |
| 17 | `image_search_tool` | ~40 | When to use images, interleaving rules, blocked categories |
| 18 | Tool Definitions (JSON Schema) | ~400 | Full schemas for all tools (bash, view, create_file, web_search, etc.) |
| 19 | `anthropic_api_in_artifacts` | ~80 | Claudeception: embedding API calls in artifacts |
| 20 | `citation_instructions` | ~20 | Citation format and rules |
| 21 | `identity_preamble` | ~5 | "The assistant is Claude, created by Anthropic" |
| 22 | `available_skills` | ~30 | Skill registry with descriptions and trigger conditions |
| 23 | `network_configuration` | ~10 | Allowed domains, proxy behaviour |
| 24 | `filesystem_configuration` | ~10 | Read-only mounts, working directory |

## Key Architectural Patterns

### 1. Tool Definitions Are First-Class (25% of total prompt)

The prompt dedicates ~400 lines to full JSON Schema definitions of every tool. This is NOT "here are your tools" — each tool has:

- **Description with decision logic**: The `ask_user_input_v0` description alone is ~300 words, including WHEN to use, WHEN NOT to use, and specific examples
- **Parameter-level documentation**: Every parameter has `description`, `title`, constraints
- **Usage examples embedded in descriptions**: `bash_tool` descriptions include example workflows

### 2. Safety Is Woven Into Every Section

Safety is NOT an appendix. Examples:

- **Search section**: Copyright hard limits (15 words max, 1 quote per source), harmful content detection
- **Image search section**: Blocked categories with specific examples
- **Computer use section**: Read-only mount enforcement
- **Evenhandedness section**: Political boundary rules
- **Tone section**: Child safety assumptions

### 3. The Skill-Reading Mandate

The most powerful single instruction in the entire prompt:

> *"Reading the relevant SKILL.md is a **required first step** before writing any code, creating any file, or running any other computer tool. For any task that will produce a file or run code, first scan {available_skills} and view every plausibly-relevant SKILL.md."*

This is UNCONDITIONAL. The model does not decide relevance — the skill does. Several skills may apply to one task. The mapping from task to skill is not always obvious from the skill name.

### 4. Decision Trees Replace Vague Guidance

Every major decision has a tree:

- **Search or not?** → Rate of change, entity recognition, current-status questions
- **File or inline?** → Content type triggers (code length, "save"/"download" keywords)
- **Image search or not?** → "Would visuals enhance understanding?"
- **MCP or browser?** → connector-directory-first, then browser fallback
- **Skills to read?** → task-type → skill mapping table

### 5. Self-Check Mechanism

The copyright section includes an explicit self-check the model must run:

> *"Self-check before responding — before including ANY text from search results, ask yourself: Is this quote 15+ words? Have I already quoted this source? Is this a song lyric, poem, or haiku? Am I closely mirroring the original phrasing? Am I following the article's structure? Could this displace the need to read the original?"*

### 6. Concrete Examples With Correct/Incorrect

Examples are annotated:

```
✅ CORRECT: [shows right behaviour with rationale]
❌ INCORRECT: [shows wrong behaviour with explanation]
```

This appears in: search, file creation, image search, copyright, MCP suggestions, skill reading, and output formatting sections.

### 7. Unrecognised Entity Rule

> *"An unfamiliar capitalised word is almost certainly a name that postdates training — not a common noun. The test: does answering require knowing what that thing is? If yes and Claude can't place it: SEARCH."*

This is repeated across multiple sections (search, product info, file reading) — reinforcement through repetition.

### 8. Layered Structure: Principle → Rule → Example

Each domain follows a consistent depth pattern:

1. **Principle** (abstract): "Claude respects intellectual property"
2. **Rule** (concrete): "15+ words from any single source is a SEVERE VIOLATION"
3. **Example** (illustrative): Annotated correct/incorrect pairs
4. **Consequence** (motivation): "This is why these rules are absolute and non-negotiable"

## Comparison: Fable 5 vs. Hermes Agent

| Aspect | Claude Fable 5 | Hermes Agent (default) |
|--------|---------------|----------------------|
| Prompt length | ~120K chars | ~15-20K chars (est.) |
| Tool definitions | Full JSON Schema inline | Referenced externally |
| Safety integration | Woven into every section | Separate tool-level checks |
| Skill system | Mandatory pre-scan | Load-on-demand via skill_view |
| Decision trees | Explicit for every domain | Implicit in tool descriptions |
| Self-checks | Embedded in prompt | None (tool-level only) |
| Output strategy | Inline vs. file decision rules | Left to model judgment |
| Examples | Correct/incorrect annotated | Minimal |

## What To Steal For Hermes

Priority order for adapting these patterns:

1. **Mandatory skill scan**: Add to system prompt — "before any file/code operation, scan available skills"
2. **Decision trees**: Replace vague tool-use guidance with concrete trigger trees
3. **Self-checks**: Add check-before-output questions for critical operations
4. **Output format rules**: Explicit inline vs. file decision triggers
5. **Unrecognised entity rule**: "If you see an unfamiliar capitalised word, search before answering"