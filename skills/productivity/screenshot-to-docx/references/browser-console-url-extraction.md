# Browser Console — Alternative URL Extraction Path

When Tesseract OCR produces unusable URLs (common with mixed Latin/Cyrillic screenshots), Hermes's `browser_console` tool offers a cleaner extraction path.

## When to use

- Screenshot contains YouTube/social media links mixed with Russian text
- Tesseract consistently garbles the Latin portions of URLs
- The image is on disk (served via local HTTP) — NOT a live web page

## Workflow

### 1. Serve the image locally

```bash
cd /path/to/images && python -m http.server 8765 &
```

### 2. Navigate to the image fragment

```python
browser_navigate(url="http://localhost:8765/part_1.jpg")
```

### 3. Extract text via vision

```python
browser_vision(question="Read ONLY the YouTube URLs on this image. Latin script only. One per line.")
```

### 4. Alternatively: if the source is a live web page (WhatsApp Web)

```python
browser_console(expression="""
  [...document.querySelectorAll('a[href*="youtube.com"], a[href*="youtu.be"]')]
    .map(a => JSON.stringify({url: a.href, text: a.textContent}))
    .join('\\n')
""")
```

## Pros/Cons vs Tesseract

| | Tesseract OCR | browser_vision |
|---|---|---|
| URL accuracy | 35-50% | 80-95% |
| Speed | ~10s per part | ~15s per part (round-trip) |
| Cost | Free | Free (local) |
| Batch | Parallel via Python | Sequential (one image at a time) |
| Russian text | Good (with rus traineddata) | Better (vision model reads mixed) |
| Setup | pip install + language data | None — Hermes built-in |

## Recommendation

For **critical** URL extraction from a screenshot:
1. Try Tesseract dual-pass first (eng + rus with preprocessing)
2. For the URLs that oEmbed rejects (404/400), re-read those specific image fragments through browser_vision
3. Fall back to WhatsApp chat export (.txt) if the source allows it