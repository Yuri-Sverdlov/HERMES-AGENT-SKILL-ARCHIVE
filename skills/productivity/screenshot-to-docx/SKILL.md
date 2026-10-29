---
name: screenshot-to-docx
description: "OCR Russian screenshots to Word: full-text blocks or table extracts."
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [OCR, DOCX, Screenshot, Russian, Text-Recognition, Productivity]
    related_skills: [docx, ocr-and-documents]
---

# Screenshot → Word Document (Russian OCR)

Convert a long vertical screenshot containing Russian text into a structured Word document.

## Prerequisites

- Tesseract OCR: `C:\Program Files\Tesseract-OCR\tesseract.exe` (v5.4.0+)
- Russian language data: `C:\Program Files\Tesseract-OCR\tessdata\rus.traineddata`
- Python packages: `pytesseract`, `pillow`, `python-docx`
- Add to PATH: `export PATH="$PATH:/c/Program Files/Tesseract-OCR"`

## Workflow

### Step 1: Check image dimensions

```python
from PIL import Image
img = Image.open("path/to/screenshot.jpg")
print(f"Size: {img.size}")  # (width, height)
```

### Step 2: Split into parts (if height > 1200 px)

Tesseract struggles with very long images. Split vertically into parts of ~1200 px each:

```python
width, height = img.size
parts = max(3, height // 1100 + 1)  # at least 3 parts
part_height = height // parts
for i in range(parts):
    top = i * part_height
    bottom = (i + 1) * part_height if i < parts - 1 else height
    crop = img.crop((0, top, width, bottom))
    crop.save(f"part_{i+1}.jpg", quality=95)
```

### Step 3: OCR each part

```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
text = pytesseract.image_to_string("part_1.jpg", lang="rus")
print(text)
```

If tesseract is not in PATH, use the full path as above.

### Step 4: Identify semantic blocks

Read the combined OCR text and identify 4–5 logical sections:
- Block 1: Introduction / thesis
- Block 2: First argument / detail
- Block 3: Second argument / counterpoint
- Block 4: Resolution / conclusion
- Block 5 (optional): Metrics / metadata

### Step 5: Create Word document

```python
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# A4 portrait (книжная)
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.0)
section.bottom_margin = Cm(2.0)
section.left_margin = Cm(2.5)
section.right_margin = Cm(2.0)

# Normal style: Times New Roman 12pt
style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(12)
style.paragraph_format.space_after = Pt(6)
style.paragraph_format.line_spacing = 1.15
```

**Heading helper:**
```python
def add_heading(text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = 'Times New Roman'
        run.font.color.rgb = RGBColor(0, 51, 102)
```

**Body text helper (with first-line indent):**
```python
def add_body(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.first_line_indent = Cm(1.25)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
```

### Step 6: Title page (optional, for substantive texts)

For post/article compilations, add a title page with:
- Source name (e.g. "БИБЛИОТЕКА АКАШИ")
- Subtitle / series name
- Article title
- Date

```python
add_para("SOURCE NAME", bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0,51,102))
add_para("Article Title", bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER)
add_para("Распознанный текст скриншота  •  Месяц Год", italic=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(128,128,128))
doc.add_page_break()
```

### Step 7: Add metrics page (last)

Extract reactions (❤️🔥👍👎), view counts (👁), and timestamp from OCR output. Place on a separate page:

```python
doc.add_page_break()
add_heading("Метрики публикаций", level=2)
add_para("Пост 1:", bold=True, size=12)
add_para("❤ 29  •  🔥 22  •  👁 1479  •  15:56", size=11, color=RGBColor(128,128,128))
```

### Step 8: Save and deliver

```python
doc.save("output.docx")
print(f"Saved: output.docx ({os.path.getsize('output.docx')} bytes)")
```

Deliver with `MEDIA:/absolute/path/to/output.docx`.

## Cleanup

Remove temporary split images and the generator script after delivery:
```bash
rm -f part_*.jpg create_*.py
```

## Variant: Extract Specific Content into a Table

When the user wants to extract only certain items (links, dates, names) rather than full text:

### Table extraction workflow

**Identify targets** — define regex patterns for the content type:
- YouTube links: garbled OCR patterns like `уоши[а-яё]+\.сот`, `уо[а-яё]+\.Бе`, `[ммп]...уо[шщ]...\.сот`
- Dates: `\d{2}[.]\d{2}[.]\d{4}`
- Phone numbers, email patterns, etc.

**Extract + deduplicate** — scan all OCR lines, match patterns, deduplicate by signature:

```python
seen = set()
entries = []
for i, line in enumerate(lines):
    if not has_target_pattern(line):
        continue
    sig = re.sub(r'[^a-z0-9]', '', line.lower())[:40]
    if sig in seen:
        continue
    seen.add(sig)
    # Gather context from nearby lines
    ...
```

**Context gathering** — for each match, search upward for a non-URL, non-noise line (title/description):

```python
for j in range(i-1, max(i-7, -1), -1):
    prev = lines[j].strip()
    if prev and len(prev) > 5 and not is_url_like(prev) and '===' not in prev:
        context = prev[:130]
        break
```

**Table document** — use landscape A4 for wide tables (4+ columns):

```python
section.page_width = Cm(29.7)
section.page_height = Cm(21.0)
```

Table construction with styled header row:

```python
table = doc.add_table(rows=1, cols=4)
table.style = 'Table Grid'
# Header with dark background — use OxmlElement for shading:
shading = OxmlElement('w:shd')
shading.set(qn('w:fill'), '003366')
shading.set(qn('w:val'), 'clear')
cell._tc.get_or_add_tcPr().append(shading)
```

