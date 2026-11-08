# Hermes state.db Schema

Path: `%LOCALAPPDATA%/hermes/state.db`

## sessions

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Session ID (e.g. `20260708_072330_f2319d`) |
| source | TEXT | `tui`, `cron`, `subagent` |
| model | TEXT | Full model ID (e.g. `deepseek/deepseek-v4-pro`) |
| model_config | TEXT | JSON config |
| system_prompt | TEXT | System prompt content |
| parent_session_id | TEXT | For subagent delegation |
| started_at | REAL | Unix timestamp |
| ended_at | REAL | Unix timestamp |
| end_reason | TEXT | |
| message_count | INTEGER | |
| tool_call_count | INTEGER | |
| input_tokens | INTEGER | |
| output_tokens | INTEGER | |
| estimated_cost_usd | REAL | |
| title | TEXT | Session title (may be null) |
| archived | INTEGER | 0 = active, 1 = archived |

## messages

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment, unique across all sessions |
| session_id | TEXT | FK to sessions.id |
| role | TEXT | `user`, `assistant`, `system`, `tool` |
| content | TEXT | Message body (may be JSON for tool results) |
| tool_call_id | TEXT | |
| tool_calls | TEXT | JSON array of function calls |
| tool_name | TEXT | Tool name for tool-result messages |
| timestamp | REAL | Unix timestamp |
| reasoning_content | TEXT | Model reasoning (if applicable) |
| active | INTEGER | 1 = active, 0 = compacted/removed |

## FTS

- `messages_fts` — full-text search index on message content
- `messages_fts_trigram` — trigram index for substring matching

## Key queries

```sql
-- All non-archived, non-subagent sessions
SELECT * FROM sessions WHERE archived = 0 AND source != 'subagent' ORDER BY started_at ASC;

-- Active messages for a session
SELECT id, role, content, tool_calls, tool_name, timestamp
FROM messages WHERE session_id = ? AND active = 1 ORDER BY id ASC;

-- Filter out system noise
-- Messages with: "active model for this chat has changed"
-- or: "from this point forward, use this runtime metadata"
-- These are internal Hermes model-switch announcements.
```

## Noise patterns to filter

1. **System messages** containing `"active model for this chat has changed"` or `"from this point forward, use this runtime metadata"` — model-switch announcements, not user content.
2. **Tool results** with content < 15 chars — empty/near-empty responses.
3. **Subagent sessions** (`source='subagent'`) — 2-message wrappers with no real content.