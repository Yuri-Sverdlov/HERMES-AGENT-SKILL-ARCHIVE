---
name: pdf-broken-text-layer-repair
description: Repair PDFs whose text layer extracts garbled characters.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [pdf, tounicode, cmap, fonttools, freetype, text-extraction, ocr-free]
    related_skills: [book-translate-and-voice, ocr-and-documents]
---

# Repair a broken PDF text layer (no OCR)

## When to Use
- A PDF extracts as substituted characters (`writinN`, `coPer`, `8nd`) while rendering perfectly.
- A glyph-name based fixer (`pdf-cmap-fixer`, `pdf-fix-tuc`, `pdf-tounicode-fix`) reported nothing to repair.
- The text must be exact and OCR noise is not acceptable.
- Counter-case: if the page has no text layer at all, this skill does not apply — OCR it.

Some publisher PDFs (seen with Myth HQ / Jason Hamilton books, output of Google Docs and
calibre pipelines) **render perfectly but extract as substituted characters**:
`writing`→`writinN`, `cover`→`coPer`, `find`→`8nd`, `-`→`(`, `:`→`R`, `s`→`E`.
MuPDF and poppler return the same garbage, the visual layer is fine — so the text is
recoverable deterministically, no pixels need to be recognised.
Worked example with all measurements: see the task brief the user keeps next to the books
(`TASK-cmap-repair.md`) and the scripts in `%LOCALAPPDATA%\hermes\audio-work\`.

## Diagnose first (5 minutes, decides everything)
1. `chars = len(page.get_text())`, `page.get_images()` per page — empty text means a scan, stop here and OCR.
2. Ratio of alphabet tokens present in an English wordlist (`words_alpha.txt` from dwyl/english-words).
   A clean text layer scores 99 %+; a broken one 0–60 %.
3. Count control characters (`ord(c) < 32`) and look for tell-tale substitutions.
4. Dump the fonts: `page.get_fonts(full=True)` then `doc.extract_font(xref)`.
   - `/Type0` + `/CIDFontType2` + `/Identity-H` is the usual shape.
   - With fontTools check the embedded subset's tables: if you see only
     `glyf, head, hhea, hmtx, loca, maxp, prep` and glyph names like `glyph00001`,
     **glyph names and cmap are stripped** — glyph-name based tools cannot work.
5. Prove that the content-stream code equals CID equals GID: compare the PDF's `/W` widths array
   with the subset's `hmtx` (560/1024·1000 = 546.875 matched). If code == GID you can rebuild
   `/ToUnicode` per code directly.
6. Read `doc.metadata['creator']` / `['producer']` and the copyright page **before working book by book**. Books
   assembled programmatically (`creator: pdf-lib`, as opposed to a Word/InDesign export) carry the *same* defect in
   every file of the batch, so one fixer script and one font inventory cover them all. The imprint on the copyright
   page is the fastest way to see which files belong to the same batch (one LLC can account for three separate books).

## Why the usual tools fail here
`pdf-cmap-fixer`, `trueroad/pdf-fix-tuc`, `zhanghao50671/pdf-tounicode-fix` rebuild `ToUnicode`
from **glyph names**; stripped subsets leave them nothing to read. `pdftotext`, `pdfminer`,
`pikepdf` all trust the same broken table.

## Method A — outline matching against the original font
1. Identify the real typeface from `/BaseFont` (e.g. `VVDCFP+CrimsonPro-Regular`).
2. Download the original from Google Fonts (Crimson Pro, EB Garamond, Noto Sans) and instantiate the
   variable font at the right weight with `fontTools.varLib.instancer.instantiateVariableFont`.
3. For every glyph of the subset, pick the original glyph with the closest outline; map
   `GID → glyph name → Unicode` (via the original's cmap reverse map, fallback `fontTools.agl`).
4. Rebuild the CMap and overwrite the stream:
   `doc.update_stream(tu_xref, cmap_bytes)` where cmap_bytes is
   `/CIDInit /ProcSet findresource begin … 1 begincodespacerange <0000> <FFFF> endcodespacerange …
   N beginbfchar <code> <unicode…> endbfchar … endcmap …`.
   A glyph may need **two code points** (ligature: `<0003> <00660069>` for `fi`).
5. Save, re-extract, re-measure with the wordlist.
Measured: 143 subsets patched / 6 056 glyphs mapped in one 324-page book → **86.4 %** dictionary words.
Map empty-outline glyphs to a space explicitly, or words lose their spaces (`bas cs of wr t ng`).

## Method B — raster matching (needed for the last ~14 %)
Subset outlines are **re-quantised**: same shape, different point count and metrics
(`l`: 28 pts / adv 310 vs 27 pts / adv 269, systematic ~+20 unit x shift, identical upem 1024).
Point-by-point matching therefore caps out. Instead:
- render each glyph with `freetype-py` (`FT_LOAD_NO_HINTING | FT_LOAD_RENDER`),
- crop to ink, scale to a 16×16 / 24×24 grid, compare by pixel difference or perceptual hash,
- use the `/W` width only as a candidate **filter**, never as the criterion.
Residual to expect: lowercase `i`/`j` are stored as dotless forms plus a combining dot — map the
pair or normalise `ı̇`→`i`, `ȷ̇`→`j` in the extracted text afterwards.

## Verify before trusting any extraction
- wordlist ratio (target ≥ 99.5 %), zero lost characters, no control bytes;
- OCR the rendered pages (`rapidocr-onnxruntime`, 220 dpi, ~2.5 s/page) purely as an
  independent reference: require ≥ 99.5 % character agreement on a sample of pages;
- for audiobook pipelines also check duration sum == combined file and a `-ss 2h+` seek.

## Pitfalls
- Every subset has its own wrong table (143 of them in one book) — patch per font xref, dedupe by ToUnicode xref.
- Run scripts with a sanitised environment: an inherited `PYTHONPATH` makes a foreign `edge_tts`/
  `numpy` shadow the venv one (`ImportError: numpy._core._multiarray_umath`).
- Do not keep venvs or sources in `hermes\cache\scratch` — pruned after ~24 h idle; use a durable work dir.
- OCR is a perfectly good fallback when speed matters more than perfection: 804 pages took 33.8 min,
  and a translator smooths the residual noise. The no-OCR route is for when the text must be exact.
