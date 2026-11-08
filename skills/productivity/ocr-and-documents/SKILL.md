---
name: ocr-and-documents
description: "Extract text from PDFs/scans (pymupdf, marker-pdf)."
version: 2.5.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, Documents, Research, Arxiv, Text-Extraction, OCR]
    related_skills: [powerpoint]
---

# PDF & Document Extraction

For DOCX: use `python-docx` (parses actual document structure, far better than OCR).
For PPTX: see the `powerpoint` skill (uses `python-pptx` with full slide/notes support).
This skill covers **PDFs and scanned documents**.

## Step 1: Remote URL Available?

If the document has a URL, **always try `web_extract` first**:

```
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])
web_extract(urls=["https://example.com/report.pdf"])
```

This handles PDF-to-markdown conversion via Firecrawl with no local dependencies.

Only use local extraction when: the file is local, web_extract fails, or you need batch processing.

## Step 2: Choose Local Extractor

| Feature | pymupdf (~25MB) | marker-pdf (~3-5GB) |
|---------|-----------------|---------------------|
| **Text-based PDF** | ✅ | ✅ |
| **Scanned PDF (OCR)** | ❌ | ✅ (90+ languages) |
| **Tables** | ✅ (basic) | ✅ (high accuracy) |
| **Equations / LaTeX** | ❌ | ✅ |
| **Code blocks** | ❌ | ✅ |
| **Forms** | ❌ | ✅ |
| **Headers/footers removal** | ❌ | ✅ |
| **Reading order detection** | ❌ | ✅ |
| **Images extraction** | ✅ (embedded) | ✅ (with context) |
| **Images → text (OCR)** | ❌ | ✅ |
| **EPUB** | ✅ | ✅ |
| **Markdown output** | ✅ (via pymupdf4llm) | ✅ (native, higher quality) |
| **Install size** | ~25MB | ~3-5GB (PyTorch + models) |
| **Speed** | Instant | ~1-14s/page (CPU), ~0.2s/page (GPU) |

**Decision**: Use pymupdf unless you need OCR, equations, forms, or complex layout analysis.

If the user needs marker capabilities but the system lacks ~5GB free disk:
> "This document needs OCR/advanced extraction (marker-pdf), which requires ~5GB for PyTorch and models. Your system has [X]GB free. Options: free up space, provide a URL so I can use web_extract, or I can try pymupdf which works for text-based PDFs but not scanned documents or equations."

---

## pymupdf (lightweight)

```bash
pip install pymupdf pymupdf4llm
```

> **Windows / uv pitfall:** `pip install pymupdf` may install into the wrong Python environment, leaving `import fitz` broken for `python3`. If you get `ModuleNotFoundError: No module named 'fitz'` after pip install, use `uv` instead:
> ```bash
> uv pip install pymupdf
> uv run python3 -c "import fitz; print(fitz.__version__)"  # verify
> ```
> Always run the extraction script with `uv run python3 ...` in this case, not bare `python3 ...`.

**Via helper script**:
```bash
python scripts/extract_pymupdf.py document.pdf              # Plain text
python scripts/extract_pymupdf.py document.pdf --markdown    # Markdown
python scripts/extract_pymupdf.py document.pdf --tables      # Tables
python scripts/extract_pymupdf.py document.pdf --images out/ # Extract images
python scripts/extract_pymupdf.py document.pdf --metadata    # Title, author, pages
python scripts/extract_pymupdf.py document.pdf --pages 0-4   # Specific pages
```

**Inline**:
```bash
python3 -c "
import pymupdf
doc = pymupdf.open('document.pdf')
for page in doc:
    print(page.get_text())
"
```

---

## marker-pdf (high-quality OCR)

```bash
# Check disk space first
python scripts/extract_marker.py --check

pip install marker-pdf
```

**Via helper script**:
```bash
python scripts/extract_marker.py document.pdf                # Markdown
python scripts/extract_marker.py document.pdf --json         # JSON with metadata
python scripts/extract_marker.py document.pdf --output_dir out/  # Save images
python scripts/extract_marker.py scanned.pdf                 # Scanned PDF (OCR)
python scripts/extract_marker.py document.pdf --use_llm      # LLM-boosted accuracy
```

