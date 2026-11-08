# SQL Queries for Session Archive

All queries run against `C:\Users\Yuri\AppData\Local\hermes\state.db` (or `%LOCALAPPDATA%\hermes\state.db`).

## Schema

```sql
-- sessions table
id TEXT PRIMARY KEY,           -- e.g. '20260802_213459_425ffc'
source TEXT,                   -- 'tui', 'cli', 'telegram', etc.
model TEXT,                    -- 'deepseek/deepseek-v4-flash'
started_at REAL,               -- unix timestamp
ended_at REAL,                 -- unix timestamp or NULL
message_count INTEGER,         -- total messages incl. tool calls
cwd TEXT,                      -- working directory at session start
title TEXT,                    -- session title or NULL
model_config TEXT,             -- JSON with provider/model config
estimated_cost_usd REAL,
actual_cost_usd REAL

-- messages table
id INTEGER PRIMARY KEY,
session_id TEXT REFERENCES sessions(id),
role TEXT,                     -- 'user', 'assistant', 'tool'
content TEXT,                  -- message content
timestamp REAL,                -- unix timestamp
tool_call_id TEXT,
tool_name TEXT
```

## Query 1: List All Sessions

```python
import sqlite3, datetime
db = sqlite3.connect(r'C:\Users\Yuri\AppData\Local\hermes\state.db')
cur = db.execute('SELECT id, title, started_at, ended_at, message_count, cwd FROM sessions ORDER BY started_at')
for r in cur:
    sid, title, started, ended, msgs, cwd = r
    dt = datetime.datetime.fromtimestamp(started).strftime('%Y-%m-%d %H:%M')
    print(f'{sid} | {dt} | msgs={msgs:3d} | cwd={cwd or "none"} | {title or "(no title)"}')
```

## Query 2: Sessions by Project (cwd)

```python
cur = db.execute("SELECT id, title, started_at, message_count FROM sessions WHERE cwd LIKE '%PROJECT-NAME%' ORDER BY started_at")
```

## Query 3: Sessions by Title Keyword

```python
cur = db.execute("SELECT id, title, started_at, message_count FROM sessions WHERE title LIKE '%keyword%' ORDER BY started_at")
```

## Query 4: Sessions in Date Range

```python
import datetime
start_ts = datetime.datetime(2026, 7, 24).timestamp()
end_ts = datetime.datetime(2026, 7, 26).timestamp()
cur = db.execute("SELECT id, title, started_at, message_count, cwd FROM sessions WHERE started_at >= ? AND started_at < ? ORDER BY started_at", (start_ts, end_ts))
```

## Query 5: Get All Messages from a Session

```python
cur = db.execute('SELECT role, content, timestamp FROM messages WHERE session_id=? AND role IN ("user", "assistant") ORDER BY id', (sid,))
```

## Query 6: Session Metadata

```python
cur = db.execute('SELECT id, title, started_at, ended_at, message_count, model FROM sessions WHERE id=?', (sid,))
```

## Query 7: Session Columns (for reference)

```python
cur = db.execute("PRAGMA table_info(sessions)")
for r in cur:
    print(r)  # (cid, name, type, notnull, dflt_value, pk)
```

## Utility: Timestamp Formatting

```python
def fmt_ts(ts):
    if ts:
        return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    return 'n/a'
```

## Full Example: Build Document Builder

```python
def build_doc(title_heading, filename, session_specs, summary_text, decisions, dirs_text):
    db = sqlite3.connect(DB)
    doc = Document()
    # ... title, summary, header ...
    for sid, order, stitle in session_specs:
        # get session meta
        cur = db.execute('SELECT id, title, started_at, ended_at, message_count, model FROM sessions WHERE id=?', (sid,))
        row = cur.fetchone()
        # add metadata table and dialog
        cur2 = db.execute('SELECT role, content, timestamp FROM messages WHERE session_id=? AND role IN ("user","assistant") ORDER BY id', (sid,))
        for role, content, ts in cur2:
            # format and add to doc
            pass
    # add key decisions section
    db.close()
```

## Path Resolution on Windows (MSYS vs Native)

| Tool | `/g/...` path | `C:\...` path |
|------|---------------|---------------|
| `terminal` (bash) | ✅ Works | ✅ Works |
| `write_file` | ❌ → `C:\g\...` | ✅ Must use `C:\...` |
| `patch` | ❌ → `C:\c\...` | ✅ Must use `C:\...` |
| `python3` in terminal | ✅ `/c/Users/...` works | ✅ `C:\Users\...` works |

**Rule:** In `terminal` commands, use MSYS paths (`/c/Users/...`). In `write_file`/`patch` tools, use native Windows paths (`C:\Users\...`).