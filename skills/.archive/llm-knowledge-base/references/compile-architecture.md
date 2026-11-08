# compile.py — архитектура и предохранители

## Роль

`compile.py` — регенератор слоя `pages/` из `chats/`. Не генерирует тело (полуручной контур, TASK-018), а только пересобирает фронтматтер + pinned-блоки + валидирует источники.

```
chats/ (сырьё)  ── compile.py (регенерация хэша/статуса) ──> pages/ (компилируемый слой)
```

## Система предохранителей (layered defence)

Три уровня защиты от повреждения данных:

### Уровень 1 — `cmd_all` (обход)

Перед вызовом `regenerate` для каждого `.md`-файла в `pages/<domain>/{projects,themes}/`:

1. **`~$*`** — lock-файлы Office (тихий continue)
2. **`.hidden`** — файлы на точку (тихий continue)
3. **Нет валидного фронтматтера** — `WARNING` в stderr, continue
4. **Пустой `sources:`** — `WARNING` в stderr, continue

### Уровень 2 — `regenerate` (ядро)

После успешного обхода, в теле `regenerate`:

- **Guard 1a:** `sources: []` → `ERROR` в stderr, возврат `None` (файл НЕ пишется)
- **Guard 2a:** `new_hash == sha256("")` → `ERROR` в stderr, возврат `None`
  - *Практически:* `_compute_all_hashes([])` возвращает `sha256(b"").hexdigest()` (хэш пустого списка). При непустом `sources` хэш никогда не бывает пустым, т.к. `h.update(src)` вызывается ДО резолва чата. Guard 2a — defence-in-depth.

### Уровень 3 — exit code

- `cmd_page`: если `regenerate` вернул `None` → `sys.exit(1)`
- `cmd_all`: считает `total_errors` (по None) + `total_warnings` (по WARNING из хэширования); любой ненулевой → `sys.exit(1)`

## Хэширование

`_compute_all_hashes(sources, chats_dir)` → `(hexdigest, warning_count)`:

1. Для каждого источника (строка `machine:source:session_id`):
   - **Всегда** `h.update((src + '\n').encode('utf-8'))` — до проверки существования чата
   - Если чат не найден → `WARNING` в stderr, warning_count++
   - Если чат найден → `h.update(chat_body_hash)` — SHA256 тела чата (без фронтматтера)
2. Возврат: финальный hexdigest + количество WARNING-ов

Этот дизайн гарантирует, что sources_hash меняется при:
- Изменении любого чата-источника
- Добавлении/удалении источника
- Рефакторинге тела чатов

ПРИ ЭТОМ sources_hash **НЕ меняется**, если:
- Поменялся pinned-блок (он внутри страницы, не в чате-источнике)
- Сменилось авторское тело страницы

## Пропуск по хэшу (`--changed`)

`cmd_all` с флагом `--changed`:
1. Парсит существующую страницу
2. Если `sources` непуст и `current_hash == stored_hash` → `SKIP` (файл не переписан)
3. Иначе → `regenerate`

Пропуск НЕ срабатывает если `sources` пуст (catch: Guard 1a).

## Парсинг страницы

`parse_page(path)` → `{frontmatter, body, pinned, sources}`:

- `pinned` = dict `{sha256[:16]: full_block_text}` — извлекается regex `PINNED_RE`
- Pinned-блоки привязываются к разделу по якорю `section="..."` или содержимому
- Потеря pinned-блока → `ERROR` в stderr, файл НЕ пишется

## Линтинг страниц

`lint_frontmatter.py` при запуске без `--selftest` проверяет:

- `chats/*/*.md` — стандартная валидация полей (title, source, session_id, domain)
- `pages/<domain>/{projects,themes}/*.md` — проверка:
  - `sources` отсутствует/пуст → `ERROR`
  - `sources_hash == sha256("")` → `ERROR`
  - Нет фронтматтера → `WARNING` (не страница)
  - Пропуск `~$*` и `.hidden` файлов

## Селфтесты

`compile.py --selftest` (20 тестов) + `lint_frontmatter.py --selftest` (8 тестов):

- Все тесты во временном каталоге (`tempfile.TemporaryDirectory`)
- Каждый тест: `total += 1` → проверка → `passed += 1` + `print("OK | ...")` / `print("FAIL | ...")`
- Финал: `N/N passed`, exit 0 если все зелёные
- Для тестирования WARNING/ERROR в stderr: захват через `io.StringIO` + подмена `sys.stderr`

Особые тесты из TASK-021:
- **Тест 10:** `~$test.md` читается без ошибки (обход не ломается)
- **Тест 11:** страница с `sources: []` → regenerate возвращает None
- **Тест 12:** `_compute_all_hashes([]) == sha256(b"").hexdigest()` (defence-in-depth)