# Example: LLM Knowledge Base — Completed Full Workflow

A real completed idea-workflow cycle (Full mode, UI stage skipped).  
Used in session 2026-07-08 with user Yuri.

## Context
- **Idea:** Single-user web app to search all LLM chats
- **Stack:** Python/FastAPI, SQLite FTS5, vanilla JS, Fly.io
- **Interviews:** 10 questions, one at a time

## Artifacts produced
- `00-idea-capture.md` — captured from existing prototype context
- `01-design-doc.md` — 10 design decisions, product philosophy, technical shape
- `02-implementation-spec.md` — project structure, DB schema, 9 API endpoints, 3 phases, 8 ACs

## Key patterns that worked
1. **Start from what exists** — user had a working CLI prototype; interview filled gaps
2. **Recommend-then-confirm stack** — proposed defaults, got one-word approval
3. **Skip UI stage for backend-heavy projects** — cleaner numbering
4. **Research inline** — notes in spec header, not a separate file