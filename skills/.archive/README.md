# .archive — отложенные скиллы (в git, но не в работе)

Здесь лежат личные скиллы Юрия, которые curator вычистил из активного каталога по таймеру
(14 дней без использования → `stale`, 30 дней → архив). Файлы **не удалены** — они просто
выключены.

## Зачем они здесь, а не в локальном архиве профиля

Локальный архив (`~/.hermes/skills/.archive/`) на других ПК не виден: он не в git.
А этот каталог — часть репозитория скиллов, поэтому после `git pull` он есть на ПК1, ПК2 и
ноутбуке. При этом сканер скиллов Hermes **пропускает папки `.archive`** (как `.git`, `.hub`,
`.locks`), поэтому они не попадают ни в перечень системного промпта, ни в `skills_list`,
ни в `skill_view` — то есть не расходуют токены и не путают выбор.

Итог: знание синхронизируется, каталог не разбухает.

## Как вернуть скилл в работу

Категория для возврата указана для каждого скилла в `_MANIFEST.json`.

```bash
cd /g/_MY-PROGRAMMING_1/HERMES-AGENT-SKILL-ARCHIVE
git mv skills/.archive/<имя> skills/<категория>/<имя>     # напр. skills/media/<имя>
git commit -m "<имя>: возвращён в работу"
git push
```

После переноса скилл сразу виден Hermes (он читает скиллы прямо из этого репозитория) — и,
чтобы таймер не убрал его снова, пометь его `pinned` (запись в `~/.hermes/skills/.usage.json`)
или поставь `curator.enabled: false`.

Правило гигиены: вернул скилл — удали его копию отсюда, двух копий быть не должно.

## `_MANIFEST.json`

По каждому скиллу: имя, кто создал (`created_by`), дата создания, дата архивации, сколько раз
использовался (`use_count`), сколько файлов, размер, рекомендуемая категория.

## Чего здесь нет

Встроенных и хаб-скиллов — они не наши, их возвращают из локального архива профиля
(`hermes curator restore <имя>`) или ставят командой `hermes skills install <id>`.
Одинаковые имена скиллов в этом архиве и в локальном архиве профиля — норма: здесь рабочая
копия для синхронизации, там служебная запись curator'а.

## Что уже ушло из этого архива

**Возвращены в работу** (перенесены в свои категории, помечены `pinned`):
`user-style-yuri`, `email-processing`, `ai-provider-billing-dashboard`, `stt-whisper-gpu-windows`,
`llm-knowledge-base`, `video-dubbing-pipeline`, `nsfw-scene-positioning`.

**Влиты в существующие скиллы как приложения** (см. `references/` у цели):
`hermes-cross-pc-git-sync` и `directory-reconciliation` → `hermes-skills-cross-pc-sync`;
`youtube-download` → `video-fetch`; `project-inventory` → `overview-projects-on-computer`;
`llm-chat-knowledge-base` → `llm-knowledge-base`; `hermes-model-switching` и
`hermes-profiles-and-sessions` → `personal-hermes-guide`.

История переносов — в git: `git log --oneline -- skills/.archive`.
