---
name: image-ocr-to-docx
description: "Use when the user provides a long image (screenshot/scan/scrolling screenshot) with Russian text and wants OCR extraction + Word .docx with semantic section headings. Triggers: распознай текст/OCR/сделай Word/слово в слово/extract text from image."
version: 1.0.0
author: Hermes Agent (Yuri)
license: MIT
metadata:
  hermes:
    tags: [ocr, russian, docx, image, pytesseract]
    related_skills: [ocr-and-documents]
---

# Image OCR → Word DOCX Pipeline

## Overview

Full pipeline to extract text from a **tall/long image** (screenshot, scrolling screenshot, scanned doc — JPG/PNG) using Tesseract with Russian support, then package it into a nicely formatted `.docx` file with semantic headings.

## When to Use

- User provides an image file path and says "распознай текст", "сделай Word", "извлеки текст", "extract text from image"
- Image is too long for a single Tesseract pass without splitting (over ~1000px height)
- User wants a .docx with structured sections, not just raw text
- **Don't use for:** PDFs (use `ocr-and-documents` skill with pymupdf/marker-pdf), short screenshots readable in one pass, purely English text with no formatting needs

## Prerequisites

```bash
# Tesseract engine (Windows)
winget install --id UB-Mannheim.TesseractOCR --exact

# Russian language data
# Download to MSYS /tmp, then copy to tessdata dir:
curl -L -o /tmp/rus.traineddata "https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata"
# If Permission denied copying to Program Files, use:
cp /tmp/rus.traineddata ~/tessdata/rus.traineddata  # user-writable dir

# Python packages
pip install pytesseract pillow python-docx
```

## Step 1: Inspect the Image

```python
from PIL import Image
img = Image.open(path)
w, h = img.size
print(f'Size: {w}x{h}, Mode: {img.mode}, Format: {img.format}')
```

For images over ~1200px height: split into N parts. Rule of thumb:
- ~8000px → 6 parts
- ~5000px → 4 parts
- ~2000-3000px → 3 parts
- Each part ≈ 1400-1500px height works well with Tesseract PSM 6

## Step 2: Set Up Tesseract

```python
import pytesseract, os
os.environ['TESSDATA_PREFIX'] = os.path.expanduser(r'~\tessdata')
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## Step 3: OCR — Split Image and Process

```python
n_parts = 6
part_h = h // n_parts

all_text = []
for i in range(n_parts):
    y0 = i * part_h
    y1 = (i + 1) * part_h if i < n_parts - 1 else h
    crop = img.crop((0, y0, w, y1))
    text = pytesseract.image_to_string(crop, lang='rus', config='--psm 6 --oem 3')
    all_text.append(text.strip())
```

**PSM modes to try:**
| Mode | When |
|------|------|
| `--psm 6` | Single uniform block of text — best for articles, essays |
| `--psm 3` | Fully automatic — mixed content |
| `--psm 4` | Single column — dialogs, error panels |
| `--psm 11` | Sparse text with no particular order — UI elements |

## Step 4: Find Semantic Sections

After raw OCR, **read the full text** and identify 4–7 natural thematic blocks. Common patterns for long-form articles:

1. Introduction / thesis / opening quote
2. Historical background / founding story
3. Core methods / practices / dark side
4. Specific examples (e.g., in Russia / country X)
5. Conclusion / modern relevance / closing thought

Mark section boundaries where the topic shifts clearly.

## Step 5: Build DOCX

Create a .docx with:
- **Title** (centered, large)
- **Subtitle / source** (italic, smaller)
- **Section headings** (Heading 1 style, e.g. dark red)
- **Body paragraphs** (Calibri 11pt, 1.35 line spacing)
- **Footer** with source attribution and date

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# Page margins
for section in doc.sections:
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

# Style: Title
style = doc.styles['Title']
style.font.size = Pt(22)
style.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)
style.font.bold = True

# Style: Heading 1
h1 = doc.styles['Heading 1']
h1.font.size = Pt(16)
h1.font.color.rgb = RGBColor(0x8b, 0x00, 0x00)
h1.font.bold = True
h1.paragraph_format.space_before = Pt(24)

# Style: Normal
norm = doc.styles['Normal']
norm.font.size = Pt(11)
norm.font.name = 'Calibri'
norm.paragraph_format.line_spacing = 1.35

# Add title, headings, paragraphs...
doc.save(out_path)
```

## Step 6: Clean OCR Artefacts

Before putting text into the DOCX, remove:
- Garbage rows that are clearly decorative elements (e.g. `алаг р ому чодечиссй с ож о еа тч ВЬ`)
- Standalone punctuation/symbols from decorative page breaks
- Repeated single characters from ornaments
- **Keep** the actual text word-for-word — only cut obvious non-text debris

## Common Pitfalls

1. **Tesseract not in PATH** — set `tesseract_cmd` explicitly to `C:\Program Files\Tesseract-OCR\tesseract.exe`
2. **Permission denied writing to Program Files** — put traineddata in `~/tessdata/` instead, set `TESSDATA_PREFIX` env var
3. **Wrong Python** — `pip install` may go to Python 3.10 but `python3` is 3.14. Check with `python --version` vs `python3 --version`. Use the one that has pytesseract installed
4. **Very long images (>10000px)** — increase `n_parts` or user may need to crop manually; quality degrades on small text
5. **DOCX installs under `python` not `python3`** — check `pip show python-docx` to confirm which env has it; run the script with the right interpreter
6. **Page break garbage dominates a part** — if a decorative page break lands exactly on a crop boundary and produces mostly garbage, increase n_parts to split finer, or join adjacent clean parts and discard the garbage row

## Verification Checklist

- [ ] Image dimensions checked — split count chosen proportionally
- [ ] Tesseract rus language data confirmed: `tesseract --list-langs | grep rus`
- [ ] All parts OCR'd — no skipped sections
- [ ] Garbage rows from decorative elements removed from final text
- [ ] Semantic sections identified (4-7 blocks) with descriptive headings
- [ ] DOCX created and saved to Desktop or user-specified path
- [ ] File size > 0 and opens correctly