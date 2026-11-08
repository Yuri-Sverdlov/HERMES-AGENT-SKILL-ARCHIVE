---
name: system-prompt-design
description: "Design and improve system prompts for AI agents — analyse existing prompts, extract architectural patterns, apply proven techniques (decision trees, self-checks, tool orchestration, mandatory skill scanning). Use when writing, reviewing, or improving any agent's system prompt (Hermes, Claude, custom agents, ComfyUI LLM workflows)."
version: 1.0.0
platforms: [linux, macos, windows]
---

# System Prompt Design

Design high-quality system prompts for AI agents using proven architectural patterns extracted from production prompts (Anthropic Claude, Nous Hermes, etc.).

## When to Use

- Writing a new system prompt for any AI agent
- Reviewing or improving an existing system prompt
- Analysing a leaked/reference prompt for reusable patterns
- Designing agent behaviour: tool use, output format, safety boundaries
- The user asks "how should I structure this agent's prompt?"

## Core Design Principles

These are extracted from production-grade system prompts (Claude Fable 5, Hermes Agent) and represent battle-tested patterns — not theory.

### 1. Concreteness Over Abstraction

Every rule must have **decision trees, concrete triggers, and annotated examples** — not vague guidance.

```
❌ BAD: "Use web search when needed"
✅ GOOD:
  Search in web?
  ├── Historical fact, couldn't have changed → do NOT search
  ├── Current status (who holds position X, is Y alive) → ALWAYS search
  ├── Unfamiliar capitalised word → SEARCH (unrecognised entity rule)
  ├── Product version / model number → SEARCH (training may be stale)
  └── Simple code / definition → do NOT search
```

### 2. Self-Check Mechanism

Insert explicit self-check questions the model must ask itself before output. This is far more effective than prohibition alone.

```
Before responding, ask yourself:
  - Is this quote over 15 words? → HARD VIOLATION
  - Have I already quoted this source? → CLOSED for further quotes
  - Am I mirroring the original phrasing? → Rewrite entirely
  - Am I following the article's structure? → Reorganise completely
```

### 3. Mandatory Skill/Context Scanning

Make skill-reading **unconditional** — the model does not decide "whether it needs a skill"; the skill itself defines relevance.

> *"For any task that will produce a file or run code, first scan {available_skills} and view every plausibly-relevant SKILL.md. This check is unconditional: don't first decide whether the task needs a skill — the skills themselves define what they cover."*

### 4. Tool Orchestration Hierarchy

Explicit priority chain — not just a list of available tools:

```
1. Internal tools (memory, file system, project context) for known data
2. Web search for external information
3. Combined approach for comparative queries
```

### 5. Output Format Decision Rules

Concrete triggers for inline vs. file output — tone and brevity do NOT change the bucket:

| Inline (chat) | File (artifact) |
|---------------|-----------------|
| Strategy, analysis, plan | Blog post, article, story |
| Code ≤20 lines | Code >20 lines |
| Concept explanation | Presentation, report |
| Direct answer to question | Anything with "save", "download", "file I can keep" |

> *"Tone and length don't change the bucket: 'write me a quick 200-word blog post lol' → still a file."*

### 6. Epistemic Calibration (Unrecognised Entity Rule)

> *"An unfamiliar capitalised word is almost certainly a name that postdates training — not a common noun. The test: does answering require knowing what that thing is? If yes and the model cannot place it: SEARCH. Knowing a franchise is NOT knowing its new release."*

### 7. Correct/Incorrect Examples Inline

Annotated examples inside the prompt itself outperform abstract rules:

```
✅ CORRECT: "The reviewer praised the film enthusiastically"
❌ INCORRECT: "The reviewer called it 'a delight and a revelation'"
```

## Architecture Checklist

When designing a system prompt, ensure these sections exist:

| Section | Purpose | ~% of total |
|---------|---------|-------------|
| Identity & product info | What the agent is, what it knows about itself | 5% |
| Behaviour & tone | How it communicates, formatting rules | 15% |
| Safety & refusals | Hard boundaries, refusal handling | 15% |
| Tool orchestration | When and how to use each tool, priority chains | 25% |
| Output strategy | File vs. inline, artifact creation rules | 15% |
| Search/research rules | When to search, how to cite, copyright limits | 15% |
| Self-checks & error recovery | How to handle mistakes, criticism, edge cases | 10% |

## Pitfalls

- **Over-abstracting**: "Be helpful and safe" is worthless without concrete triggers
- **Safety as appendix**: Safety rules must be woven into every section, not ghettoised
- **Missing tool orchestration**: Listing tools is not enough — the prompt must define WHEN and HOW to use them
- **No self-checks**: Prohibition alone ("don't do X") is far weaker than self-check questions
- **Wrong granularity**: Too short = vague. Too long = model ignores it. Target: concrete examples for every abstract rule

## Reference

See `references/claude-fable-5-analysis.md` for the full structural analysis of the leaked Claude Fable 5 system prompt — sections, patterns, and annotated excerpts.