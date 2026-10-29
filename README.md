# HERMES-AGENT-SKILL-ARCHIVE — общие скиллы Hermes для всех ПК

Приватный репозиторий. Через него ПК1, ПК2 и ноутбук обмениваются **личными**
скиллами Hermes Agent: находка или новый скилл на одной машине после `git push`
доступны на остальных после `git pull`.

- Как устроена синхронизация, правила, онбординг ПК — [`SYNC-LOGIC.md`](SYNC-LOGIC.md)
- Что и когда менялось — [`CHANGELOG.md`](CHANGELOG.md)

## Главное

На **каждом** ПК репозиторий клонирован по одному и тому же пути:

```
E:\_MY-PROGRAMMING\HERMES-AGENT-SKILL-ARCHIVE
```

и подключён к Hermes напрямую: Hermes читает скиллы **из этой папки** и сюда же
записывает новые. Копировать скиллы в `%LOCALAPPDATA%\hermes\skills` **не нужно и
нельзя** — локальная копия с тем же именем молча затеняет версию из репо.

```yaml
# %LOCALAPPDATA%\hermes\config.yaml
skills:
  create_dir: E:/_MY-PROGRAMMING/HERMES-AGENT-SKILL-ARCHIVE/skills
```

Ежедневно: `git pull` перед работой, `git add -A && git commit && git push` после.
Подключение нового ПК — `SYNC-LOGIC.md` §5.

## Что в репо

Только личные скиллы, по категориям как в Hermes (`skills/<категория>/<имя>/`).
Встроенные скиллы Hermes (`computer-use`, `github-*` и т.п.) сюда не кладём — их
обновляет сам Hermes.

| Категория | Скиллы |
|---|---|
| `autonomous-ai-agents` | `hermes-skills-cross-pc-sync`, `personal-hermes-guide` |
| `email` | `mail-aliexpress`, `mail-export`, `mail-inbox`, `mail-translate` |
| `idea-workflow` | `idea-superpowers-suite`, `idea-to-design-doc`, `idea-to-implementation-doc`, `idea-to-ui-design-brief` |
| `media` | `video-source-resolve` → `video-fetch` → `video-batch-runner`; `video-compression` |
| `productivity` | `book-translate-and-voice`, `cost-model-today`, `image-ocr-to-docx`, `ocr-and-documents`, `overview-projects-on-computer`, `save-to-google-drive`, `screenshot-to-docx`, `whatsapp-yt-links` |
| `software-development` | `coder-terminal-workflow`, `plan`, `robocopy-migration` |

`home-accounting` живёт в своём репо `HERMES-ALL-IN-ONE` и подключается через
`skills.external_dirs` — здесь его нет.

### `scripts/` — утилиты вне скиллов

| Файл | Куда класть | Зачем |
|---|---|---|
| `smart_dl.py` | `C:\Users\<user>\.hermes\` | загрузчик aria2c + Python-докачка (`video-fetch`) |
| `aria2c.exe` (+ `aria2c-COPYING.txt`, GPL v2) | `C:\Users\<user>\.hermes\` | только если aria2c не поставлен через `winget install aria2.aria2` |
| `create_docx_template.py` | `C:\Users\<user>\.hermes\` | шаблон Word (TNR 12, A4) для `screenshot-to-docx` |

## Зависимости

| Компонент | Для чего |
|---|---|
| Python 3.11+, `pip install -r requirements.txt` | python-docx, pillow, pytesseract, yt-dlp |
| Tesseract OCR 5.4+ (UB-Mannheim) с языком `rus` | `screenshot-to-docx`, `image-ocr-to-docx` |
| ffmpeg / ffprobe | `video-compression`, проверка видео |
| aria2c | многопоточная загрузка (`video-fetch`) |

## Приватность

В репо не коммитятся чаты, выгрузки, документы (`*.docx`, `*.pdf`, `*.zip`),
cookies и ключи — см. `.gitignore`. Перед push просматривать `git status --short`.
