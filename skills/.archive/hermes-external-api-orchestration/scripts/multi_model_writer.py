#!/usr/bin/env python3
"""
Multi-Model Writer
Sends the same prompt to two models via OpenRouter and saves results to separate files.
Models: x-ai/grok-4 and google/gemini-2.5-flash
"""

import os
from datetime import datetime
from pathlib import Path
from openai import OpenAI

# ====================== CONFIG ======================
OPENROUTER_API_KEY=os.get...
if not OPENROUTER_API_KEY:
    raise EnvironmentError("OPENROUTER_API_KEY not found in environment variables")

OUTPUT_DIR = Path("G:/_My_Programming/HERMES-AGENT/outputs")
HISTORY_FILE = Path("G:/_My_Programming/HERMES-AGENT/prompt_history.md")

MODELS = {
    "grok": "x-ai/grok-4",
    "gemini": "google/gemini-2.5-flash"
}

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)


def call_model(model_name: str, prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
            max_tokens=2500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR] {str(e)}"


def save_output(model_key: str, content: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{model_key}_{timestamp}.md"
    filepath = OUTPUT_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {model_key.upper()} Output\n\n")
        f.write(content)
        f.write("\n")

    print(f"✓ Saved {model_key} → {filepath}")
    return filepath


def log_to_history(prompt: str, grok_path: Path, gemini_path: Path):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"""
## {timestamp}

**Prompt:**
```
{prompt}
```

**Outputs:**
- Grok 4: `{grok_path.name}`
- Gemini 2.5 Flash: `{gemini_path.name}`

---

"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(entry)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prompt = input("Enter prompt:\n\n").strip()
    if not prompt:
        print("Empty prompt. Exiting.")
        return

    print("\nCalling models...")
    grok_out = call_model(MODELS["grok"], prompt)
    gemini_out = call_model(MODELS["gemini"], prompt)

    grok_file = save_output("grok", grok_out)
    gemini_file = save_output("gemini", gemini_out)

    log_to_history(prompt, grok_file, gemini_file)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()