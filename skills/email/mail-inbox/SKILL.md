---
name: mail-inbox
description: Use when the user asks to show recent emails, check inbox, or list Gmail messages. Shows the 5 most recent emails from the inbox.
version: 1.1.0
author: POST-MAIL-AUTOMATION project
platforms: [windows]
metadata:
  hermes:
    tags: [mail, gmail, inbox, read]
    category: mail
---

# Mail Inbox

Show recent Gmail inbox messages.

## Project location

- **PC1:** `G:\_My_Programming\POST-MAIL-AUTOMATION`
- **PC2:** `G:\AI\_MY_PROGRAMMING\POST-MAIL-AUTOMATION`

All commands run from the project root.

## When to Use

- User asks to see emails, check mail, or list inbox.
- User says "what's in my inbox" or "show recent messages".

## Procedure

1. `cd` to the project root (see paths above).
2. Run:

```
python -m app
```

With a specific account:

```
python -m app --account other@gmail.com
```

See all options:

```
python -m app help
```

## Pitfalls

- OAuth2 token must exist for the account. First run per account opens a browser — confirm access, then retry.
- Network timeout: retry once if IMAP connection fails.
- Default account is set in `app/.env` (`IMAP_USER`). `--account` overrides it.

## Verification

- Output shows 5 emails with UID, date, from, subject.
- Total count is printed at the end.
