---
name: llm-chat-knowledge-base
description: Export, organize, and search chat histories from LLM platforms (Hermes, GPT, Gemini, Grok, Perplexity, Claude) as a local markdown knowledge base with document-level and paragraph-level search.
version: 1.0.0
platforms: [linux, macos, windows]
---

# LLM Chat Knowledge Base

Build a unified, searchable knowledge base from chat histories across multiple LLM platforms. The core pattern: **export → markdown with anchors → dual-mode search**.

## When to use

- User wants to centralise chats from multiple LLMs into one searchable place
- User needs to find specific conversations across models/platforms
- User asks to "сделать базу знаний чатов" or "organise my LLM chats"
- User mentions exporting Hermes sessions, GPT history, or other LLM chat logs
- User needs paragraph-level search (not just document-level) with exact navigation to the matching paragraph

## Architecture

```
LLM-KNOWLEDGE-BASE/
├── export_<platform>.py     # Per-platform exporters: state.db / JSON export → .md
├── search.py                # Dual-mode search CLI
├── <platform>-chats/        # Exported markdown files
│   ├── YYYY-MM-DD_model_title.md
│   └── ...
└── README.md
```

Each `.md` file = one chat session, with:
- **YAML frontmatter**: model, date, source, title, topics, message_count, tokens, cost
- **Anchored messages**: `<a id="msg-N"></a>` before each message — enables paragraph-level navigation
- **Formatted messages**: blockquotes with role emoji + timestamp

## Search modes

### 1. Document-level (`--docs`)
Returns a table of matching files with metadata: title, model, date, message count, topics, match count, snippet.

```
python search.py --docs "python проект"
python search.py --docs "" --topic проза          # all docs by topic
python search.py --docs "nsfw" --model deepseek    # filter by model
```

### 2. Paragraph-level (`--paras`)
Returns specific paragraphs with ~2 lines of context and **anchor links** (`file.md#msg-N`) that jump directly to the matching message — not the beginning of the file.

```
python search.py --paras "nsfw сцены"
python search.py --paras "python" --model deepseek --context 3
```

Each result shows:
- File name, model, date
- Anchor link (`file.md#msg-N`) with approximate line number
- Context before (previous messages)
- The matching paragraph (highlighted with `>>> ROLE >>>`)
- Context after (following messages)

## Exporters

### Hermes (state.db)
Reads `C:\Users\<user>\AppData\Local\hermes\state.db` (Windows) or `~/.hermes/state.db` (Linux/macOS).

The script at `scripts/export_hermes.py` handles:
- Session metadata extraction (model, tokens, cost, title)
- Topic auto-detection from title + first 10 messages (keyword heuristics)
- Russian → ASCII filename transliteration
- UTF-8 with BOM output (critical for Windows Cyrillic users)

### Future platforms
- **ChatGPT**: parse the official JSON export (`conversations.json`)
- **Claude**: parse Claude.ai export or Claude Code session logs
- **Gemini**: parse Google Takeout JSON
- **Grok**: parse xAI export
- **Perplexity**: parse Perplexity export

## Pitfalls

- **claude.ai shared links (`/share/...`) are inaccessible by automation.** Cloudflare protection + React SPA = two-layer barrier. `curl` gets an empty HTML shell, headless Playwright gets blocked at the bot-detection challenge. 27 attempts with various headers all failed. The only reliable path is: user opens the link in their real browser → Ctrl+A, Ctrl+C → pastes text here. Do NOT attempt automated fetching of claude.ai share links; tell the user immediately and ask them to copy-paste.
- **UTF-8 BOM is mandatory for Russian users on Windows.** Without BOM, legacy Notepad and some Markdown readers decode UTF-8 as Windows-1251 → mojibake. Always write with `encoding='utf-8-sig'`.
- **Anchors are the key feature.** The user's primary pain point is finding specific paragraphs in very long chats (300+ messages). Document-level search is not enough — every result must link to the exact message.
- **Topic auto-detection is heuristic.** The current keyword-based approach is simple. For better results, consider LLM-based topic extraction on the first pass.
- **Google Drive sync requires OAuth.** The `google-workspace` skill handles upload, but setup is non-trivial (Google Cloud Console project, OAuth consent screen, test user). Prioritize local search first; Google Drive is phase 2.

## Scripts

- `scripts/export_hermes.py` — Export Hermes Agent state.db sessions to markdown
- `scripts/search_kb.py` — Dual-mode search CLI (copy of the main search.py)