**CLI** (installed with marker-pdf):
```bash
marker_single document.pdf --output_dir ./output
marker /path/to/folder --workers 4    # Batch
```

---

## Arxiv Papers

```
# Abstract only (fast)
web_extract(urls=["https://arxiv.org/abs/2402.03300"])

# Full paper
web_extract(urls=["https://arxiv.org/pdf/2402.03300"])

# Search
web_search(query="arxiv GRPO reinforcement learning 2026")
```

## Split, Merge & Search

pymupdf handles these natively — use `execute_code` or inline Python:

```python
# Split: extract pages 1-5 to a new PDF
import pymupdf
doc = pymupdf.open("report.pdf")
new = pymupdf.open()
for i in range(5):
    new.insert_pdf(doc, from_page=i, to_page=i)
new.save("pages_1-5.pdf")
```

```python
# Merge multiple PDFs
import pymupdf
result = pymupdf.open()
for path in ["a.pdf", "b.pdf", "c.pdf"]:
    result.insert_pdf(pymupdf.open(path))
result.save("merged.pdf")
```

```python
# Search for text across all pages
import pymupdf
doc = pymupdf.open("report.pdf")
for i, page in enumerate(doc):
    results = page.search_for("revenue")
    if results:
        print(f"Page {i+1}: {len(results)} match(es)")
        print(page.get_text("text"))
```

No extra dependencies needed — pymupdf covers split, merge, search, and text extraction in one package.

---

## Screenshot / Image OCR (Vision Models)

When the user provides **image files** (JPG, PNG, screenshots) and wants text extracted:

**DO NOT use `delegate_task` with vision toolset for OCR** — subagents inherit a potentially different (cheaper) model. If Haiku is the delegated model, it will **hallucinate text** on small-font screenshots instead of admitting it can't read them. The output looks plausible but is fabricated.

**Correct approach (in order of preference):**

1. **Open the image in browser** — use `browser_navigate` with a `file://` URL and `browser_snapshot(full=True)`. Often readable for UI screenshots with large text.

