#!/usr/bin/env python3
"""
Export Hermes Agent sessions from state.db to organised markdown files.

Each session -> one .md file with YAML frontmatter and anchored messages.
Anchors (<a id="msg-N"></a>) enable paragraph-level search navigation.

Usage:
    python export.py                          # export all sessions
    python export.py --db path/to/state.db    # custom DB path
    python export.py --out path/to/output/    # custom output dir
"""

import sqlite3
import json
import re
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

# --- config ---
DEFAULT_DB = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "state.db"
DEFAULT_OUT = Path("G:/_My_Programming/LLM-KNOWLEDGE-BASE/hermes-chats")


# --- helpers ---

def sanitise_filename(s: str, max_len: int = 80) -> str:
    """Turn a string into a safe filename fragment."""
    if not s:
        return "untitled"
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    }
    result = []
    for ch in s:
        if ch in translit:
            result.append(translit[ch])
        elif ch.isalnum() or ch in ' -_':
            result.append(ch)
        else:
            result.append('-')
    clean = re.sub(r'[-]+', '-', ''.join(result)).strip('-').lower()
    return clean[:max_len] if clean else "untitled"


def extract_title(session_row: dict, messages: list[dict]) -> str:
    """Derive a title from session data or first user message."""
    title = session_row.get('title', '')
    if title and title.strip():
        return title[:120] if len(title) > 120 else title

    for msg in messages:
        if msg['role'] == 'user' and msg['content']:
            text = msg['content'].strip()
            first_line = text.split('\n')[0].strip()
            return first_line[:120] if len(first_line) > 120 else first_line

    return "Untitled"


def extract_topics(messages: list[dict], title: str) -> list[str]:
    """Extract topic keywords from title and messages (simple heuristic)."""
    keyword_sets = {
        'python': ['python', 'pip', 'pytest', 'django', 'flask', 'uv', 'poetry', 'pyenv'],
        'prose': ['story', 'scene', 'character', 'prose', 'nsfw', 'fiction', 'writing'],
        'hermes': ['hermes', 'agent', 'cli', 'config', 'skill', 'profile', 'plugin', 'model'],
        'project': ['project', 'github', 'git', 'repo', 'deploy', 'directory', 'structure'],
        'video': ['youtube', 'video', 'transcript', 'screenshot', 'frame'],
        'analysis': ['analysis', 'data', 'chart', 'statistics', 'report', 'summary'],
        'memory': ['memory', 'guide', 'instructions', 'reminder', 'note'],
    }

    all_text = title.lower() + ' '
    for msg in messages[:10]:
        if msg['content']:
            all_text += msg['content'].lower() + ' '

    topics = []
    for topic, keywords in keyword_sets.items():
        if any(kw in all_text for kw in keywords):
            topics.append(topic)
    return topics


def format_message(msg: dict) -> str:
    """Format a single message as markdown with anchor."""
    role_emoji = {'user': 'User', 'assistant': 'Assistant', 'system': 'System', 'tool': 'Tool'}
    role_label = role_emoji.get(msg['role'], msg['role'].capitalize())

    ts = datetime.fromtimestamp(msg['timestamp']).strftime('%Y-%m-%d %H:%M:%S') if msg['timestamp'] else ''

    lines = [f'<a id="msg-{msg["id"]}"></a>']
    lines.append(f'### {role_label} - {ts}  *(#{msg["id"]})*')
    lines.append('')

    if msg['content']:
        content = msg['content']
        for line in content.split('\n'):
            lines.append(f'> {line}' if line.strip() else '>')
    else:
        lines.append('> *(empty)*')

    lines.append('')

    if msg['tool_calls']:
        try:
            tool_calls = json.loads(msg['tool_calls']) if isinstance(msg['tool_calls'], str) else msg['tool_calls']
            lines.append('**Tools called:**')
            for tc in tool_calls:
                fn = tc.get('function', {})
                name = fn.get('name', '?')
                args_str = fn.get('arguments', '{}')
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    args_compact = ', '.join(f'{k}={repr(v)[:60]}' for k, v in args.items())
                except (json.JSONDecodeError, TypeError):
                    args_compact = str(args_str)[:120]
                lines.append(f'- `{name}`({args_compact})')
            lines.append('')
        except (json.JSONDecodeError, TypeError):
            lines.append(f'**Tools:** `{str(msg["tool_calls"])[:200]}`')
            lines.append('')

    if msg['tool_name']:
        lines.append(f'*Result `{msg["tool_name"]}`*')
        lines.append('')

    return '\n'.join(lines)


# --- main export ---

def export_sessions(db_path: Path, out_dir: Path) -> list[Path]:
    """Export all sessions from state.db to markdown files."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM sessions
        WHERE archived = 0
        ORDER BY started_at DESC
    """)
    sessions = cursor.fetchall()

    out_dir.mkdir(parents=True, exist_ok=True)
    exported = []

    for sess in sessions:
        sess_dict = dict(sess)

        cursor.execute("""
            SELECT id, role, content, tool_calls, tool_name, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
        """, (sess_dict['id'],))
        messages = [dict(m) for m in cursor.fetchall()]

        if not messages:
            continue

        title = extract_title(sess_dict, messages)
        topics = extract_topics(messages, title)
        date_str = datetime.fromtimestamp(sess_dict['started_at']).strftime('%Y-%m-%d')
        model_short = sess_dict['model'].split('/')[-1] if sess_dict['model'] else 'unknown'

        fn = f"{date_str}_{model_short}_{sanitise_filename(title, 60)}.md"
        filepath = out_dir / fn

        fm = {
            'model': sess_dict['model'],
            'date': date_str,
            'source': sess_dict['source'],
            'title': title,
            'topics': topics,
            'message_count': len(messages),
            'session_id': sess_dict['id'],
            'tool_call_count': sess_dict['tool_call_count'] or 0,
            'input_tokens': sess_dict['input_tokens'] or 0,
            'output_tokens': sess_dict['output_tokens'] or 0,
            'estimated_cost_usd': sess_dict['estimated_cost_usd'],
        }

        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write('---\n')
            for key, value in fm.items():
                if isinstance(value, list):
                    f.write(f'{key}: [{", ".join(repr(v) for v in value)}]\n')
                elif value is None:
                    f.write(f'{key}: null\n')
                elif isinstance(value, str):
                    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                    f.write(f'{key}: "{escaped}"\n')
                else:
                    f.write(f'{key}: {value}\n')
            f.write('---\n\n')
            f.write(f'# {title}\n\n')
            f.write(f'**Model:** `{fm["model"]}` | **Date:** {fm["date"]} | **Messages:** {fm["message_count"]}\n')
            if topics:
                f.write(f'**Topics:** {", ".join(topics)}\n')
            f.write('\n---\n\n')
            for msg in messages:
                f.write(format_message(msg))

        exported.append(filepath)
        print(f'  OK {fn} ({len(messages)} msgs)')

    conn.close()
    return exported


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Export Hermes sessions to markdown')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB, help='Path to state.db')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT, help='Output directory')
    args = parser.parse_args()

    if not args.db.exists():
        print(f'ERROR: Database not found: {args.db}')
        print(f'  Default path: {DEFAULT_DB}')
        print(f'  Override with --db')
        sys.exit(1)

    print(f'Database: {args.db}')
    print(f'Output:   {args.out}')
    print('Exporting...')

    files = export_sessions(args.db, args.out)
    print(f'\nDone! {len(files)} sessions exported to {args.out}')


if __name__ == '__main__':
    main()