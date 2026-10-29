---
name: mail-export
description: Use when the user wants to export emails to a text file. Supports filters by date range, sender, and account. Optional auto-translation to Russian. Outputs UID, date, time, from, subject, attachments, and body.
version: 1.2.0
author: POST-MAIL-AUTOMATION project
platforms: [windows]
metadata:
  hermes:
    tags: [mail, export, report, filter, translation]
    category: mail
---

# Mail Export

Export Gmail messages to a text file with metadata and optional translation.

## Project location

- **PC1:** `G:\_My_Programming\POST-MAIL-AUTOMATION`
- **PC2:** `G:\AI\_MY_PROGRAMMING\POST-MAIL-AUTOMATION`

All commands run from the project root.

## When to Use

- User asks to export emails, save emails to file, or dump inbox.
- User provides filters: date range, sender, limit, translation.

## Procedure

1. `cd` to the project root (see paths above).
2. Run:

```
python -m app export [options]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--days N` | 7 | Last N days |
| `--limit N` | 20 | Max emails |
| `--output FILE` | exported_emails.txt | Output filename |
| `--from ADDR` | none | Filter by sender (e.g. `@domain.com`) |
| `--translate` | off | Auto-translate body to Russian |
| `--account EMAIL` | from .env | Switch Gmail account |
| `--from-date YYYY-MM-DD` | none | Start date (inclusive) |
| `--to-date YYYY-MM-DD` | none | End date (inclusive) |
| `--before YYYY-MM-DD` | none | Emails strictly before date |
| `--after YYYY-MM-DD` | none | Emails strictly after date |
| `--skip-newsletters` | off | Filter out newsletter/spam |

**Date filter logic:**
- `--from-date` + `--to-date` = date range. `--limit` applies inside the range.
- `--before` + `--limit 5` = last 5 emails before the date.
- `--after` + `--limit 5` = first 5 emails after the date.
- `--days` and `--from-date`/`--to-date` are mutually exclusive — date range takes priority.

## Common examples

```bash
# Last 7 days, max 20 (defaults)
python -m app export

# Last 30 days, max 50
python -m app export --days 30 --limit 50

# Filter by sender
python -m app export --from "@aliexpress" --days 90

# Different account
python -m app export --account sverdlovy@gmail.com --limit 10

# With auto-translation
python -m app export --days 7 --limit 5 --translate

# Date range: all emails from July
python -m app export --from-date 2026-07-01 --to-date 2026-07-31

# Last 5 emails before a date
python -m app export --before 2026-07-15 --limit 5

# First 10 emails after a date, translated
python -m app export --after 2026-07-20 --limit 10 --translate

# Exclude newsletters
python -m app export --days 7 --skip-newsletters
```

## Pitfalls

- Output file is created in the project root. Use `--output` to change location.
- `--translate` must be explicitly added — it is OFF by default.
- HTML emails are auto-cleaned (tags, zero-width chars, entities removed).
- Body preview is first 2000 characters.
- `--from` filter matches the sender address (e.g., `@domain.com`).

## Verification

- File is created in the project root.
- Each email block contains UID, Date, Time, From, Subject, Attachments, Body.
- If `--translate` is set, both original and translated text appear.
