# Archive workflow — SQL queries and docx template

## 1. Inventory: list all sessions

```sql
SELECT id, title, started_at, ended_at, message_count, cwd
FROM sessions
ORDER BY started_at;
```

Column `cwd` holds the working directory — use it to detect project-bound sessions.

## 2. Find sessions by project (cwd match)

```sql
SELECT id, title, started_at, ended_at, message_count
FROM sessions
WHERE cwd LIKE '%PROJECT_NAME%'
ORDER BY started_at;
```

## 3. Get session metadata for one session

```sql
SELECT id, title, started_at, ended_at, message_count, model
FROM sessions
WHERE id = ?;
```

## 4. Get all user+assistant messages (chronological)

```sql
SELECT role, content, timestamp
FROM messages
WHERE session_id = ? AND role IN ('user', 'assistant')
ORDER BY id;
```

## 5. Count messages per session (noise detection)

```sql
SELECT session_id, COUNT(*) as msg_count
FROM messages
GROUP BY session_id
ORDER BY msg_count;
```

Sessions with ≤2 messages are typically `dead` type (interrupted/cron no-op).

## 6. Schema overview

```sql
PRAGMA table_info(sessions);
PRAGMA table_info(messages);
```

## Python: build .docx (template)

```python
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import sqlite3, datetime

DB = r'C:\Users\Yuri\AppData\Local\hermes\state.db'
OUTPUT = r'G:\_My_Programming\HERMES-AGENT\HERMES-1-ARCHIVE\PROJECTS\PROJECT_NAME.docx'

doc = Document()

# Title
t = doc.add_heading('PROJECT NAME', level=0)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Sessions loop
for session_info in session_list:
    # Get meta
    cur = db.execute(
        'SELECT id, title, started_at, ended_at, message_count, model '
        'FROM sessions WHERE id=?', (session_info['id'],))
    row = cur.fetchone()
    
    doc.add_heading(f"Сессия N: {session_info['title']}", level=2)
    
    # Metadata table
    table = doc.add_table(rows=5, cols=2)
    table.style = 'Light Shading Accent 1'
    for i, (k, v) in enumerate(...):
        table.rows[i].cells[0].text = k
        table.rows[i].cells[1].text = v
    
    # Messages
    cur2 = db.execute(
        'SELECT role, content, timestamp FROM messages '
        'WHERE session_id=? AND role IN ("user","assistant") ORDER BY id',
        (session_info['id'],))
    for role, content, ts in cur2.fetchall():
        # limit content to 3000 chars for large sessions
        ...

doc.save(OUTPUT)
```

## Key decisions section — common patterns to look for in session transcripts

- Architecture decisions (2-agent, native vs WSL, etc.)
- File locations that changed (skills, config, secrets)
- Git workflow (rebase vs merge, conflict resolution strategy)
- Integration points (Telegram, cron, rclone, Google Drive)
- Tool adoptions (yt-dlp, python-docx, specific model choices)