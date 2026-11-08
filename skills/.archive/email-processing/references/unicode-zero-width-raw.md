# Raw Unicode zero-width / control chars — TASK-012 finding

**Date:** 2026-07-24
**Project:** POST-MAIL-AUTOMATION
**File:** `app/imap_client.py → strip_html()`
**Commit:** `6d698f9` (TASK-012)

## The gap the existing skill missed

`strip_html()` handled HTML-entities (`&zwnj;`, `&zwsp;`, `&#8202-5;`) but **not the raw Unicode code points themselves**. Emails from `roycenter.co.il` (and similar) contained raw `\u200B`–`\u200F`, `\u2800`, `\u034F` etc. that bypassed entity handling and produced 200+ char garbage lines.

## The regex (working)

```python
# After HTML-entity replacements, run a single pass:
ZERO_WIDTH_RE = re.compile(r'[\u2000-\u200f\u2028-\u202f\u034f\u2800\ufeff]')
text = ZERO_WIDTH_RE.sub('', text)
```

### Why this exact range, not `\u200b-\u200f` (my first attempt)

My first regex was `[\u200b-\u200f\u2028-\u202f\u034f\u2800\ufeff]` — and **test T7 failed**: U+2007 (Figure Space) was not in that range. U+2007 lives in `U+2000`–`U+200A` (General Punctuation, spaces), not in the zero-width block.

| Code point | Name | Block | In `\u200b-\u200f`? | In `\u2000-\u200f`? |
|---|---|---|---|---|
| U+2000 | En Quad | Spaces | ❌ | ✅ |
| U+2007 | Figure Space | Spaces | ❌ | ✅ |
| U+200A | Hair Space | Spaces | ❌ | ✅ |
| U+200B | ZWSP | Zero-width | ✅ | ✅ |
| U+200C | ZWNJ | Zero-width | ✅ | ✅ |
| U+200D | ZWJ | Zero-width | ✅ | ✅ |
| U+200E | LRM | Zero-width | ✅ | ✅ |
| U+200F | RLM | Zero-width | ✅ | ✅ |
| U+2028 | Line Separator | Separators | (own range) | (own range) |
| U+2029 | Paragraph Separator | Separators | (own range) | (own range) |
| U+202A–U+202F | Bidi controls | Separators | (own range) | (own range) |
| U+034F | Combining Grapheme Joiner | Combining marks | (own code) | (own code) |
| U+2800 | Braille Pattern Blank | Braille | (own code) | (own code) |
| U+FEFF | BOM / ZWNBSP | Arabic Presentation Forms-B | (own code) | (own code) |

**Lesson:** When in doubt about Unicode whitespace/control ranges, cast a wider net (`\u2000-\u200f` covers all of U+2000–U+200F in one go) and add the truly out-of-band ones explicitly.

## The dedup pitfall (also part of TASK-012)

Naive dedup compares on raw string equality:

```python
elif deduped and deduped[-1] == line:    # raw equality
    continue
```

This fails when upstream Unicode cleanup left a residual zero-width char on one line but not its duplicate:

```
"X\u2800"      # first occurrence, with trailing Braille blank
"X"            # second occurrence, clean
"X\u2800"      # third, again with residual
```

The naive dedup sees three distinct lines, not duplicates. After Unicode cleanup the dedup **must** compare on the *visible* form:

```python
def _visible(s: str) -> str:
    return ZERO_WIDTH_RE.sub('', s)

elif deduped and _visible(deduped[-1]) != '' and _visible(deduped[-1]) == _visible(line):
    continue
```

## Test corpus (21 tests, all green)

File: `tests/test_strip_html.py`. Run: `python tests/test_strip_html.py` — works with stdlib only (no pytest needed).

### New functionality (11 tests)

1. ZWSP between words removed
2. 200× U+2800 → empty string
3. BOM stripped from start
4. Dedup of `X\u2800` + `X` + `Y` → `X\nY`
5. Real UID 84284 garbage: 448 chars of `\u200B`/`\u200C`/`\u034F`/`\u2800` → 22 chars of clean text
6. ZWJ (U+200D) stripped
7. Figure Space (U+2007) stripped — **this caught my first regex bug**
8. CGJ (U+034F) stripped
9. En Quad (U+2000) stripped
10. Hair Space (U+200A) stripped
11. Empty string / None → empty string

### Backward-compat (10 tests)

1. HTML tags removed
2. HTML entities decoded (`&lt;`, `&gt;`, `&amp;`, `&nbsp;`)
3. Whitespace normalized
4. "96" prefix artifact removed
5. Triple+ blank lines collapsed to one
6. Identical-line dedup still works
7. `&zwnj;` entity removed
8. Clean text untouched
9. Cyrillic + Latin preserved
10. Multi-paragraph structure preserved

## Sample real-world output (UID 84284, roycenter.co.il)

**Before TASK-012:** 448+ char body of mixed `\u200C`, `\u200B`, `\u034F`, `\u2800` between subject and content.

**After TASK-012:** `"Одна история с ретрита"` — clean, 22 chars.

## Hermes skills discovery note

`hermes skills list` shows the `email-*` local skills as `enabled`, but `hermes skills inspect <name>` does NOT find them — it queries the skills.sh hub and offers hub alternatives instead. For local skills, use:

- `skill_view(name="mail-inbox")` (works in chat)
- `hermes --cli -z "..." --skills "mail-inbox"` (works in terminal)

Worth knowing when debugging "why doesn't Hermes see my new skill?"