2. **pytesseract (tesseract-ocr) local OCR** — best for UI screenshots, dialogs, error messages. Full workflow:

   ```bash
   # Install tesseract engine (Windows)
   winget install --id UB-Mannheim.TesseractOCR --exact

   # Install Python wrapper
   pip install pytesseract pillow
   ```

   **Windows MSYS2 pitfall — `python` vs `python3`:** On Git-Bash/MSYS2 (Hermes Windows shell), `python` and `python3` may be different Python versions with different pip environments. Always verify which one has pytesseract installed:
   ```bash
   python  -c "import pytesseract; print('python OK')" 2>&1
   python3 -c "import pytesseract; print('python3 OK')" 2>&1
   ```
   If only one works (e.g. `python` 3.11 has it but `python3` 3.14 does not), use that binary consistently (`python`, not `python3`).

   **Verify binary location** — after install, confirm the engine is present:
   ```bash
   ls /c/Program\ Files/Tesseract-OCR/tesseract.exe 2>/dev/null && echo "FOUND"
   ```

   **Setting tesseract_cmd** — after winget install, the binary may not be in PATH for the current shell. Find it and set explicitly:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

   **Checking available languages** — Tesseract ships with only English (`eng`) and orientation detection (`osd`) by default. Check before attempting OCR in another language:
   ```bash
   "C:/Program Files/Tesseract-OCR/tesseract.exe" --list-langs
   ```

   **Installing missing language data** — if your language (e.g. `rus`) is not listed, download the traineddata file. On Windows, writing to `Program Files` is permission-denied, so use a user-writable fallback:
   ```bash
   # Download to a writable location (Python avoids MSYS curl's path issues)
   python -c "
   import urllib.request
   url = 'https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata'
   dst = r'C:\Users\<user>\tessdata\rus.traineddata'
   import os; os.makedirs(os.path.dirname(dst), exist_ok=True)
   urllib.request.urlretrieve(url, dst)
   print(f'Downloaded to {dst}')
   "
   ```
   Then set `TESSDATA_PREFIX` before calling pytesseract:
   ```python
   import os
   os.environ['TESSDATA_PREFIX'] = r'C:\Users\<user>\tessdata'
   ```
   Language codes: `rus` for Russian, `eng` for English, combine with `+`: `rus+eng`, `eng+rus+ukr`, etc.

   **Image preprocessing** — raw screenshots often OCR poorly. Preprocess for better results:
   ```python
   from PIL import Image, ImageEnhance, ImageFilter

   img = Image.open(path)
   gray = img.convert('L')                          # grayscale
   enhancer = ImageEnhance.Contrast(gray)
   gray = enhancer.enhance(2.0)                     # boost contrast
   gray = gray.filter(ImageFilter.SHARPEN)          # sharpen
   ```

   **Choosing PSM mode** — try different Page Segmentation Modes and pick the best:
   | PSM | When to use |
   |-----|-------------|
   | `3` | Fully automatic (default) — good for mixed content |
   | `4` | Single column of text — dialogs, error panels |
   | `6` | Single uniform block of text — headers, labels |
   | `11` | Sparse text with no particular order — UI elements |
   | `12` | Sparse text with OSD — last resort for noisy images |

   **Splitting tall images** — very long images (e.g. 867×8521 px — a multi-screen scroll) exceed what Tesseract handles in one pass. Split into vertical slices:
   ```python
   from PIL import Image

   img = Image.open(path)
   w, h = img.size
   n_parts = 6  # adjust based on height
   part_h = h // n_parts

   for i in range(n_parts):
       y0 = i * part_h
       y1 = (i + 1) * part_h if i < n_parts - 1 else h
       crop = img.crop((0, y0, w, y1))
       text = pytesseract.image_to_string(crop, lang='rus', config='--psm 6 --oem 3')
       print(f"--- Part {i+1}/{n_parts} ---")
       print(text.strip())
   ```

   ```python
   import pytesseract
   text = pytesseract.image_to_string(gray, lang='rus+eng', config='--psm 6 --oem 3')
   ```

   **Confidence-based filtering** — use `image_to_data` to filter out low-confidence reads:
   ```python
   data = pytesseract.image_to_data(gray, lang='rus+eng', config='--psm 6 --oem 3',
                                     output_type=pytesseract.Output.DICT)
   for i, text in enumerate(data['text']):
       if text.strip() and data['conf'][i] > 0:
           print(f"  [{data['conf'][i]}%] {text.strip()}")
   ```

3. **marker-pdf**

4. **Vision models in the main session** — only when the above methods fail and the text is clearly readable to a human eye. Do NOT delegate; use the main session model directly. Be honest if the text is too small to read reliably.

**If vision_analyze tool is unavailable** — do not fabricate the content. Use the pytesseract workflow above. The `vision_analyze` tool may not be available in all Hermes backends/configurations; pytesseract is a reliable local fallback.

**If text is too small** — tell the user directly. Do NOT invent plausible-sounding content. Ask the user to provide a higher-resolution image or crop/zoom.

**Signs of hallucination in OCR output:**
- Text reads smoothly but doesn't quite make sense
- Code snippets with realistic-looking but slightly wrong function names
- Russian text that's grammatically broken in odd ways

---

## OCR монтажа страниц одной картинкой (без tesseract)

> **Сначала замерь движки на одной странице — это решает всю задачу.** Прямой замер на книжной странице 927 px:
> **tesseract `--psm 6 -l eng` ≈ 1.5 с/страница** против **RapidOCR ≈ 10 с/страница**; при этом tesseract нашёл
> **14 из 15 строк**, которые RapidOCR выбрасывал целиком (строки другим шрифтом — курсив, цитаты, сноски).
> Вывод для целой книги: tesseract первым, RapidOCR — вторым мнением для спорных мест.
> Ускорения параллелизмом нет: onnxruntime уже берёт все ядра, 4 процесса дали 0.8× (замерено).
> Ставить: `winget install --id UB-Mannheim.TesseractOCR --exact` → `C:\Program Files\Tesseract-OCR\tesseract.exe`.
> Если есть исходный PDF/EPUB — OCR не нужен вообще: `pymupdf` вытащит текст мгновенно и точно.


