#!/usr/bin/env python3
"""
Vision Writer
Sends images + prompt to a vision-capable model via OpenRouter.
Default model: x-ai/grok-4.3

Usage:
  python vision_writer.py [image1.png] [image2.jpg] ...
  (or run with no args to enter paths interactively)
"""

import os
import base64
import sys
from datetime import datetime
from pathlib import Path
from openai import OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise EnvironmentError("OPENROUTER_API_KEY not found. Run: setx OPENROUTER_API_KEY 'sk-or-...'")

OUTPUT_DIR = Path("G:/_My_Programming/HERMES-AGENT/outputs")
HISTORY_FILE = Path("G:/_My_Programming/HERMES-AGENT/prompt_history.md")
MODEL = "x-ai/grok-4.3"

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp"}.get(ext, "image/jpeg")


def call_vision_model(prompt: str, image_paths: list, max_tokens: int) -> str:
    content = []
    for img in image_paths:
        content.append({"type": "image_url",
                         "image_url": {"url": f"data:{get_mime(img)};base64,{encode_image(img)}"}})
    content.append({"type": "text", "text": prompt})
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": content}],
            temperature=0.9, max_tokens=max_tokens)
        if r.choices and r.choices[0].message.content:
            return r.choices[0].message.content.strip()
        return "[ERROR] Empty response"
    except Exception as e:
        return f"[ERROR] {e}"


def save_output(content: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fp = OUTPUT_DIR / f"grok_vision_{ts}.md"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"# GROK Vision Output\n**Timestamp:** {ts}\n\n---\n\n{content}\n")
    print(f"✓ Saved → {fp}")
    return fp


def main():
    print(f"=== Vision Writer ===\nModel: {MODEL}\n")
    image_paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not image_paths:
        print("Enter image paths (empty line to finish):")
        while True:
            p = input(f"  Photo {len(image_paths)+1}: ").strip()
            if not p:
                break
            image_paths.append(p) if Path(p).exists() else print(f"  [WARN] Not found: {p}")
    if not image_paths:
        print("No images. Exiting.")
        return

    prompt = input("\nEnter prompt:\n\n").strip()
    if not prompt:
        print("Empty prompt. Exiting.")
        return

    min_words = int(input("\nMin words: ").strip())
    max_words = int(input("Max words: ").strip())
    max_tokens = int(max_words * 1.4)

    print(f"\nRange: {min_words}–{max_words} words → ~{max_tokens} tokens\nCalling model...\n")
    output = call_vision_model(prompt, image_paths, max_tokens)
    print("\n" + "="*50 + "\n" + output + "\n" + "="*50)
    save_output(output)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()
