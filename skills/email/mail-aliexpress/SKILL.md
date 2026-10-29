---
name: mail-aliexpress
description: Use when the user wants to track AliExpress orders. Parses transactional emails, filters out promotions, outputs chronological txt report and Excel table.
version: 1.1.0
author: POST-MAIL-AUTOMATION project
platforms: [windows]
metadata:
  hermes:
    tags: [mail, aliexpress, orders, tracking, excel]
    category: mail
---

# Mail AliExpress Tracker

Track AliExpress orders from Gmail.

## Project location

- **PC1:** `G:\_My_Programming\POST-MAIL-AUTOMATION`
- **PC2:** `G:\AI\_MY_PROGRAMMING\POST-MAIL-AUTOMATION`

All commands run from the project root.

## When to Use

- User asks about AliExpress orders, tracking, delivery status.
- User says "show my AliExpress orders" or "check where my packages are".

## Procedure

1. `cd` to the project root (see paths above).
2. Run:

```
python -m app aliexpress [options]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--days N` | 365 | Last N days |
| `--limit N` | 200 | Max emails to scan |
| `--account EMAIL` | from .env | Gmail account that receives AliExpress emails |

## Examples

```bash
# Default: last 365 days, max 200
python -m app aliexpress

# Last 90 days, max 100, specific account
python -m app aliexpress --account <your-email> --days 90 --limit 100
```

## Output Files

- `aliexpress_orders.txt` — chronological text report.
- `aliexpress_orders.xlsx` — Excel table with columns: Date, Order ID, Tracking ID, Status, Subject.

## Pitfalls

- Only transactional emails from `transaction@notice.aliexpress.com` are included.
- Promotional emails (promo, discounts, recommendations) are automatically filtered out.
- Requires `openpyxl` installed (`pip install openpyxl`).
- The account must be the one that receives AliExpress order emails.

## Verification

- Both output files are created in the project root.
- Summary line shows number of transactional vs promotional emails.
- Excel file opens with correct column headers.
