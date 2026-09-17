# robocopy-migration — скилл для миграции папок между дисками

## Что это

Скилл для Hermes Agent, автоматически созданный 2026-08-25 в сессии MIGRATION-G-F. Документирует весь процесс переноса папок с одного диска на другой через robocopy с проверкой, сканированием и починкой путей.

## Зачем создан

В ходе сессии были перенесены 5 партий папок с G: на F: (общий объём >700 ГБ, >250 000 файлов):

| Партия | Папки | Файлов |
|--------|-------|--------|
| 1 | 6 папок (Ollama, LM Studio, ...) | проверка |
| 2a | 8 мелких папок | 1–110 каждая |
| 2b | `_MY_PROGRAMMING_4`, `_MY_PROGRAMMING_2` | 767 + 4776 |
| 4 | `_MY_PROGRAMMING` (гигант) | 101 019 |
| 5 | COMFYUI-SHARED, COMFYUI_PORTABLE, COMFY_UI | 221 + 57 472 + 43 294 |

В процессе были найдены и исправлены грабли, которые теперь зафиксированы в скилле, чтобы не наступать на них повторно.

---

## Полное содержание скилла

### 1. Копирование — robocopy

```powershell
robocopy "SRC" "DST" /E /COPY:DAT /R:1 /W:1
```

- **Exit code 0–7** = успех (0 = нечего копировать, 1+ = скопировано)
- **Exit code 8+** = ошибка, стоп
- Для больших папок (+1 GB или много файлов): добавить `/MT:16` **и** запускать в фоне с `notify_on_complete=true`
- Если DST уже существует — robocopy дозапишет/обновит (идемпотентно)

### 2. Проверка — число файлов src = dst

```powershell
$src = (Get-ChildItem "SRC" -Recurse -File).Count
$dst = (Get-ChildItem "DST" -Recurse -File).Count
"SRC -> src=$src dst=$dst match=$($src -eq $dst)"
```

**Без match=True** перенос не засчитывать. При расхождении — перезапустить robocopy.

### 3. Скан — поиск жёстких путей исходного диска

Писать **временный `.ps1` файл**, а не inline `pwsh -Command` — вложенные кавычки и бэкслеши ломают парсинг.

Фильтр расширений текстовых файлов:
```powershell
$_.Extension -match '\.(py|ps1|bat|json|env|md|txt|yml|yaml|cfg|ini)$'
```

Поиск: `Select-String -SimpleMatch -Quiet`, дедупликация: `Sort-Object -Unique`.

### 4. Починка — патч путей

Для единичных файлов — `patch(mode='replace')`:

```
G:\AI\OLD_FOLDER\... → F:\NEW_FOLDER\...
```

**Главное правило:** не менять пути к папкам, которые ещё не перенесены.

### 5. Массовая замена (200+ файлов) — сразу Python

Когда скан выдаёт десятки файлов, **не использовать PowerShell одного-лайн и не делегировать сабагентам**:

- В `pwsh -Command` легко ошибиться в синтаксисе (`$_Extension` вместо `$_.Extension`)
- Сабагенты падают (нет кредитов, таймаут) — приходится переписывать в Python

**Правильный путь — сразу Python-скрипт** (следует правилу DEV-NOTES §14.3):

```python
import os, re

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
        if '.git' in parts or '__pycache__' in parts: continue
        if '.claude' in parts and 'worktrees' in parts: continue
        for fname in files:
            if os.path.splitext(fname)[1].lower() not in TEXT_EXTS: continue
            if should_skip_file(fname): continue
            with open(os.path.join(root, fname), 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if 'G:\\' not in content: continue
            # Проверка: все G:\ рефы — из списка пропуска?
            if all(pat in content for pat in SKIP_IF_ONLY): continue
            new_content = apply(content)
            if new_content != content:
                with open(os.path.join(root, fname), 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'CHANGED: {os.path.join(root, fname)}')
```

### 5a. Особый случай: install_path.txt

Одноcтрочные конфиги легко пропустить. Искать явно:

```powershell
Get-ChildItem $root -Recurse -Filter 'install_path.txt'
```

Пример: `G:\AI\COMFYUI_PORTABLE` → `F:\COMFYUI_PORTABLE`

### 5b. ComfyUI config cascade

