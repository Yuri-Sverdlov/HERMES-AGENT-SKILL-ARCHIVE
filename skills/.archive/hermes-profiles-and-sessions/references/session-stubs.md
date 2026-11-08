# Creating empty session stubs in a Hermes profile

Goal: seed a profile with labelled, empty placeholder chats (e.g. `[ПРОЗА] ...`)
WITHOUT starting real chats (which cost API calls and need keys).

## state.db location

- Default profile: `<HERMES_HOME>/state.db`
  (Windows: `C:\Users\<user>\AppData\Local\hermes\state.db`)
- Named profile: `<HERMES_HOME>/profiles/<name>/state.db`

A new profile's `state.db` does NOT exist until first use. Create it first
(step 1 below).

## sessions table — relevant columns

`id` is the primary key and follows the format `YYYYMMDD_HHMMSS_<6hexchars>`.
The human-visible name is the `title` column. Other columns used by stubs:
`source` (e.g. `'cli'`), `started_at` (REAL unix epoch), `message_count`
(0 for a stub), `archived` (0). The table has ~33 columns total but the rest
default fine when omitted.

The DB also has `messages` + several `messages_fts*` virtual tables and triggers.
The FTS index is over `messages`, so inserting zero-message `sessions` rows is
safe.

## Step 1 — create a correct empty state.db for the profile

Do NOT hand-write the schema (FTS5 virtual tables + triggers are fiddly).
Instead copy the default DB and wipe its data — that yields the exact correct
empty schema:

```python
import sqlite3, shutil, os
src = r'C:\Users\<user>\AppData\Local\hermes\state.db'
dstdir = r'C:\Users\<user>\AppData\Local\hermes\profiles\creative'
dst = os.path.join(dstdir, 'state.db')
os.makedirs(dstdir, exist_ok=True)
shutil.copy(src, dst)
c = sqlite3.connect(dst)
for t in ('messages', 'sessions'):
    c.execute(f'DELETE FROM {t}')
try:
    c.execute("INSERT INTO messages_fts(messages_fts) VALUES('delete-all')")  # clear FTS
except Exception:
    pass
c.commit(); c.close()
```

## Step 2 — insert labelled stub rows

```python
import sqlite3, time, random, datetime
dst = r'C:\Users\<user>\AppData\Local\hermes\profiles\creative\state.db'
c = sqlite3.connect(dst)
stubs = [
    ('[ПРОЗА]',     'Художественная проза — черновики'),
    ('[РАССКАЗ]',   'Короткие рассказы — идеи'),
    ('[ПЕРСОНАЖИ]', 'Проработка персонажей'),
]
base = time.time()
for i, (pfx, desc) in enumerate(stubs):
    ts = base - i*60  # stagger so ordering is stable
    dt = datetime.datetime.fromtimestamp(ts)
    sid = dt.strftime('%Y%m%d_%H%M%S') + '_' + ('%06x' % random.randint(0, 0xffffff))
    c.execute(
        'INSERT INTO sessions (id, source, started_at, message_count, title, archived) '
        'VALUES (?,?,?,?,?,?)',
        (sid, 'cli', ts, 0, f'{pfx} {desc}', 0))
c.commit(); c.close()
```

## Step 3 — verify via the real CLI (not just raw SQL)

```bash
hermes -p creative sessions list
```

This confirms Hermes recognizes the rows. A raw `SELECT` proving they're in the
file is NOT sufficient — the point is that the CLI/app surfaces them.

## Gotcha that wasted time this session

`HERMES_PROFILE=creative hermes sessions list` showed the DEFAULT profile's
sessions, making it look like the stubs failed. The profile is selected by the
**`-p` flag**, not that env var. Always test with `hermes -p <name> ...`.
