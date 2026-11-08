#!/usr/bin/env python3
"""
clean_model_command.py — sanitize a Hermes /model slash-command.

Problem this solves
--------------------
The in-session `/model --provider <slug> --model <id>` command rejects input
with the error "Model names cannot contain spaces." whenever the model id (or
provider slug) contains ANY Unicode whitespace — most commonly a non-breaking
space (U+00A0) or a zero-width character (U+200B etc.) that sneaks in via
copy/paste from a chat app or browser. The command LOOKS correct but fails.

What this does
--------------
Takes a pasted (possibly "dirty") /model command, or a bare provider+model,
removes every invisible / Unicode-whitespace character from the provider slug
and model id (these tokens never legitimately contain whitespace), rebuilds a
clean ASCII command, prints it, and (on Windows) copies it to the clipboard via
clip.exe so you can paste it straight back into the session.

It does NOT type into the live session for you (an external script can't drive
the in-session slash command). It hands you a guaranteed-clean string to paste.

Usage
-----
  # From a dirty pasted command (quote it!):
  python clean_model_command.py "/model --provider openrouter --model deepseek/deepseek-chat"

  # From provider + model as two args:
  python clean_model_command.py openrouter deepseek/deepseek-chat

  # From stdin (e.g. piping the clipboard):
  echo "<pasted command>" | python clean_model_command.py

Exit codes: 0 = clean command produced, 2 = could not parse provider/model.
"""
import re
import sys
import subprocess

# Zero-width / BOM / word-joiner / soft hyphen -> deleted everywhere.
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
# Any Unicode whitespace char (used to detect/strip inside tokens).
WS = re.compile(r"\s", flags=re.UNICODE)


def strip_all_ws(token: str) -> str:
    """A provider slug / model id never contains whitespace: remove ALL of it."""
    return WS.sub("", token.translate(ZERO_WIDTH))


def _capture(text: str, flag: str) -> str | None:
    """
    Grab the value after `--flag`, spanning across any spurious internal
    whitespace, up to the next real `--flag` or end of string. Then scrub it.
    """
    m = re.search(rf"{flag}\s+(.*?)(?=\s--\w|\Z)", text, flags=re.DOTALL)
    if not m:
        return None
    val = strip_all_ws(m.group(1))
    return val or None


def parse(text: str):
    """Extract (provider, model) from a string in any supported shape."""
    text = text.translate(ZERO_WIDTH)
    provider = _capture(text, "--provider")
    model = _capture(text, "--model")
    if provider and model:
        return provider, model
    # Fallback: two bare tokens "provider model" (model id usually has a slash).
    cleaned = WS.sub(" ", text.replace("/model", "")).strip()
    toks = [strip_all_ws(t) for t in cleaned.split() if not t.startswith("--")]
    toks = [t for t in toks if t]
    if len(toks) >= 2:
        return provider or toks[0], model or toks[1]
    return provider, model


def copy_to_clipboard(text: str) -> bool:
    """Best-effort copy to the Windows clipboard via clip.exe."""
    try:
        subprocess.run(["clip.exe"], input=text.encode("utf-16-le"), check=True)
        return True
    except Exception:
        return False


def main(argv):
    if len(argv) >= 3 and not argv[1].startswith(("-", "/")):
        provider, model = strip_all_ws(argv[1]), strip_all_ws(argv[2])
    else:
        raw = " ".join(argv[1:]) if len(argv) > 1 else sys.stdin.read()
        provider, model = parse(raw)

    if not provider or not model:
        print("ERROR: could not find both a provider and a model in the input.",
              file=sys.stderr)
        print('Usage: clean_model_command.py "/model --provider <slug> --model <id>"',
              file=sys.stderr)
        return 2

    return f"/model --provider {provider} --model {model}"


if __name__ == "__main__":
    out = main(sys.argv)
    if isinstance(out, int):
        sys.exit(out)
    print(out)
    if copy_to_clipboard(out):
        print("\n(Copied to clipboard — paste it into the session.)", file=sys.stderr)
    sys.exit(0)
