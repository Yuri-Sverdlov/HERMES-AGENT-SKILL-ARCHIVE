#!/usr/bin/env python3
"""
Search the LLM Knowledge Base with two modes:

  --docs   Document-level search: list all matching files with metadata.
  --paras  Paragraph-level search: specific paragraphs with context + anchor links.

Output includes anchor links (file.md#msg-N) that jump directly to the message.

Usage:
    python search.py --docs "python project"
    python search.py --paras "nsfw scenes"
    python search.py --paras "nsfw" --context 3       # 3 lines of context
    python search.py --paras "config" --model deepseek  # filter by model
    python search.py --docs "" --topic prose            # all docs in topic
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import Iterator

# --- config ---
DEFAULT_DIR = Path("G:/_My_Programming/LLM-KNOWLEDGE-BASE/hermes-chats")


# --- document model ---

class Document:
    """Represents one exported session .md file."""
    def __init__(self, path: Path):
        self.path = path
        self.filename = path.name
        self.frontmatter = {}
        self.title = ""
        self.body = ""
        self._messages: list[dict] | None = None
        self._parse()

    def _parse(self):
        """Read file and extract frontmatter + body."""
        with open(self.path, 'r', encoding='utf-8-sig') as f:
            text = f.read()

        fm_match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
        if fm_match:
            self.body = text[fm_match.end():]
            fm_text = fm_match.group(1)
            for line in fm_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, _, value = line.partition(':')
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if value.startswith('[') and value.endswith(']'):
                        value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(',') if v.strip()]
                    elif value.replace('.', '', 1).replace('-', '', 1).isdigit():
                        try:
                            value = int(value)
                        except ValueError:
                            try:
                                value = float(value)
                            except ValueError:
                                pass
                    self.frontmatter[key] = value
        else:
            self.body = text

        self.title = self.frontmatter.get('title', self.filename)

    @property
    def model(self) -> str:
        return self.frontmatter.get('model', '?')

    @property
    def date(self) -> str:
        return self.frontmatter.get('date', '?')

    @property
    def topics(self) -> list[str]:
        return self.frontmatter.get('topics', [])

    @property
    def message_count(self) -> int:
        return int(self.frontmatter.get('message_count', 0))

    def messages(self) -> list[dict]:
        """Parse body into individual message blocks with anchors and line numbers."""
        if self._messages is not None:
            return self._messages

        messages = []
        pattern = re.compile(
            r'<a id="msg-(\d+)"></a>\n'
            r'(### .*?\n)'
            r'\n'
            r'(.*?)'
            r'(?=\n<a id="msg-|\Z)',
            re.DOTALL
        )

        lines = self.body.split('\n')
        line_positions = []
        pos = 0
        for line in lines:
            line_positions.append(pos)
            pos += len(line) + 1

        def line_number(char_pos: int) -> int:
            for i, lp in enumerate(line_positions):
                if lp >= char_pos:
                    return i
            return len(lines)

        for m in pattern.finditer(self.body):
            msg_id = int(m.group(1))
            heading = m.group(2).strip()
            content = m.group(3).strip()
            start_line = line_number(m.start())

            clean_content = '\n'.join(
                line[2:] if line.startswith('> ') else (line[1:] if line.startswith('>') else line)
                for line in content.split('\n')
            )

            role = 'unknown'
            if 'User' in heading:
                role = 'user'
            elif 'Assistant' in heading:
                role = 'assistant'
            elif 'System' in heading:
                role = 'system'
            elif 'Tool' in heading:
                role = 'tool'

            messages.append({
                'id': msg_id,
                'role': role,
                'heading': heading,
                'content': clean_content,
                'raw_content': content,
                'line': start_line + 1,
            })

        self._messages = messages
        return messages

    def search_messages(self, query: str, context_lines: int = 2) -> list[dict]:
        """Search within this document's messages for query matches."""
        results = []
        msgs = self.messages()
        query_lower = query.lower()

        for i, msg in enumerate(msgs):
            if query_lower in msg['content'].lower():
                context_before = msgs[max(0, i - 1):i]
                context_after = msgs[i + 1:i + 1 + context_lines]

                snippet = msg['content']
                if len(snippet) > 500:
                    idx = snippet.lower().find(query_lower)
                    start = max(0, idx - 200)
                    end = min(len(snippet), idx + len(query) + 300)
                    snippet = ('...' if start > 0 else '') + snippet[start:end] + ('...' if end < len(snippet) else '')

                results.append({
                    'file': self.filename,
                    'msg_id': msg['id'],
                    'role': msg['role'],
                    'line': msg['line'],
                    'snippet': snippet,
                    'anchor': f'{self.filename}#msg-{msg["id"]}',
                    'context_before': [{'role': m['role'], 'snippet': m['content'][:200]} for m in context_before],
                    'context_after': [{'role': m['role'], 'snippet': m['content'][:200]} for m in context_after],
                })

        return results


