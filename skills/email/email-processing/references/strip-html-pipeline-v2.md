# strip_html() pipeline v2 — TASK-010 improvements (2026-07-23)

Full pipeline order used in `POST-MAIL-AUTOMATION/app/imap_client.py:strip_html()`:

1. Early return if text is empty
2. `\r\n` → `\n` (CRLF normalisation)
3. If text contains structural HTML tags (`html|body|div|table|a |img`):
   - Strip `<style>` blocks
   - Strip `<script>` blocks
   - Replace all remaining tags with `\n`
4. Multiple spaces/tabs → single space
5. 3+ consecutive newlines → 2 newlines (prepares for paragraph grouping)
6. HTML entity replacements:
   - `&nbsp;` → space
   - `&amp;` → `&`
   - `&lt;` → `<`
   - `&gt;` → `>`
   - `&zwnj;` → `""`
   - `&zwsp;` → `""`
   - `&#8202;` through `&#8205;` → `""`
6a. **(TASK-012) Strip raw Unicode zero-width / control chars** that bypass entity handling:
   ```python
   ZERO_WIDTH_RE = re.compile(r'[\u2000-\u200f\u2028-\u202f\u034f\u2800\ufeff]')
   text = ZERO_WIDTH_RE.sub('', text)
   ```
   Covers: U+2000–U+200A (En Quad…Hair Space), U+200B–U+200F (ZWSP, ZWNJ, ZWJ, LRM, RLM), U+2028–U+202F (line/paragraph/word-joiner separators), U+034F (CGJ), U+2800 (Braille Pattern Blank), U+FEFF (BOM). See `references/unicode-zero-width-raw.md` for the why behind the range.
7. Split by `\n`, strip each line; preserve exactly one blank line between paragraph groups
8. Remove leading isolated digit artifact (1-999) on first line
9. Deduplicate consecutive identical lines (keep one). **(TASK-012) compare on the *visible* form** (after the ZERO_WIDTH_RE pass), so that `"X\u2800"` and `"X"` are detected as duplicates — see `references/unicode-zero-width-raw.md` for the exact helper.
10. Trim leading/trailing blank lines
11. Rejoin with `\n`

## Blank-line preservation logic

```python
raw_lines = text.split('\n')
lines = []
blank_streak = 0
for line in raw_lines:
    stripped = line.strip()
    if stripped:
        lines.append(stripped)
        blank_streak = 0
    else:
        blank_streak += 1
        if blank_streak == 1 and lines:
            lines.append('')  # keep one blank line
```

## Dedup logic

```python
# After TASK-012: compare on the *visible* form, so that "X" and "X\u2800"
# are treated as duplicates even after the Unicode zero-width pass.
def _visible(s: str) -> str:
    ZERO_WIDTH_RE = re.compile(r'[\u2000-\u200f\u2028-\u202f\u034f\u2800\ufeff]')
    return ZERO_WIDTH_RE.sub('', s)

deduped = []
for line in lines:
    if line == '':
        deduped.append(line)
    elif deduped and _visible(deduped[-1]) != '' and _visible(deduped[-1]) == _visible(line):
        continue  # skip any consecutive visible-duplicate
    else:
        deduped.append(line)
```

**Pitfall:** the original raw-equality dedup let garbage lines through when one occurrence of a line carried a residual `\u2800` (or any other zero-width char) and the next didn't. Fix shipped in commit `6d698f9` (TASK-012). See `references/unicode-zero-width-raw.md` for the test corpus that catches this.

## Truncation indicator

```python
def _truncate_with_indicator(body: str, max_chars: int = 2000) -> str:
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rstrip() + "\n... [truncated]"
```

## Newsletter filter pattern

```python
NEWSLETTER_DOMAINS = (".aliexpress.com", ".puzat.ru")
NEWSLETTER_KEYWORDS = ("unsubscribe", "отписаться", "отписать")

def _is_newsletter(msg) -> bool:
    from_lower = msg.from_.lower()
    for domain in NEWSLETTER_DOMAINS:
        if domain in from_lower:
            return True
    body = (msg.text or msg.html or "").lower()
    for kw in NEWSLETTER_KEYWORDS:
        if kw in body:
            return True
    return False
```

## IMAP date range filtering

`imap_tools` supports these date operators:
- `A(date_gte=date)` — on or after date
- `A(date_lte=date)` — on or before date
- `A(date_lt=date)` — strictly before date
- `A(date_gt=date)` — strictly after date

Combine with `AND(...)`. Priority: explicit `--from-date`/`--to-date` beats `--days`.