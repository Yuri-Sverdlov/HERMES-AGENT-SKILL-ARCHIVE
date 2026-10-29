---
name: save-to-google-drive
description: "Use when the user asks to save a message, analysis, or content to the cloud / Google Drive. Saves as Markdown (.md) with UTF-8 BOM to the user's sync folder. Asks user to confirm filename before uploading."
version: 1.0.0
author: Hermes Agent + Yuri
license: MIT
metadata:
  hermes:
    tags: [google-drive, cloud-sync, markdown, save]
    related_skills: [google-workspace]
---

# Save to Google Drive (Cloud Sync)

Сохраняет сообщение/контент как Markdown-файл в Google Drive папку для синхронизации между компьютерами.

## When to Use

Срабатывает на фразы:
- «сохрани в облаке»
- «сохрани в Google Drive»
- «закинь в гугл диск»
- «save to cloud»
- «сохрани это в папку синхронизации»
- Любая вариация с просьбой сохранить контент в облачное хранилище

## Target Folder

Google Drive folder ID: **`14z50C-o27hUrWWDrOVCGqzc9sPtkv_dB`**

Это папка для синхронизации чатов/заметок между компьютерами. Все файлы сохраняются сюда.

## Workflow

### Step 0: Check Auth

```bash
python "$SKILL_DIR/../google-workspace/scripts/setup.py" --check
```

Если `NOT_AUTHENTICATED` — сообщи пользователю, что нужна настройка Google OAuth, и направь к скиллу `google-workspace`.

### Step 1: Prepare Content

1. Возьми контент, который пользователь хочет сохранить
2. Отформатируй как Markdown:
   - Заголовок H1 с темой
   - Дата и источник
   - Основной контент
   - Подпись (создано Hermes Agent, дата)

### Step 2: Propose Filename — ASK USER

**Критично:** НЕ сохраняй файл сразу. Предложи название и спроси подтверждения.

Правила для названия:
- Нижний регистр, дефисы вместо пробелов
- Префикс даты: `YYYY-MM-DD-`
- Описательное название: `claude-system-prompt-analysis`, `session-notes`, `project-ideas`
- Расширение `.md`

Пример: `2026-07-15-claude-fable-5-system-prompt-analysis.md`

Спроси пользователя текстом (НЕ через clarify — не работает в GUI):
> «Сохраняю в Google Drive как `2026-07-15-название.md`. Ок? Или другое название?»

### Step 3: Save File

После подтверждения от пользователя:

```bash
GAPI="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_api.py"

# 1. Создать временный .md файл локально (UTF-8 with BOM)
# 2. Загрузить в Google Drive
$GAPI drive upload /tmp/filename.md --name "filename.md" --parent 14z50C-o27hUrWWDrOVCGqzc9sPtkv_dB
```

### Step 4: Confirm

Сообщи пользователю результат: ссылку на файл или ошибку.

## Google Drive Setup (одноразово)

Если Google Drive не настроен:

1. Google Cloud Console → создать OAuth 2.0 Client ID (Desktop app)
2. Включить API: Google Drive API
3. Скачать `client_secret_*.json`
4. Запустить настройку через `google-workspace` скилл

Детальная инструкция: загрузи скилл `google-workspace` и следуй шагам.

При проблемах с OAuth (запрос USB-ключа, Advanced Protection) — см. `references/google-oauth-troubleshooting.md`.

## Common Pitfalls

1. **Скилл `clarify` НЕ работает** у этого пользователя (Yuri) в desktop GUI — всегда спрашивай обычным текстом
2. **Все .md файлы должны быть UTF-8 with BOM** — маркдаун-ридер Юрия требует BOM, иначе mojibake (Windows-1251 декодирование)
3. **Не загружай без подтверждения названия** — пользователь хочет контролировать имена файлов
4. **Файл блокирован?** — если PermissionError при записи, подожди 3 секунды и попробуй снова (файл может быть открыт в ридере)
5. **Google OAuth может запросить USB-ключ безопасности** — если у пользователя включена Advanced Protection Program (APP), OAuth-авторизация потребует физический ключ (Titan/Feitan). Без ключа — тупик. Подробнее: `references/google-oauth-troubleshooting.md`
6. **После `hermes tools enable vision` нужен `/reset`** — tool changes не применяются mid-session. Даже после /reset инструмент может не появиться (наблюдалось: `vision` enabled в `hermes tools list`, но `vision_analyze` absent в сессии)

## Verification Checklist

- [ ] Google Drive авторизован (`--check` passed)
- [ ] Название файла подтверждено пользователем
- [ ] Файл сохранён с UTF-8 BOM
- [ ] Загружен в папку `14z50C-o27hUrWWDrOVCGqzc9sPtkv_dB`
- [ ] Пользователю показан результат (webViewLink или ошибка)