# --- document loader ---

def load_documents(directory: Path) -> list[Document]:
    """Load all .md files from the directory."""
    docs = []
    for fp in sorted(directory.glob('*.md')):
        docs.append(Document(fp))
    return docs


# --- search modes ---

def search_docs(docs: list[Document], query: str,
                model_filter: str | None = None,
                topic_filter: str | None = None) -> list[dict]:
    """Document-level search: return matching files with metadata."""
    results = []
    query_lower = query.lower() if query else ''

    for doc in docs:
        if model_filter and model_filter.lower() not in doc.model.lower():
            continue
        if topic_filter and topic_filter not in doc.topics:
            continue

        if query_lower:
            body_matches = doc.body.lower().count(query_lower)
            title_match = query_lower in doc.title.lower()
            if body_matches == 0 and not title_match:
                continue
        else:
            body_matches = 0
            title_match = True

        snippet = ''
        if query_lower and body_matches > 0:
            idx = doc.body.lower().find(query_lower)
            start = max(0, idx - 80)
            end = min(len(doc.body), idx + len(query) + 120)
            snippet = doc.body[start:end].replace('\n', ' ').strip()
            if start > 0:
                snippet = '...' + snippet
            if end < len(doc.body):
                snippet += '...'

        results.append({
            'file': doc.filename,
            'title': doc.title,
            'model': doc.model,
            'date': doc.date,
            'topics': doc.topics,
            'messages': doc.message_count,
            'matches': body_matches,
            'title_match': title_match,
            'snippet': snippet,
            'path': str(doc.path),
        })

    results.sort(key=lambda r: (-r['title_match'], -r['matches']))
    return results


def search_paras(docs: list[Document], query: str,
                 model_filter: str | None = None,
                 topic_filter: str | None = None,
                 context_lines: int = 2) -> list[dict]:
    """Paragraph-level search: return specific messages matching query."""
    all_results = []

    for doc in docs:
        if model_filter and model_filter.lower() not in doc.model.lower():
            continue
        if topic_filter and topic_filter not in doc.topics:
            continue

        msg_results = doc.search_messages(query, context_lines)
        for r in msg_results:
            r['file_path'] = str(doc.path)
            r['doc_title'] = doc.title
            r['doc_model'] = doc.model
            r['doc_date'] = doc.date
            all_results.append(r)

    all_results.sort(key=lambda r: (
        0 if r['role'] == 'user' else 1,
        r['doc_date'] or '',
    ), reverse=False)

    return all_results


# --- output formatters ---

