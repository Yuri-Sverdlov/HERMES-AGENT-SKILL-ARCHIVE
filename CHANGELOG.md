# CHANGELOG — HERMES-AGENT-SKILL-ARCHIVE

Журнал изменений архива скиллов. Пишется человеческим языком, чтобы перед
push в GitHub не гадать, что переписано, переименовано или добавлено.

**Правило синхронизации (с 2026-10-29):** единственная правда — этот репозиторий.
Он подключён к Hermes на каждом ПК через `skills.create_dir`, скиллы создаются и
правятся прямо в нём; синхронизация — `git pull` / `git push`. См. `SYNC-LOGIC.md`.

---

## 2026-11-09 — ПК1: репозиторий переехал с диска E: на G: + Word-версии руководств синхронизируются

Переезд:
- Репозиторий лежал в `E:\_MY-PROGRAMMING\HERMES-AGENT-SKILL-ARCHIVE`, переехал в
  `G:\_MY-PROGRAMMING_1\HERMES-AGENT-SKILL-ARCHIVE` (рядом с остальными проектами на G:).
- Копия сделана robocopy, проверена по числу файлов и байт: 648 файлов, 10,6 МБ, расхождений нет;
  `git fsck` и `git status` в новом месте чистые, HEAD совпадает с `origin/main`.
- `skills.create_dir` в `config.yaml` переключён на новый путь; старый путь вычищен из всех
  документов репозитория (README, SYNC-LOGIC, ИНСТРУКЦИЯ, ОТЛОЖЕННЫЕ-ВОПРОСЫ, CHANGELOG) и из скилла
  `hermes-skills-cross-pc-sync`.

Обновлены:
- `.gitignore` — правило: Word-версии руководств (`<ИМЯ>-GUIDE.docx`, папка `guides/`) синхронизируются
  между ПК, остальные `.docx`/`.pdf`/`.zip` остаются личными артефактами; служебные замки Word (`~$*`)
  игнорируются.
- `SKILLS-GUIDE.md` + `SKILLS-GUIDE.docx` — полный гайд по скиллам Hermes (14 разделов).

---

## 2026-11-03 — ПК1: скиллы из чатов «Озвучка книг + скилы на GitHub» стали переносимыми

Добавлены:
- `productivity/pdf-broken-text-layer-repair` — починка битого текстового слоя PDF без OCR
  (сопоставление контуров глифов с оригинальным шрифтом, перезапись `/ToUnicode`).
  Скрипты: `fix_tounicode.py`, `score_text_layer.py`.
- `productivity/project-knowledge-guides` — оформление уроков проекта в гиды для человека.

Обновлены:
- `book-translate-and-voice` — рабочие скрипты конвейера перенесены внутрь скилла
  (`run_ocr`, `clean_ocr`, `clean_pdf`, `translate`, `repair`, `synth_book`); раньше они лежали
  только в рабочей папке одного ПК. Пути — через `$BOOK_WORK_DIR` / `$BOOK_OUT_DIR`,
  ключ OpenRouter — из окружения или `.env` Hermes. Проверено: чанки на эталонных книгах
  совпадают байт-в-байт, починка PDF воспроизводит 6056 глифов / 86,4 %.
- `hermes-skills-cross-pc-sync` — смешанная схема размещения скиллов, порядок коммитов.

---

## 2026-10-29 — ПК1: репо становится живой папкой скиллов, +18 личных скиллов

**Контекст:** репозиторий переведён в приватный; клон на всех ПК по пути
`G:\_MY-PROGRAMMING_1\HERMES-AGENT-SKILL-ARCHIVE`; Hermes подключается к нему через
`skills.create_dir` вместо ручного копирования (все 4 старые копии архива на ПК1
оказались старее живых скиллов).

Структура: `skills/<имя>/` → `skills/<категория>/<имя>/` (как в Hermes).

Удалены:
- `Чат WhatsApp … .txt/.zip`, `YouTube_ссылки_….docx`, `app.py` — личные
  артефакты, не скиллы (в истории первых коммитов остаются).
- `robocopy-migration-skill.md` — старая отдельная копия, есть скилл `robocopy-migration`.
- `computer-use` — встроенный скилл Hermes, обновляется самим Hermes.

