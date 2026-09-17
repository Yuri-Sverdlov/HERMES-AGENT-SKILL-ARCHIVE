# Архив инструментов Hermes Agent — инструкция по переносу

Дата сборки: 24 августа 2026 · обновлено 17 сентября 2026

> **Как устроен и как поддерживается этот архив** (синхронизация с Hermes,
> правила обновления, назначение CHANGELOG) — см. отдельный файл
> [`SYNC-LOGIC.md`](SYNC-LOGIC.md). Журнал изменений человеческим языком —
> [`CHANGELOG.md`](CHANGELOG.md). Этот README — инструкция по **установке** на
> новом устройстве.

## Что в архиве

8 скиллов и 3 Python-скрипта:

| Задача | Скиллы | Скрипты |
|---|---|---|
| Управление GUI-приложениями в фоне | `computer-use` | — |
| Скачивание одного видео (быстро, диагностика 403/throttle) | `video-fetch` | `scripts/smart_dl.py` |
| Резолв страницы/агрегатора в реальный источник видео | `video-source-resolve` | — |
| Список из N видео: манифест, resume, verify | `video-batch-runner` | — |
| Сжатие локального видео (пресеты A≈5×, B≈10×) | `video-compression` | — |
| Распознавание скриншотов в Word | `screenshot-to-docx` | `scripts/create_docx_template.py` |
| YouTube-ссылки из WhatsApp в Word | `whatsapp-yt-links` | — |
| Инвентаризация проектов на компьютере | `overview-projects-on-computer` | — |

> Устаревшие скиллы `playlist-downloader`, `video-url-extractor`,
> `video-extraction`, `multithread-downloader` удалены — их функции переехали в
> `video-fetch` / `video-batch-runner` / `video-source-resolve` (см. CHANGELOG).

---

## Установка на новом компьютере

### Шаг 1 — скопировать скиллы

