---
name: email-processing
description: Common pitfalls and verification patterns when programmatically extracting readable text from HTML emails. Use when building, testing, or debugging any email content extraction pipeline (IMAP, parsing, HTML stripping).
---

# Email content extraction — pitfalls & verification

## When to load

Load this skill whenever you are:
- Building or debugging an IMAP email client
- Extracting text from HTML emails (strip_html, BeautifulSoup, regex-based)
- Testing an email export/translation pipeline
- Reviewing email tool output for quality

## Common HTML-stripping gaps

When stripping HTML from emails, standard regex-based cleaners often miss these:

| Gap | Symptom | Fix |
|---|---|---|
| HTML entities (`&zwnj;`, `&zwj;`) | Visible `&zwnj;` litter in output | Add to entity-replacement list: `&zwnj; → ""`, `&zwj; → ""` |
| **Raw Unicode zero-width / control chars** (bypasses `&zwnj;` / `&#8202-5;` entity handling) | Invisible garbage that survives entity replacement: `\u200B` (ZWSP), `\u200C` (ZWNJ), `\u200D` (ZWJ), `\u2007` (Figure Space), `\u2000`–`\u200A` (En Quad…Hair Space), `\u034F` (CGJ), `\u2800` (Braille Pattern Blank — **visually blank, but a character**), `\uFEFF` (BOM) | After entity replacements, run a single regex pass: `ZERO_WIDTH_RE = re.compile(r'[\u2000-\u200f\u2028-\u202f\u034f\u2800\ufeff]'); text = ZERO_WIDTH_RE.sub('', text)`. **Common mistake:** using `\u200b-\u200f` only — that misses U+2007 (Figure Space) and U+2000–U+200A. |
| `\r\n` (CRLF) in body | Broken mid-line text, stray `\r` | Normalize: `text.replace('\r\n', '\n').replace('\r', '\n')` |
| Numeric prefix artifact | Mysterious number (e.g. `96`) at start of body | Check `msg.obj.get_payload(decode=True)` — it may prepend charset metadata; strip leading digits+newline |
| `&nbsp;` as separator | Words glued together | Already handled by most cleaners, but verify |
| `&zwnj;`, `&zwsp;`, `&#8202;`, `&#8203;`, `&#8204;`, `&#8205;` (zero-width) | Invisible chars, output looks fine — but they clutter downstream analysis | `text.replace('&zwnj;', '').replace('&zwsp;', '')` + `re.sub(r'&#820[2-5];', '', text)` |
| 3+ identical consecutive lines | Bloated output, repeated headers/footers | Deduplicate: skip if line == last two entries in deduped list. **Critical:** if the upstream is Unicode-cleaned, compare on the *visible* (post-zero-width-strip) form, not the raw string — otherwise `"X"` and `"X\u2800"` won't be detected as duplicates and 200-char garbage lines will slip through. |
| Blank lines between paragraphs | Text looks like wall of words (all blank lines stripped) | Preserve exactly one blank line between non-empty paragraph groups |
| Truncation without indicator | URL is silently broken at cut point (e.g. `https://icca.`) | After truncation, append `\n... [truncated]` |
| RTL language mojibake | `????????` for Hebrew/Arabic | Fallback decode: `windows-1255`, `iso-8859-8`, `cp1255` |

## Verification checklist

After every change to HTML stripping logic:

- [ ] Run on a real mailbox (not synthetic HTML) — at least 10 emails
- [ ] Check: no `&zwnj;` / `&zwj;` / `&nbsp;` in output
- [ ] Check: no **raw** Unicode zero-width chars in output (U+200B, U+200C, U+200D, U+2007, U+2000–U+200A, U+034F, U+2800, U+FEFF) — these bypass entity handling. Quick probe: `python -c "import sys; t=open(sys.argv[1],encoding='utf-8').read(); print([hex(ord(c)) for c in t if 0x2000<=ord(c)<=0x200f or 0x2800==ord(c) or 0x034f==ord(c) or 0xfeff==ord(c)])" output.txt`
- [ ] Check: no 200+ char lines made entirely of "blank-looking" chars (Braille Pattern Blank, etc.) — sign that dedup compared on raw, not visible, content
- [ ] Check: no `\r` in output
- [ ] Check: no numeric prefix on bodies
- [ ] Check: Hebrew text is readable (not `????`)
- [ ] Check: English text is intact
- [ ] Check: no '?' * 10 (Hebrew mojibake) in body
- [ ] Check: no 3+ identical consecutive lines in output
- [ ] Check: blank lines between paragraphs are preserved (one, not zero)
- [ ] Check: truncated body ends with `... [truncated]`
- [ ] Check: HTML-only emails (promo, transactional) produce clean text, not tag soup

## Related

- `references/html-stripping-bugs.md` — concrete bugs found in POST-MAIL-AUTOMATION `strip_html()`
- `references/strip-html-pipeline-v2.md` — full pipeline order, blank-line logic, dedup, truncation indicator, newsletter filter, IMAP date filtering
- `references/unicode-zero-width-raw.md` — TASK-012 finding: raw (non-entity) zero-width/control chars that survive `&zwnj;`/`&#8202-5;` handling, with regex and test corpus
