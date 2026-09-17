---
name: whatsapp-yt-links
description: "Extract YouTube links from WhatsApp to Word table."
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [WhatsApp, YouTube, DOCX, Links]
    related_skills: [screenshot-to-docx, docx]
---

# WhatsApp → YouTube Links Table

Extract all YouTube links from an exported WhatsApp chat `.txt` file, fetch video titles via YouTube oEmbed API, produce a formatted Word table with: number, date, channel, video title, checkbox.

## When to Use

User provides a `.txt` WhatsApp chat export and asks to extract YouTube links with descriptions.

## Workflow

### Step 1: Read the chat export

WhatsApp export format: `DD.MM.YYYY, HH:MM - Sender Name: message`

```python
with open(chat_path, "r", encoding="utf-8") as f:
    chat_text = f.read()
```

### Step 2: Parse YouTube URLs with date filter

```python
import re

date_header = re.compile(r'^(\d{2}\.\d{2}\.\d{4}), (\d{2}:\d{2}) - (.*?): (.*)$')
yt_entries = []

for line in chat_text.split('\n'):
    m = date_header.match(line)
    if not m: continue
    date_str, message = m.group(1), m.group(4)
    day, month, year = map(int, date_str.split('.'))
    # Apply user's date filter
    if not (year == Y and month == M and D1 <= day <= D2): continue
    for url in re.findall(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)[^\s\n]*)', message):
        yt_entries.append({'date': date_str, 'url': url.rstrip('.,;:!?)\]}"\'')})
```

### Step 3: Deduplicate by video ID

```python
def get_vid(url):
    m = re.search(r'(?:shorts/|youtu\.be/|watch\?v=)([a-zA-Z0-9_-]{8,15})', url)
    if m: return m.group(1)
    m = re.search(r'youtube\.com/(@[\w.-]+)', url)
    if m: return m.group(1)
    return url[-30:]

seen = set(); unique = []
for e in yt_entries:
    vid = get_vid(e['url'])
    if vid not in seen: seen.add(vid); unique.append(e)
```

### Step 4: Fetch video titles via YouTube oEmbed API

No API key required. Rate limit: 0.15s between requests.

```python
import urllib.request, json, ssl, time

ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

for e in unique:
    oembed = f"https://www.youtube.com/oembed?url={urllib.request.quote(e['url'], safe='')}&format=json"
    try:
        req = urllib.request.Request(oembed, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read())
        e['title'] = data.get('title', '???')
        e['author'] = data.get('author_name', '')
        e['ok'] = True
    except Exception as ex:
        e['title'] = f'HTTP {ex.code}' if hasattr(ex, 'code') else 'ERR'
        e['author'] = ''; e['ok'] = False
    time.sleep(0.15)
```

### Step 5: Create Word document

```python
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()
# Landscape A4 for wide table
section = doc.sections[0]
section.page_width = Cm(29.7); section.page_height = Cm(21.0)
section.top_margin = Cm(1.0); section.bottom_margin = Cm(1.0)

style = doc.styles['Normal']
style.font.name = 'Times New Roman'; style.font.size = Pt(9)

# Title
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("YouTube-ссылки из WhatsApp"); r.font.size = Pt(14)
r.bold = True; r.font.color.rgb = RGBColor(0,51,102); r.font.name = 'Times New Roman'
p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r2 = p2.add_run(f"Распознано N из M ссылок"); r2.font.size = Pt(9)
r2.font.color.rgb = RGBColor(128,128,128); r2.italic = True
doc.add_paragraph()

# Table header
table = doc.add_table(rows=1, cols=5); table.style = 'Table Grid'
for i, hdr in enumerate(['№', 'Дата', 'Канал', 'О чём видео', '☐']):
    cell = table.rows[0].cells[i]; pp = cell.paragraphs[0]; pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = pp.add_run(hdr); rr.font.size = Pt(9); rr.bold = True; rr.font.name = 'Times New Roman'
    rr.font.color.rgb = RGBColor(255,255,255)
    sh = OxmlElement('w:shd'); sh.set(qn('w:fill'), '003366'); sh.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(sh)

# Data rows
for idx, r in enumerate(ok_results, 1):
    row = table.add_row()
    for ci, (txt, w, font, sz, col) in enumerate([
        (str(idx), Cm(0.6), 'Consolas', 8, None),
        (r['date'], Cm(1.8), 'Times New Roman', 9, None),
        (r['author'], Cm(4.0), 'Times New Roman', 8, None),
        (r['title'], Cm(14.0), 'Times New Roman', 8, None),
        ('☐', Cm(1.0), 'Segoe UI Symbol', 12, None),
    ]):
        cell = row.cells[ci]; cell.width = w; pp = cell.paragraphs[0]
        if ci in (0, 4): pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = pp.add_run(txt); rr.font.name = font; rr.font.size = Pt(sz)
        if col: rr.font.color.rgb = col

doc.save(output_path)
```

## Pitfalls

1. **Date filter always required** — confirm range with user before running.
2. **Channel URLs** (`youtube.com/@channel`) — oEmbed returns 404 for channels. List separately.
3. **Non-breaking spaces** — WhatsApp uses `\u00a0` (not ` `) in filenames on some platforms. Use exact path from `search_files` if `FileNotFoundError`.
4. **oEmbed rate** — YouTube has no strict limit, but `time.sleep(0.15)` between requests is safe.
5. **Export quality** — Direct `.txt` export gives 100% accurate URLs. OCR'd screenshots are unreliable — use this skill only with native chat export.

## Quick Command

```
Parse WhatsApp chat → extract YouTube URLs for DD.MM-DD.MM.YYYY → fetch titles via oEmbed → Word table with date/channel/title/checkbox.
```