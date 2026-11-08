# HTML stripping bugs — POST-MAIL-AUTOMATION

Concrete bugs found in `app/imap_client.py:strip_html()` during a real 10-email export test (2026-07-23).

## Bug 1: `&zwnj;` entity not decoded

**Symptom:** Output littered with `&zwnj; &zwnj; &zwnj;` (zero-width non-joiner). Dozens per email body.

**Root cause:** `strip_html()` handles `&nbsp;`, `&amp;`, `&lt;`, `&gt;` but not `&zwnj;` or `&zwj;`.

**Example from output:**
```
&zwnj; &zwnj; &zwnj; &zwnj; &zwnj; &zwnj; &zwnj; &zwnj; &zwnj; &zwnj;
```

**Fix:** Add `&zwnj;` and `&zwj;` to the entity replacement chain:
```python
text = text.replace('&zwnj;', '').replace('&zwj;', '')
```

## Bug 2: `\r\n` (CRLF) not normalized

**Symptom:** Body text has stray `\r` at line breaks, e.g.:
```
Как эмоции возвращаются через\r\nдвижение, дыхание, границу и контакт
```

**Root cause:** `strip_html()` normalizes `\n{3,}` but doesn't handle `\r\n` or standalone `\r`. Email bodies often contain CRLF line endings.

**Fix:** Normalize before other processing:
```python
text = text.replace('\r\n', '\n').replace('\r', '\n')
```

## Bug 3: Mysterious `96` prefix

**Symptom:** Multiple email bodies start with `96` on its own line:
```
96
Внимание: это может увлечь
```

Seen in: AliExpress promo (UID 84280), Alpina book (UID 84279), Robinhood Snacks (UID 84277), another AliExpress (UID 84278).

**Root cause (hypothesis):** `msg.obj.get_payload(decode=True)` may return charset metadata or part-length prefix that `_decode_body()` doesn't strip. Needs investigation — could be `imap_tools` quirk or MIME part header leakage.

**Fix:** Investigate `msg.obj` structure. If it's a consistent prefix, strip leading digits before HTML processing:
```python
body = re.sub(r'^\d+\n', '', body)
```

## Test corpus

Export command used: `python -m app export --account sverdlovy@gmail.com --days 30 --limit 10`

Emails in test: ICCA Academy (2), AliExpress promo (2), Alpina Publisher (1), Robinhood Snacks (1) + others.
