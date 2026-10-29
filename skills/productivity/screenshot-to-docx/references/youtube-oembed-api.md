# YouTube oEmbed API — Fetch Video Metadata Without API Key

The YouTube oEmbed endpoint returns video title, channel name, and thumbnail URL
for any public YouTube URL. No authentication, no API key, no JavaScript.

## Endpoint

```
GET https://www.youtube.com/oembed?url=<URL_ENCODED_YOUTUBE_URL>&format=json
```

## Response

```json
{
  "title": "Video title here",
  "author_name": "Channel Name",
  "author_url": "https://www.youtube.com/@channel",
  "thumbnail_url": "https://i.ytimg.com/vi/VIDEOID/hqdefault.jpg",
  "width": 480,
  "height": 270,
  "html": "<iframe ...></iframe>",
  "type": "video",
  "version": "1.0",
  "provider_name": "YouTube",
  "provider_url": "https://www.youtube.com/"
}
```

## Python Example

```python
import urllib.request, json, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False  # needed behind some proxies
ctx.verify_mode = ssl.CERT_NONE

url = "https://youtube.com/shorts/BFoFfcz6BNs"
oembed = f"https://www.youtube.com/oembed?url={urllib.request.quote(url, safe='')}&format=json"

req = urllib.request.Request(oembed, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
    data = json.loads(resp.read())

print(data['title'])       # "Some video title"
print(data['author_name'])  # "Channel Name"
```

## Error Codes

| Code | Meaning |
|------|---------|
| 200  | Success |
| 400  | Bad request (malformed URL, or URL doesn't point to a valid video) |
| 401  | Unauthorized (private/unlisted video) |
| 404  | Video not found (deleted, incorrect video ID) |

## Rate Limiting

No official rate limit documented, but 0.2s delay between requests is safe.

## Limitations

- Does NOT work for channel pages (youtube.com/@channel) — only individual videos
- Does NOT return description text — only title and author
- Requires the exact video ID to be correct — OCR-corrupted IDs will return 404 or 400