Порядок копирования важен (SHARED → PORTABLE → COMFY_UI), потому что конфиги ссылаются друг на друга:

| Файл | Что править |
|------|------------|
| `COMFYUI-SHARED/tools/comfy_shared/config.py` | `SHARED_ROOT`, `WORKING_COMFYUI`, `SCAN_ROOTS` (3 независимых пути) |
| `COMFYUI-SHARED/extra_model_paths.yaml` | `base_path` (слеши: `G:/AI/...` → `F:/...`) |
| `COMFYUI_PORTABLE/ComfyUI/extra_model_paths.yaml` | Любые `G:/AI/COMFYUI-SHARED` |
| `COMFY_UI/extra_models_config.yaml` (может быть 2 копии) | Legacy `G:\...\COMFY_UI` — regex: `$text -replace 'G:\\\\[^\\\\]+\\\\COMFY_UI', 'F:\\COMFY_UI'` |

### 6. Dual-path pitfall

Одна и та же папка может быть и **в корне** G:, и **вложена** в другую мигрируемую папку:

- `G:\AI\COMFYUI_PORTABLE\...` (корень) → `F:\COMFYUI_PORTABLE\...`
- `G:\AI\_MY_PROGRAMMING_2\COMFYUI_PORTABLE\...` (вложена) → `F:\_MY_PROGRAMMING_2\COMFYUI_PORTABLE\...`

Правила замены — **от конкретного к общему**: сначала вложенный путь, потом корневой.

### 7. Контрольный скан

После массовой замены — узкий скан по операционным файлам:

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

Ожидание: **0 hits**. Если есть — править вручную.

### 8. Исторические строки в README

Строки вида `- **Откуда:** G:\AI\...` / `- **Куда:** G:\AI\...` — это **история миграции**, не рабочие пути. Не трогать.

---

## Грабли (pitfalls)

### `$_Extension` vs `$_.Extension`
В PowerShell `$_Extension` — синтаксическая ошибка. Нужно `$_.Extension`. Если скан возвращает 0 — проверь эту опечатку. Лучше вообще не использовать PowerShell для много-папочных сканов — сразу Python.

### Регистрозависимость патча
Если в коде `g:\AI\...` (нижний регистр), а патч ищет `G:\AI\...` — тихо не сработает. Проверять `Select-String` после патча.

### `Format-Table` блокируется хуком
Хук защиты от `rm -rf` может ложно заблокировать любую команду со словом "Format". Использовать `Out-String` или `foreach { "..." }`.

### Таймаут на больших файлах
22 GB `flux1-schnell.safetensors` копируется 2+ минуты. Синхронный robocopy с коротким таймаутом убьёт процесс. Ставить `timeout=600` или фон.

### Fork-bomb на 3+ параллельных robocopy
Не запускать 3+ robocopy в параллель с `/MT:16` — диск I/O насыщается. Маленькие папки — синхронно, большие — последовательно в фоне.

### Оригиналы не удалять
Хук блокирует `rm -rf` / `Remove-Item -Recurse -Force`. Удаление — через Проводник (Shift+Delete).

### `.venv` не переносить
Не копировать и не чинить — пересоздать при запуске проекта.

### Дедупликация скана
`Get-ChildItem` с `-Recurse` может вернуть один файл несколько раз, если подпапки дублируются. Всегда `Sort-Object -Unique`.

---

## Структура отчёта REPORT.md

1. Результаты копирования (exit code для каждой папки)
2. Таблица проверки (src/dst/match)
3. Результаты скана путей (что найдено, что исправлено)
4. Особые случаи (GGUF dedup, config migration, и т.п.)
5. Итоговый вердикт

**Правило:** полный вывод команд в отчёте. Пустой stdout + exit 0 — не доказательство успеха.

---

## Дополнительно: ссылка на полный скилл

Скилл установлен в Hermes Agent под именем `robocopy-migration`:

- SKILL.md: `%LOCALAPPDATA%\hermes\skills\software-development\robocopy-migration\SKILL.md`
- Reference: `%LOCALAPPDATA%\hermes\skills\software-development\robocopy-migration\references\batch-path-rewriter.md`

На новом ПК можно импортировать через `skill_manage(action='create', name='robocopy-migration', ...)` или просто читать этот файл как памятку.