Обновлены (находки ПК1 из старых `multithread-downloader` / `video-extraction`,
сделанные после миграции 17.09, влиты в новые имена):
- `video-source-resolve` — раздел HDrezka/rezka.ag (Anubis PoW, voidboost CDN),
  скрипты `rezka_fetch.py` / `rezka_parse.py`, полный разбор в
  `references/rezka-anubis.md`.
- `video-fetch` — aria2c через winget/PATH или `.hermes\aria2c.exe`, yt-dlp +
  aria2c downloader, докачка `.aria2`; грабли: иллюзия размера sparse-файла aria2c,
  размер в выводе yt-dlp ≠ итоговый файл, общий лимит на IP при параллельных
  загрузках, проверка места на диске, YouTube через `player_client=android`.
- `video-*` — жёсткие пути `C:/Users/Yuri/AppData/Local/hermes/skills/...` заменены
  на `${HERMES_SKILL_DIR}` (иначе ломаются при подключении из репо).
- `overview-projects-on-computer` — `projects.json` с ПК1 (top_folder
  `G:/_MY-PROGRAMMING_1`; версия с ПК2 `G:/AI` — в истории git).

Добавлены (личные скиллы ПК1, которых не было ни в одном архиве):
- `autonomous-ai-agents/`: `hermes-skills-cross-pc-sync`, `personal-hermes-guide`
- `email/`: `mail-aliexpress`, `mail-export`, `mail-inbox`, `mail-translate`
- `idea-workflow/`: `idea-superpowers-suite`, `idea-to-design-doc`,
  `idea-to-implementation-doc`, `idea-to-ui-design-brief`
- `productivity/`: `book-translate-and-voice`, `cost-model-today`,
  `image-ocr-to-docx`, `ocr-and-documents`, `save-to-google-drive`
- `software-development/`: `coder-terminal-workflow`, `plan`, `robocopy-migration`

**Итог:** 25 скиллов.

---

## 2026-09-17 — первичная миграция в отдельный репозиторий + синхронизация

**Контекст:** папка вынесена из родительского дерева `HERMES-AGENT` (пушилось в
старый репо `HERMES-AGENT`) в самостоятельную папку `HERMES-AGENT-SKILL-ARCHIVE`
под отдельный публичный репозиторий, чтобы обмениваться скиллами между
компьютером 1, компьютером 2 и ноутбуком через GitHub.

**Миграция:** содержимое `F:\_MY_PROGRAMMING\HERMES-AGENT\SOURCES-ARCHIVE`
(26 файлов, 6.0 MB) скопировано в `F:\_MY_PROGRAMMING\HERMES-AGENT-SKILL-ARCHIVE`
(robocopy, верифицировано 26/26 файлов, match=TRUE). Источник не тронут.

**Сверка скиллов с директорией Hermes (правда):**

Не изменились (архив уже актуален, байт-в-байт идентичны Hermes):
- `computer-use`
- `overview-projects-on-computer`
- `screenshot-to-docx`
- `whatsapp-yt-links`

Удалены как устаревшие — их функции переехали в новый видео-пайплайн Hermes:
- `multithread-downloader`  → влилось в `video-fetch`
- `playlist-downloader`     → стало `video-batch-runner`
- `video-extraction`        → стало `video-source-resolve`
- `video-url-extractor`     → стало `video-source-resolve`

Добавлены (свежие версии из Hermes, в архиве отсутствовали):
- `video-fetch`           — быстрая загрузка одного видео, диагностика 403/throttle
- `video-batch-runner`    — список N видео: манифест, resume, verify
- `video-source-resolve`  — резолв страницы/агрегатора в реальный источник
- `video-compression`     — сжатие локального видео (пресеты A=~5×, B=~10×);
                            закреплён в кураторе (`hermes curator pin`)

**Итог:** 8 скиллов в архиве, все — самые свежие версии из директории Hermes.

---

<!--
ШАБЛОН для следующей записи (копировать наверх, под заголовок):

## ГГГГ-ММ-ДД — краткое описание

Добавлены:  <имя> — <зачем>
Обновлены:  <имя> — <что изменилось>
Переименованы: <старое> → <новое> — <почему>
Удалены:    <имя> — <причина / куда переехало>
-->