def format_docs_table(results: list[dict]) -> str:
    """Format document results as a readable table."""
    if not results:
        return '(Nothing found)'

    lines = [f'Documents found: {len(results)}', '=' * 80, '']
    for i, r in enumerate(results, 1):
        lines.append(f'{i}. **{r["title"]}**')
        lines.append(f'   File: `{r["file"]}`')
        lines.append(f'   Model: {r["model"]} | Date: {r["date"]} | Messages: {r["messages"]}')
        if r['topics']:
            lines.append(f'   Topics: {", ".join(r["topics"])}')
        lines.append(f'   Matches: {r["matches"]}' + (' (in title)' if r['title_match'] else ''))
        if r['snippet']:
            lines.append(f'   Snippet: {r["snippet"][:200]}')
        lines.append('')
    return '\n'.join(lines)


def format_paras_table(results: list[dict]) -> str:
    """Format paragraph results with context and anchor links."""
    if not results:
        return '(Nothing found)'

    lines = [f'Paragraphs found: {len(results)}', '=' * 80, '']
    for i, r in enumerate(results, 1):
        lines.append(f'**#{i}** - {r["doc_title"]}')
        lines.append(f'File: `{r["file"]}` | Model: {r["doc_model"]} | Date: {r["doc_date"]}')
        lines.append(f'Link: `{r["anchor"]}` (line ~{r["line"]})')
        lines.append('')

        if r['context_before']:
            for cb in r['context_before']:
                role_tag = 'U' if cb['role'] == 'user' else 'A'
                lines.append(f'   [{role_tag}] {cb["snippet"][:150]}')
            lines.append('')

        lines.append(f'   >>> {r["role"].upper()} >>>')
        for line in r['snippet'].split('\n')[:5]:
            lines.append(f'   {line}')
        lines.append('   <<<')

        if r['context_after']:
            lines.append('')
            for ca in r['context_after']:
                role_tag = 'U' if ca['role'] == 'user' else 'A'
                lines.append(f'   [{role_tag}] {ca["snippet"][:150]}')

        lines.append('')
        lines.append('-' * 80)
        lines.append('')
    return '\n'.join(lines)


# --- main ---

def main():
    parser = argparse.ArgumentParser(
        description='Search the LLM Chat Knowledge Base',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search.py --docs "python project"
  python search.py --paras "nsfw scenes"
  python search.py --paras "nsfw" --context 3
  python search.py --paras "config" --model deepseek
  python search.py --docs "" --topic prose
        """,
    )
    parser.add_argument('query', nargs='?', default='', help='Search query')
    parser.add_argument('--docs', action='store_true', help='Document-level search mode')
    parser.add_argument('--paras', action='store_true', help='Paragraph-level search mode')
    parser.add_argument('--model', type=str, help='Filter by model (e.g. deepseek, claude)')
    parser.add_argument('--topic', type=str, help='Filter by topic (e.g. prose, python, hermes)')
    parser.add_argument('--context', type=int, default=2, help='Context lines for --paras (default: 2)')
    parser.add_argument('--dir', type=Path, default=DEFAULT_DIR, help='Directory with .md files')
    parser.add_argument('--json', action='store_true', help='JSON output')

    args = parser.parse_args()

    if not args.docs and not args.paras:
        if args.query.strip():
            args.docs = True
        else:
            parser.print_help()
            sys.exit(1)

    if not args.dir.exists():
        print(f'ERROR: Directory not found: {args.dir}')
        print(f'  Run export first to generate .md files.')
        sys.exit(1)

    docs = load_documents(args.dir)
    if not docs:
        print(f'No .md files found in {args.dir}')
        print(f'  Run export first.')
        sys.exit(1)

    print(f'Loaded: {len(docs)} documents from {args.dir}')
    print(f'Query: "{args.query}"')
    if args.model:
        print(f'Model filter: {args.model}')
    if args.topic:
        print(f'Topic filter: {args.topic}')
    print()

    query = args.query.strip().lower() if args.query else ''

    if args.docs:
        results = search_docs(docs, query, args.model, args.topic)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(format_docs_table(results))

    if args.paras:
        if not query:
            print('ERROR: --paras requires a search query')
            sys.exit(1)
        results = search_paras(docs, query, args.model, args.topic, args.context)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(format_paras_table(results))


if __name__ == '__main__':
    main()