# Project Inventory — Пример из сессии (2026-07-02)

Директории, обработанные за одну сессию: 
- `G:\_My_Programming` (14 items)
- `G:\_My_Programming-2` (9 items)
- `G:\_MY_PROGRAMMING_3` (3 items)
- `G:\_MY_PROGRAMMING_4` (5 items)

## Структура описания проекта

Каждый проект описывался по шаблону:

```
## N. PROJECT-NAME
Описание: <цель, стек, ключевые файлы, 60-70 слов (или подробнее по запросу)>
Статус: <завершён/в разработке/%оценка/примечания>
```

## Уровни детализации

**Обычный** (60–70 слов): цель, стек, ключевая особенность.

```
Описание: Веб-приложение для тренировки таблицы умножения и деления.
Бэкенд: FastAPI + SQLite. Фронтенд: чистый HTML/JS, панель родителя.
E2E-тесты на Playwright. Стек: Python, FastAPI, Pydantic, Uvicorn.
```

**Подробный** (по запросу «подробнее» / если интересные инструменты):
блоки с bullet-листами файлов, архитектуры, решённых проблем.

```
Инструменты и пайплайн:
• orchestrator.py — пошаговая генерация через Grok API (черновик ~2500 слов).
  Поддержка двух моделей: grok-3 (основная) и grok-3-mini (быстрая).
• to_docx.py — конвертер в Word. Удаляет мета-комментарии Grok,
  форматирует заголовки, даёт латинские имена файлам.
• check_models.py — диагностика: проверяет API-ключ и список моделей.
• prompts/ — папка с системным промптом (мир, стиль, персонажи).
• output/ — пошаговые файлы: structure → draft → polish → .docx.
```

## Типы проектов

| Тип | Как определять | Пример |
|-----|---------------|--------|
| **Авторский проект** | Есть README, AGENTS.md, CONTEXT.md, git-репо, исходники Python/JS | COMFYUI-API-CHAT, VIDEO-CLAUDE-CHAT |
| **Сторонний клон** | Официальный README со значками бейджами, ссылками на upstream | ComfyUI, n8n-workflow-builder |
| **Пустая папка** | Нет файлов, только .git | test_antigravity, WAN2_5-UNCENSORED-ALL-IN-ONE |
| **Системная директория** | Инструмент для установки/запуска AI-софта | PINOKIO |
| **Архив/заметки** | Только .md/.docx файлы, нет кода | COMFYUI-SOURCES, notуpad_N8N_Notion |
| **Утилита (завершена)** | Одноцелевой скрипт, нет продолжения | CUT-PAGE |

## Уровни статусов

- **Завершён** — задача выполнена, проект закрыт
- **Завершён в основной части (~X%)** — базовый функционал есть, мелкие недоработки
- **В активной разработке (~X%)** — прямо сейчас ведётся работа
- **В разработке (~X%)** — начат, есть структура/ТЗ, но не доделан
- **Черновик** — только начало, скрипты написаны, не тестировались
- **Не начат** — пустая папка или заготовка
- **Сторонний инструмент / Сторонний клон** — не авторский код
- **Архив / Не проект** — вспомогательные файлы

## Вывод .docx

```python
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

projects = [...]

doc = Document()

# Title
title = doc.add_heading('DIR NAME — Обзор проектов', 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Projects loop
for p in projects:
    doc.add_heading(p["name"], level=2)
    
    desc = doc.add_paragraph()
    desc.add_run("Описание: ").bold = True
    desc.add_run(p["desc"])
    
    status = doc.add_paragraph()
    status.add_run("Статус: ").bold = True
    status.runs[0].font.color.rgb = RGBColor(0x1F, 0x5C, 0x99)
    status.add_run(p["status"]).font.color.rgb = RGBColor(0x1F, 0x5C, 0x99)
    
    doc.add_paragraph()

doc.save(r"G:\PATH\MY-PROGRAMMING-N-SUMMERY.docx")
```

## Примечания из реальных сессий

- **MY-PROGRAMMING-1** (14 items): хаб HERMES-AGENT + инструменты. Папка «!! Сортироват !!» пропущена.
- **MY-PROGRAMMING-2** (9 items): фокус на ComfyUI и CivitAI-скрипты. Есть пустая WAN2_5.
- **MY-PROGRAMMING-3** (3 items): TTS-проекты на Qwen3 (Base + Instruct). Тесная связь проектов через junction-venv.
- **MY-PROGRAMMING-4** (5 items): писательские системы — sci-fi (Grok), KDP low-content (reportlab), DOE-архитектура (Flask + многоагентка). Пользователь запросил максимальную детализацию с перечислением файлов.