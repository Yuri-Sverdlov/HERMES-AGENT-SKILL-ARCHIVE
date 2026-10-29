---
name: cost-model-today
description: "Мониторинг дневных трат API в Hermes Agent: Today's cost в /usage, cron-предупреждения, bat-файл для быстрой проверки"
version: 1.0.0
author: Yuri
---

# COST-MODEL-TODAY

Проект для отслеживания дневных трат API Hermes Agent с автоматическим предупреждением о превышении бюджета.

## Где лежит

`G:\_My_Programming\COST-MODEL-TODAY\`

Репозиторий: https://github.com/Yuri-Sverdlov/COST-MODEL-TODAY

## Что сделано

1. **Today's cost в `/usage`** — патч cli.py выводит блок с сегодняшними тратами, процентом от бюджета и визуальным индикатором
2. **Cron-мониторинг** — задача `budget-monitor` раз в 30 мин проверяет траты через `budget_monitor.py` (no-agent режим). При превышении 75% от $2.00 доставляет предупреждение в чат
3. **Bat-файл** — `show_budget.bat` (двойной клик → окно с отчётом). Внутри использует абсолютный путь, работает с рабочего стола
4. **GUIDE.md** — путеводитель по проекту

## Файлы

- `cost_tracker.py` — ядро: получает траты за Today из SessionDB (SQLite state.db)
- `budget_monitor.py` — cron-скрипт проверки бюджета
- `show_budget_window.py` + `show_budget.bat` — окно с отчётом
- `config.yaml` — настройки (daily_budget, warn_at_percent, check_interval_minutes)
- `install.py` — установщик (патч cli.py + копирование скриптов в ~/.hermes/scripts/ + настройка cron)
- `patches/patch_cli_usage.py` — патч для cli.py

## Важные нюансы

- **Кодировка .md файлов:** UTF-8 with BOM (utf-8-sig). Без BOM ридер пользователя показывает кракозябры
- **Патч cli.py:** вставляет блок today-cost после вывода "Compressions" и перед "Account limits" в `_show_usage()`. При обновлении Hermes может слететь — перезапустить `install.py`
- **Cron задача:** `hermes cron list` — проверить статус. Если не активна — `python install.py`
- **config.yaml** читается при каждом запуске budget_monitor.py, изменения применяются без перезапуска
- Для работы скриптов нужен PYTHONPATH, указывающий на `C:\Users\Yuri\AppData\Local\hermes\hermes-agent`

## Откат

- Патч cli.py: `python patches\patch_cli_usage.py revert`
- Cron: `hermes cron remove budget-monitor`

## Идеи на будущее (из GUIDE.md раздел 7)

- 🪟 Интерактивное окно предупреждения — при превышении бюджета открывается консольное окно, где можно выбрать и переключить модель
- 🎯 Рекомендация модели — агент предлагает дешёвую модель при высоких тратах
- 📊 Недельная статистика
- 🔔 Уведомления в Telegram
- 💾 История трат в отдельную таблицу