Класс задачи: на входе одна высокая картинка со стопкой страниц («чётко видны границы между страницами»),
на выходе — постраничный текст. Работает в `ocrenv` (`rapidocr_onnxruntime` + PIL + cv2, CPU).

1. **Границы страниц — не белые поля, а светло-серые полосы во всю ширину.** Признак: почти все пиксели
   строки < 250 (`(a<250).sum(axis=1) == ширина`). Белые разрывы дают ложные границы — по ним резать нельзя.
   Центры серых полос — границы страниц; первая полоса обычно шапка/интерфейс.
2. **Готовь страницу так: 3× LANCZOS + `UnsharpMask(radius=2, percent=120)`.** На 2× RapidOCR клеит слова
   («wasdiscoveredasDNAin thechromosomespresentin»), на 3× с шарпом текст читается чисто. Второе мнение
   (для спорных строк): 4× + `MedianFilter(3)` + бинаризация по Оцу.
3. **Строки восстанавливай по координатам:** `(round(y/шаг), x)` — иначе колонтитул или сноска влезет в середину абзаца.
4. **Главная напасть: строки, набранные другим шрифтом (курсив/цитата), OCR выбрасывает целиком.** Их ищи
   по шагу между строками: медиана ≈ шаг строки; если между двумя строками шаг > 1.6×медианы и предыдущая строка
   не закончила предложение, а следующая начинается со строчной — между ними потеряна строка. На странице в 45 строк
   таких пропусков бывает 1–3. Дальше: вырезать полосу, апскейл 5–6×, OCR заново; если оценка < 0.85 —
   **прочитать самому через vision** (собрать все спорные полосы в один вертикальный композит с подписями номеров
   и прочитать одним вызовом). Строка-«склейка» из двух полуслов (`physical ob-` + `jects,`) опознаётся по шагу ≥ 2× медианы.
5. **Склеенные слова внутри строки** ищи по словарю (`words_alpha.txt`): токены длиной ≥ 20 символов, которых нет
   в словаре. Их немного (у нас 2 на 4 000 слов), но каждый закрывается чтением строки через vision.
6. **Переносы:** склеивать `строка-` + строчная следующей без дефиса; `--` → `—`; `\xa0` → пробел; 3+ пустых строки → одна.
  Параграф — разрыв, когда шаг > 1.45× медианы (искусственные вставки не должны создавать разрыв).
7. **Проверка без неё отчёт не готов:** число строк/слов на страницу в разумных пределах; фразы на каждом
   стыке вставки (`«…genes need in some way to be realized…»`) должны находиться в собранном тексте. Одно это ловит
   и потерянные строки, и сдвиг вставки на строку вверх/вниз.
8. Монтаж часто **неполный** (у нас были страницы 30, 31, 33, 34, 37, 38, 39, 41, 44, 46 — без 32, 35, 36, 40, 42, 43, 45):
   определяй номера по колонтитулу (чётная — номер слева, нечётная — справа), а не по порядку полос, и скажи Юрию, каких страниц нет.
   Заголовок главы («2» отдельной строкой) — это номер главы, а не страница: не спутать.

## Notes

- `web_extract` is always first choice for URLs
- pymupdf is the safe default — instant, no models, works everywhere
- marker-pdf is for OCR, scanned docs, equations, complex layouts — install only when needed
- Both helper scripts accept `--help` for full usage
- marker-pdf downloads ~2.5GB of models to `~/.cache/huggingface/` on first use
- For Word docs: `pip install python-docx` (better than OCR — parses actual structure)
- For PowerPoint: see the `powerpoint` skill (uses python-pptx)
