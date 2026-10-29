---
name: mail-translate
description: Use when the user wants to translate an email to Russian. Translates both subject and body via OpenRouter LLM. Supports English and Hebrew source languages.
version: 1.1.0
author: POST-MAIL-AUTOMATION project
platforms: [windows]
metadata:
  hermes:
    tags: [mail, translation, russian, llm]
    category: mail
---

# Mail Translate

Translate a Gmail message to Russian (from English or Hebrew).

## Project location

- **PC1:** `G:\_My_Programming\POST-MAIL-AUTOMATION`
- **PC2:** `G:\AI\_MY_PROGRAMMING\POST-MAIL-AUTOMATION`

All commands run from the project root.

## When to Use

- User asks to translate an email, or says "translate this message".
- User provides a UID from the inbox list.

## Procedure

1. `cd` to the project root (see paths above).
2. Get the UID from `python -m app` output.
3. Run:

```
python -m app translate <UID>
```

Example:

```
python -m app translate 20822
```

With a specific account:

```
python -m app --account sverdlovy@gmail.com translate 20822
```

## Pitfalls

- UID must be a valid number from the inbox list. Run `python -m app` first to get UIDs.
- OpenRouter API key must be set in `app/.env`.
- Translation works for English and Hebrew. Body is truncated at 8000 chars (warning printed if exceeded).

## Verification

- Output shows original subject and translation.
- Body is printed with original preview and full translation.