**Column structure** — typical layout for link extraction:
- Col 1: № (0.7 cm, centered, Consolas 8pt)
- Col 2: URL/link (8 cm, Consolas 7pt, blue)
- Col 3: Title/description (14 cm, Times New Roman 8pt)
- Col 4: ☐ checkbox (1.5 cm, centered)

**Deliver with explicit warning** — OCR-distorted URLs are NOT usable directly. The table is an INDEX for manual lookup from the original source. State this clearly when delivering.

### YouTube link extraction with video descriptions

When the user wants not just URLs but actual video titles/descriptions:

**Phase A — Improve URL accuracy with dual-pass OCR.** The core discovery: Tesseract `rus` distorts Latin characters in URLs; `eng` preserves them but loses Russian context. Use BOTH:

```python
# Run OCR twice per part — eng for URLs, rus for context
text_eng = pytesseract.image_to_string(path, lang="eng")
text_rus = pytesseract.image_to_string(path, lang="rus")
```

For even better URL accuracy, preprocess images:
```python
from PIL import Image, ImageFilter, ImageEnhance
img = Image.open(path).convert('L')          # grayscale
img = ImageEnhance.Contrast(img).enhance(2.0) # boost contrast
img = img.filter(ImageFilter.SHARPEN)         # sharpen edges
img = img.resize((w*2, h*2), Image.LANCZOS)   # 2x upscale
```

Then use Tesseract CLI with `--psm 6` (uniform block mode):
```bash
tesseract part.png stdout -l eng --psm 6
```

**Phase B — Extract + deduplicate URLs from English OCR:**
```python
import re
yt_pat = r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)[^\s\n]*'
urls = re.findall(yt_pat, text_eng, re.IGNORECASE)
```

Deduplicate by video ID:
```python
def extract_vid(url):
    m = re.search(r'(?:shorts?/|youtu\.be/|v=)([a-zA-Z0-9_-]{8,15})', url)
    return m.group(1) if m else url[-30:]
```

**Phase C — Merge with Russian context.** For each URL, find the nearest non-URL text line in the RUS OCR output to serve as the human-readable title/description.

**Phase D — Fetch real video titles via YouTube oEmbed API** (no JS, no API key):
```python
import urllib.request, json, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

oembed = f"https://www.youtube.com/oembed?url={urllib.request.quote(url)}&format=json"
req = urllib.request.Request(oembed, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
    data = json.loads(resp.read())
title = data['title']          # video title
author = data['author_name']   # channel name
```

Rate-limit: `time.sleep(0.2)` between requests. Expect ~35-50% success rate — many URLs will have OCR-corrupted video IDs. See `references/youtube-oembed-api.md` for full API details.

**Phase E — Build the Word table.** 5 columns: №, URL, Channel, Title, ☐. Landscape A4. Header with dark blue background via OxmlElement shading. Deliver with clear note that URLs are best-effort OCR reconstructions and may need manual correction from the original screenshot.

## Pitfalls

1. **Tesseract PATH**: After install, tesseract is NOT in bash PATH. Export: `export PATH="$PATH:/c/Program Files/Tesseract-OCR"` or use full `pytesseract_cmd` path.
2. **Russian text artifacts**: Stylized fonts (bold/italic headers) produce garbled output like "ОРО5 МАСМУМ" for "OPUS MAGNUM". Manual correction may be needed.
3. **Very long images (>5000px)**: Split into 4–5 parts minimum. Tesseract loses context on extreme aspect ratios.
4. **PermissionError on save**: If the target .docx is open in WPS Office/Word, save to a different filename (e.g. append " (OCR)").
5. **Social media screenshots**: Reactions/buttons in the sidebar produce OCR noise. Place metrics in a separate appendix page rather than inline.
6. **URL distortion by OCR**: Tesseract heavily garbles URLs — `youtube.com/shorts` becomes `уошибе.сот/зпопз`, `youtu.be` becomes `уоши.Бе`. OCR'd URLs are NEVER usable directly. **Fix**: use dual-pass OCR (`eng` for URLs + `rus` for context) with preprocessing (contrast 2x, sharpen, 2x upscale, `--psm 6`). Even with this, expect ~35-50% of video IDs to be correct — the rest must be manually verified against the original screenshot. For maximum accuracy on critical URLs, use browser_vision on individual image fragments — it reads mixed Latin/Cyrillic far better than Tesseract. See `references/browser-console-url-extraction.md` for the full workflow and comparison.
7. **Book orientation**: Use A4 portrait (книжная), NOT landscape, for text documents. Landscape (Cm 29.7 × 21.0) is acceptable only for wide tables with 4+ columns.

## Verification

- [ ] Tesseract recognizes Russian text (`tesseract --list-langs` shows `rus`)
- [ ] Image split into correct number of parts
- [ ] All parts OCR'd successfully
- [ ] 4–5 semantic blocks identified
- [ ] Document: A4 portrait, Times New Roman 12pt, first-line indent
- [ ] Title page present for multi-post/serious content
- [ ] Metrics page at end
- [ ] Delivered via MEDIA: path

## WhatsApp-specific workflow

When the source is a WhatsApp screenshot, **exporting the chat as .txt is strongly preferred** over OCR. See `references/whatsapp-chat-export.md` for the complete decision tree, export instructions, and parsing patterns. In short: .txt export = 100% URL accuracy vs OCR's ~35%.