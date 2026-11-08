# Provider billing endpoints — tested snippets

Tested 2026-06. Re-probe before relying; provider APIs drift.

## OpenRouter — HAS balance API ✅

```bash
curl -s https://openrouter.ai/api/v1/credits \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
# -> {"data":{"total_credits":47,"total_usage":37.535...}}
# remaining = total_credits - total_usage  (≈ 9.46)
```

Per-key usage detail (daily/weekly/monthly):
```bash
curl -s https://openrouter.ai/api/v1/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
# -> {"data":{"label":"sk-or-v1-...","usage":..,"usage_daily":..,
#             "usage_weekly":..,"usage_monthly":..,"limit":null,...}}
```

## Anthropic — NO balance API ❌ (only spend, only with Admin key)

A normal `x-api-key` is rejected on org endpoints:
```bash
curl -s https://api.anthropic.com/v1/organizations/cost_report \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01"
# -> 401 {"error":{"type":"authentication_error","message":"invalid x-api-key"}}
```

With an **Admin key** (`sk-ant-admin...`, Console → Settings → Admin Keys,
organization owner only) you get SPEND, not balance:
```bash
curl -s "https://api.anthropic.com/v1/organizations/cost_report?starting_at=2025-01-01T00:00:00Z" \
  -H "x-api-key: $ANTHROPIC_ADMIN_KEY" -H "anthropic-version: 2023-06-01"
# -> buckets with results[].amount  (sum = total spend)
```

There is **no** endpoint that returns prepaid credit remaining. Compute:
`remaining = sum(manual top-ups) − spend_from_cost_report`.

### cost_report gotchas (cost me real debugging time, 2026-06)

- **Paginated.** Response is `{data:[...buckets], has_more, next_page}`. Reading
  only page 1 gives a wrong total (often $0 if the window starts in an empty
  period). Loop until `has_more` is false, passing `&page=<next_page>`.
- **Use monthly buckets** to cut page count: `&bucket_width=1month` (default
  daily → ~78 pages/yr; monthly → ~12).
- **`results[].amount` is a STRING** (`"3.353475"`), `currency:"USD"`. Cast to
  float. Empty periods have `results: []`.
- **Severe rate limit (429).** Several quick calls exhausted it; even 2-minute
  waits still 429'd (felt ~hourly reset). In production: cache the total with a
  ~5-min TTL, back off on 429 (5/10/15/20s then give up → degrade to
  remaining=top-ups). While developing, probe ONCE — don't loop to "confirm".

Paginated + cached + backoff loop (the shape that works):
```python
base = (".../cost_report?starting_at=2025-01-01T00:00:00Z&bucket_width=1month")
url, total, last = base, 0.0, None
while url:
    status, data = http_get(url, headers)      # retry 429 w/ backoff inside
    last = status
    if status != 200: break
    for b in data.get("data", []):
        for it in b.get("results", []):
            total += float(it.get("amount") or 0)
    url = base + "&page=" + data["next_page"] if data.get("has_more") else None
```

## Pricing probe (model price-quality, same project family)

OpenRouter is also the go-to for live per-model pricing + tool-use support:
```bash
curl -s https://openrouter.ai/api/v1/models | python -c "
import sys,json
d=json.load(sys.stdin); m={x['id']:x for x in d['data']}
x=m['deepseek/deepseek-chat']; p=x['pricing']
print('in/1M', float(p['prompt'])*1e6, 'out/1M', float(p['completion'])*1e6)
sp=x.get('supported_parameters',[]); print('tool use:', 'tools' in sp and 'tool_choice' in sp)
"
```

## Finding the real key name (don't guess)

Hermes stores the source env-var name in `auth.json`:
```bash
cd ~/AppData/Local/hermes && python -c "
import json; d=json.load(open('auth.json',encoding='utf-8'))
for prov in ['openrouter','anthropic']:
  for c in d.get('credential_pool',{}).get(prov,[]):
    print(prov, c.get('source'), c.get('auth_type'), c.get('last_status'))
"
# -> openrouter env:OPENROUTER_API_KEY api_key ok
```
Keys also live in `~/AppData/Local/hermes/.env` (read lines, skip `#`/blank).
