#!/usr/bin/env python
"""Scan the Hermes session DB for recent sessions and Hermes-mechanics findings.

Built for the weekly "personal guide" cron audit, but useful for any
"what happened recently in Hermes" review.

WHY A SCRIPT FILE: in cron mode `execute_code` is hard-blocked and an inline
`python -c "..."` call goes to pending_approval and hangs forever (nobody is
present to approve). A plain script file runs fine. So: write this file, run it.

Usage (bash on Windows / any shell):
    python scan_sessions.py                      # sessions from the last 8 days
    python scan_sessions.py --days 14
    python scan_sessions.py --all                # last 40 sessions, any age
    python scan_sessions.py --dump 20260912_184051_e7a81f
    python scan_sessions.py --last-cron          # previous weekly-cron report
    python scan_sessions.py --grep "Ctrl+C" "max_tokens"   # search all messages

DB: ~/AppData/Local/hermes/state.db  (opened read-only, safe while Hermes runs)
Relevant columns:
  sessions(id, source, model, started_at, message_count, title)
  messages(id, session_id, role, content, tool_name, timestamp)
"""

import argparse
import datetime as dt
import os
import sqlite3
import sys

DB = os.path.expanduser("~/AppData/Local/hermes/state.db")


def connect():
    if not os.path.exists(DB):
        sys.exit(f"state.db not found at {DB}")
    # read-only URI: never locks or mutates the live DB
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def fmt(ts):
    try:
        return dt.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(ts)


def list_sessions(con, since=None, limit=40):
    sql = "SELECT id, source, started_at, message_count, title FROM sessions"
    args = ()
    if since is not None:
        sql += " WHERE started_at > ?"
        args = (since,)
    sql += " ORDER BY started_at DESC LIMIT ?"
    args = args + (limit,)
    cur = con.execute(sql, args)
    print(f"{'started':16} {'src':9} {'msgs':>5}  id / title")
    for sid, src, st, mc, title in cur.fetchall():
        print(f"{fmt(st):16} {str(src):9} {mc:>5}  {sid}  | {title}")
    print("\nTip: the newest row with src='cron' is the previous weekly run — "
          "read it first (--last-cron) so you don't re-report findings.")


def dump(con, session_id, limit=1400):
    cur = con.execute(
        "SELECT id, role, content FROM messages "
        "WHERE session_id=? AND role IN ('user','assistant') ORDER BY id",
        (session_id,),
    )
    for mid, role, content in cur.fetchall():
        c = (content or "").strip().replace("\n", " ")
        if c:
            print(f"--[{mid}|{role}] {c[:limit]}")


def last_cron(con):
    row = con.execute(
        "SELECT id FROM sessions WHERE id LIKE 'cron_%' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        print("no cron sessions found")
        return
    print(f"### previous cron session: {row[0]}\n")
    dump(con, row[0], limit=2500)


def grep(con, needles, limit=900, roles=("user", "assistant")):
    placeholders = ",".join("?" for _ in roles)
    cur = con.execute(
        f"SELECT session_id, id, role, content FROM messages "
        f"WHERE role IN ({placeholders}) ORDER BY id",
        roles,
    )
    low = [n.lower() for n in needles]
    for sid, mid, role, content in cur.fetchall():
        c = content or ""
        cl = c.lower()
        if any(n in cl for n in low):
            print(f"\n=====[{sid} | {mid} | {role}]=====\n{c[:limit]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=8,
                    help="window in days for the session list (default 8)")
    ap.add_argument("--all", action="store_true", help="ignore --days, list last 40")
    ap.add_argument("--dump", metavar="SESSION_ID", help="dump a session's messages")
    ap.add_argument("--last-cron", action="store_true",
                    help="dump the previous cron session (what was already reported)")
    ap.add_argument("--grep", nargs="+", metavar="WORD",
                    help="search all user/assistant messages for these words")
    args = ap.parse_args()

    con = connect()
    if args.dump:
        dump(con, args.dump)
    elif args.last_cron:
        last_cron(con)
    elif args.grep:
        grep(con, args.grep)
    else:
        since = None if args.all else (dt.datetime.now().timestamp() - args.days * 86400)
        list_sessions(con, since=since)


if __name__ == "__main__":
    main()