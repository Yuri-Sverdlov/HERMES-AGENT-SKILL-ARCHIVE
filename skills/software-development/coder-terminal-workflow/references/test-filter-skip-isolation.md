# Testing a skip/filter guard in cmd_all (or similar runner)

When writing a test for a skip/filter (e.g. `~$*` lock file filter), the test fixture must **pass every other guard** in the runner. Otherwise the test may "pass" because the lock file is caught by a different check (no frontmatter, empty sources), not by the filter under test.

## Pattern

1. **Add a `pages_root` parameter** to the runner function (e.g. `cmd_all(chats_dir, pages_root=None)`) so tests can point it at a temp directory instead of `HERE / "pages"`.

2. **Create a fixture that passes all other guards:**
   - Valid frontmatter (`---\ntitle: ...\nsources: [...]\nsources_hash: ""\n---`)
   - Non-empty sources pointing to a real chat (same chat directory and session_id)
   - The lock file in the same test axis dir

3. **Test three conditions:**
   - `lock_before == lock_after` (file not modified by regenerate)
   - Filename NOT in stdout (the filter prevented processing)
   - A valid page's name IS in stdout with `OK` or `SKIP` (the filter didn't block everything)

4. **Red test (mandatory):**
   - Temporarily comment out the filter line
   - Confirm the test FAILS (`lock_after != lock_before`, filename appears in stdout)
   - Restore the filter
   - Confirm the test PASSES again

## Example from TASK-023

```python
# ── тест 10: ~$* lock-файл не трогается при обходе ──────────
total += 1
pages_root_10 = tmp / "pages_test_10"
pages_axis_10 = pages_root_10 / "programming" / "projects"
pages_axis_10.mkdir(parents=True, exist_ok=True)

# Valid page with source pointing to existing chat
chat_10 = "---\ntitle: Chat for Lock Test\nsession_id: \"20260810_064525_095061\"\n---\n\nSome body content\n"
chat_file_10 = chats_test / "02_lock-chat.md"
write_file_utf8(chat_file_10, chat_10)

valid_page = ('---\n' 'title: Lock Test Page\n'
              'domain: ["programming"]\n' 'axis: project\n'
              'status: generated\n'
              'sources: ["pc1:hermes:20260810_064525_095061"]\n'
              'sources_hash: ""\n' 'updated: 2026-08-12\n' '---\n'
              '\n' '## Сводка\n' '\n' 'TODO\n')
valid_page_file = pages_axis_10 / "valid-lock-test.md"
write_file_utf8(valid_page_file, valid_page)

lock_file = pages_axis_10 / "~$lock.md"
lock_content = "---\ntitle: Lock File\nsources: [\"pc1:hermes:SOME_ID\"]\nsources_hash: \"\"\n---\n\nGARBAGE\n"
lock_file.write_text(lock_content, encoding='utf-8')
lock_before = read_file_utf8(lock_file)

import io
stdout_cap = io.StringIO()
old_stdout = sys.stdout
sys.stdout = stdout_cap
try:
    cmd_all(tmp / "chats", pages_root=pages_root_10)
except SystemExit:
    pass
sys.stdout = old_stdout
stdout = stdout_cap.getvalue()

lock_after = read_file_utf8(lock_file)
lock_unchanged = (lock_before == lock_after)
no_lock = ("~$lock" not in stdout)
valid_ok = "valid-lock-test" in stdout and ("OK" in stdout or "SKIP" in stdout)

if lock_unchanged and no_lock and valid_ok:
    passed += 1
    print("OK | tilde-lock: cmd_all skipped lock file, valid page OK")
else:
    print(f"FAIL | tilde-lock: unchanged={lock_unchanged} no_lock={no_lock} valid={valid_ok}")
```

## Key insight

The lock file content MUST have **valid frontmatter** (`---\n...\n---` structure) so the frontmatter/empty-sources guards don't catch it. If the lock file is just plain text (no frontmatter), the no-frontmatter guard will skip it and the test passes even with the filter removed — the test would be a false positive.