Все папки из `skills/` скопируй в `C:\Users\<твой_пользователь>\AppData\Local\hermes\skills\`:

```
skills\playlist-downloader\         → %LOCALAPPDATA%\hermes\skills\media\playlist-downloader\
skills\computer-use\              → %LOCALAPPDATA%\hermes\skills\autonomous-ai-agents\computer-use\
skills\video-url-extractor\      → %LOCALAPPDATA%\hermes\skills\media\video-url-extractor\
skills\video-extraction\         → %LOCALAPPDATA%\hermes\skills\media\video-extraction\
skills\multithread-downloader\    → %LOCALAPPDATA%\hermes\skills\media\multithread-downloader\
skills\screenshot-to-docx\        → %LOCALAPPDATA%\hermes\skills\productivity\screenshot-to-docx\
skills\whatsapp-yt-links\         → %LOCALAPPDATA%\hermes\skills\productivity\whatsapp-yt-links\
```

ИЛИ просто скопируй `skills\` → `%LOCALAPPDATA%\hermes\skills\` с сохранением структуры.

Важно: Hermes должен быть перезапущен после копирования (нажми `/new` в чате).

### Шаг 2 — скопировать скрипты

```
scripts\smart_dl.py              → C:\Users\<пользователь>\.hermes\smart_dl.py
scripts\aria2c.exe               → C:\Users\<пользователь>\.hermes\aria2c.exe
scripts\create_docx_template.py  → C:\Users\<пользователь>\.hermes\create_docx_template.py
```

### Шаг 3 — проверить Python и зависимости

Должен быть установлен Python 3.11+ (проверить: `python --version`).

Установить пакеты:
```
pip install python-docx pillow pytesseract
```

### Шаг 4 — установить Tesseract OCR (только для screenshot-to-docx)

1. Скачай: https://github.com/UB-Mannheim/tesseract/wiki
2. Установи в `C:\Program Files\Tesseract-OCR\`
3. Выбери Russian language data при установке (или потом: `tesseract --list-langs` должен показать `rus`)

### Шаг 5 — установить cua-driver (только для computer-use)

Computer Use позволяет агенту управлять GUI-приложениями в фоне (кликать, печатать, скроллить). Требует cua-driver:

1. Открой PowerShell **от имени администратора**
2. Выполни:
   ```
   irm https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.ps1 | iex
   ```
3. Включи инструмент в Hermes:
   ```
   hermes tools enable computer_use
   ```
4. Проверь:
   ```
   hermes computer-use doctor
   ```
   Должен показать: ✅ binary_version, ✅ platform_supported, ✅ screen_capture_capability

### Шаг 6 — опционально: yt-dlp (для VK Video)

```
pip install yt-dlp
```

---

## Как использовать

### Управлять любым GUI-приложением в фоне

Скажи агенту:
> Открой VideoPaw и нажми кнопку Download

Агент загрузит `computer-use`, захватит скриншот окна (в фоне, не трогая твою мышь), найдёт кнопку по номеру и кликнет.

**Основные команды:**
- `capture(app="Chrome")` — скриншот конкретного приложения
- `click(element=7)` — клик по элементу с номером
- `type(text="...")` — ввод текста
- `scroll(direction="down", amount=3)` — прокрутка

Подробнее: `skill_view(name='computer-use')` после установки.

### Скачать плейлист (несколько видео)

Скажи агенту:
> Скачай эти видео:
> https://eporner.com/...
> https://vkvideo.ru/...

Агент загрузит `playlist-downloader`, для каждого URL извлечёт прямой видео-адрес и запустит параллельную закачку через yt-dlp (по 6 потоков на видео, 3-4 видео одновременно). Прогресс отображается в реальном времени.

### Скачать одно видео

Скажи агенту:
> Скачай видео https://yandex.ru/video/preview/...

Агент загрузит `video-url-extractor`, найдёт прямой URL, затем применит `multithread-downloader` → `smart_dl.py` (aria2c если установлен, иначе Python-докачка).

**Вручную через консоль:**
```
python smart_dl.py "<URL>" "C:\путь\файл.mp4" 6
```
При обрыве — просто повтори ту же команду. Докачка автоматическая.

### Конвертировать скриншот в Word

Скажи агенту:
> Распознай этот скриншот и оформи в Word

Агент загрузит `screenshot-to-docx`, разделит изображение, распознает Tesseract'ом, создаст `.docx`.

### YouTube-ссылки из WhatsApp

Скажи агенту:
> Достань YouTube-ссылки из этого чата с 5 по 22 августа

Агент загрузит `whatsapp-yt-links`, распарсит `.txt` экспорт, запросит названия через oEmbed API и создаст таблицу в Word.

---

## Требования к окружению

| Компонент | Минимальная версия | Для чего |
|---|---|---|
| Windows | 10/11 | — |
| Python | 3.11+ | smart_dl.py |
| cua-driver | 0.21.0+ | computer-use (управление GUI) |
| python-docx | любой | Word-документы |
| pillow | любой | Обработка изображений |
| pytesseract | 0.3+ | Распознавание текста |
| Tesseract OCR | 5.4.0+ | Движок распознавания (с языком rus) |
| yt-dlp | любой | Скачивание с VK Video |
| Hermes Agent | последняя | Запуск скиллов |

---

## Файлы в архиве

```
SOURCES-ARCHIVE/
├── README.md
├── requirements.txt
├── scripts/
│   ├── smart_dl.py                    # Универсальный загрузчик (aria2c + Python, докачка)
│   ├── aria2c.exe                     # aria2c 1.37.0 (6-32 соединений, динамические куски)
│   ├── aria2c-COPYING.txt             # GPL v2 license for aria2c
│   └── create_docx_template.py        # Шаблон создания Word-документа (TNR 12pt, А4)
└── skills/
    ├── playlist-downloader/
    │   └── SKILL.md                   # Пакетная закачка N видео параллельно
    ├── computer-use/
    │   └── SKILL.md                   # Управление GUI-приложениями в фоне (cua-driver)
    ├── video-url-extractor/
    │   └── SKILL.md                   # Извлечение прямого URL видео через browser
    ├── video-extraction/
    │   ├── SKILL.md                   # Извлечение URL видео (fallback, без GUI)
    │   └── references/
    │       └── yandex-pbembed-chain.md  # Цепочка Yandex → pbembed.me/strip2.in
    ├── multithread-downloader/
    │   ├── SKILL.md                   # Закачка в 4-8 потоков через HTTP Range
    │   └── references/
    │       └── script-usage.md
    ├── screenshot-to-docx/
    │   ├── SKILL.md                   # Распознавание скриншотов → Word
    │   └── references/
    │       ├── browser-console-url-extraction.md  # Альтернативный способ извлечения URL
    │       ├── whatsapp-chat-export.md            # Инструкция по экспорту чата WhatsApp
    │       └── youtube-oembed-api.md              # API YouTube для названий видео
    └── whatsapp-yt-links/
        └── SKILL.md                   # WhatsApp .txt → таблица YouTube-ссылок в Word
```

---

## Примечания

- **computer-use** работает в фоне — не отбирает мышь/клавиатуру у пользователя. Для установки нужен PowerShell от админа: `irm https://.../install.ps1 | iex`
- **VK Video** (vkvideo.ru) не поддерживает HTTP Range — используй `yt-dlp -N 6` вместо `smart_dl.py`
- **pbembed.me**, **strip2.in**, **noodlemagazine.net**, **nmcorp.video** — разные CDN. `pvvstream.pro` (Cloudflare) отлично работает с многопоточностью (~90 MiB/s). `fp.spac.me` (strip2) — медленный (~280 KB/s), многопоточность не поможет.
- `video-extraction` — запасной скилл: извлечение URL через browser DOM, если GUI-загрузчики не работают. Содержит цепочки для всех хостов.
- `smart_dl.py` на Windows: всегда используй прямые пути (`C:/Users/…`), не `$HOME/` — двойной escape ломает путь
- **screenshot-to-docx** для WhatsApp-скриншотов: всегда лучше экспортировать чат как `.txt` (100% точность), чем распознавать скриншот (35-50%)
- Все скиллы спроектированы для работы через Hermes Agent — агент сам вызывает нужные инструменты (browser, terminal, python)