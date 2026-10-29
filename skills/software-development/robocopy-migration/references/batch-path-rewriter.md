# Batch path rewriter (Python)

Use when scan finds dozens of files with stale disk paths. Follow DEV-NOTES section 14.3.

## Template

```python
import os

FOLDERS = [r'F:\TARGET']
TEXT_EXTS = {'.py', '.ps1', '.bat', '.json', '.env', '.md', '.txt', '.yml', '.yaml', '.cfg', '.ini'}

REPLACEMENTS = [
    (r'G:\AI\OLD_FOLDER\\', r'F:\NEW_FOLDER\\'),
]

SKIP_IF_ONLY = [
    r'G:\AI\_MY_PROGRAMMING\\',  # not yet migrated
    r'G:\_My_Programming',         # different drive
    r'https://github.com/',
]

def should_skip_file(name):
    return name.startswith('session-') and name.endswith('.json')

def apply(content):
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    return content

for folder in FOLDERS:
    for root, dirs, files in os.walk(folder):
        parts = root.split(os.sep)
        if '.git' in parts or '__pycache__' in parts:
            continue
        if '.claude' in parts and 'worktrees' in parts:
            continue
        for fname in files:
            if os.path.splitext(fname)[1].lower() not in TEXT_EXTS:
                continue
            if should_skip_file(fname):
                continue
            path = os.path.join(root, fname)
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if 'G:\\' not in content:
                continue
            new_content = apply(content)
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'CHANGED: {path}')
```

## Control scan after replace

```powershell
$ext = '\.(bat|ps1|py|yaml|yml|env)$'
$hits = @()
foreach ($root in @('F:\TARGET1','F:\TARGET2')) {
  Get-ChildItem $root -Recurse -File | Where-Object { $_.Extension -match $ext } |
    ForEach-Object {
      if (Select-String -Path $_.FullName -Pattern 'G:\\AI\\STALE_PATH' -SimpleMatch -Quiet) {
        $hits += $_.FullName
      }
    }
}
"operational hits=$($hits.Count)"
```

Expect 0 hits.

## PC1 note (2026-08-26)

After G: rebuild, WORK volume is `G:\_MY-PROGRAMMING_1`. Adjust REPLACEMENTS for actual source/target pairs on this PC.
