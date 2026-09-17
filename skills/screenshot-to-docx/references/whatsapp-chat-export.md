# WhatsApp Chat Export — Preferred Source for Link Extraction

When the source screenshot is from WhatsApp, **exporting the chat as .txt is superior to OCR** in every dimension:

| | OCR скриншота | Экспорт чата WhatsApp |
|---|---|---|
| Точность URL | 35-50% (Tesseract искажает латиницу) | 100% (чистый текст) |
| Контекст | Обрывки OCR-строк | Полное сообщение, дата, отправитель |
| Скорость | 5-10 минут (разрезка + OCR + правка) | 30 секунд (экспорт) + 1 минута (парсинг) |
| Повторяемость | Каждый раз разная точность | Детерминированный результат |

## How to export

1. Open WhatsApp (desktop or web)
2. Open the target chat
3. ⋮ → **Ещё** → **Экспорт чата**
4. Select **«Без медиа»**
5. Save the `.txt` file

## Parsing the export

WhatsApp export format:
```
01.08.2026, 15:56 - Sender Name: message text
01.08.2026, 15:57 - Sender Name: https://youtube.com/shorts/abc123
```

Parse with regex:
```python
import re
pattern = r'(\d{2}\.\d{2}\.\d{4}), (\d{2}:\d{2}) - ([^:]+): (.+)'
```

Extract YouTube URLs:
```python
yt_pat = r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)[^\s]*)'
```

## WhatsApp Web alternative (browser_console)

If export is not possible, inject JavaScript into WhatsApp Web:

```js
// Get ALL YouTube links visible on the page
[...document.querySelectorAll('a[href*="youtube.com"], a[href*="youtu.be"]')]
  .map(a => a.href)
```

This requires:
- User opens web.whatsapp.com in their browser
- Scroll through the date range to load messages
- Hermes uses `browser_console` tool (NOT computer_use — browser tools connect to a headless Chromium)

Limitation: WhatsApp Web lazy-loads messages. Multiple scroll passes needed for long date ranges.

## Decision tree

```
Source is WhatsApp screenshot?
├─ YES → Can user export chat as .txt?
│   ├─ YES → Export → parse .txt → 100% accuracy ✅
│   └─ NO  → Can user open WhatsApp Web?
│       ├─ YES → browser_console → JS injection → good accuracy
│       └─ NO  → Fall back to OCR (inaccurate URLs, expect manual fixes)
└─ NO  → Use screenshot-to-docx OCR workflow
```