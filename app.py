#!/usr/bin/env python3
"""
gui/app.py — Веб-панель пользователя (Gradio).

Запуск:
    python gui/app.py

Откроется в браузере: http://localhost:7860

Документация: specs/web-gui.md
Зависимости: pip install gradio pyyaml

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СТАТУС РАЗРАБОТКИ:

Фаза 1: ✅ Статический layout (завершена)
Фаза 2: ✅ Подключение YAML-конфигов (завершена)
  — Dropdown и чекбоксы реально читают/пишут config/*.yaml
  — Данные загружаются из файлов при старте
  — Изменения сохраняются автоматически

Фаза 3: ✅ Чат — приём вводных (завершена)
  — Кнопка "Отправить": обычный диалог с LLM, сохраняется в чат-файл
  — Кнопка "💾 Вводные": сохраняет текст как есть в input/idea.md
  — Один файл чата на день: YYYY-MM-DD_chat.md
  — ⭐ Кнопка "⏹ Стоп" для прерывания запроса (19.03.2026)

Фаза 4: ✅ Запуск пайплайна (завершена)
  — Кнопка "▶ Запустить" подключена к run-pipeline.py
  — Упрощённый pipeline: generate → critique → edit → finalize
  — Показывается статус выполнения в реальном времени
  — Кнопки "Пауза" и "Стоп" базовые

Фаза 4.5: 🔄 Выбор моделей через пагинацию (19.03.2026)
  — ⭐ config/user-config.yaml — API ключи пользователя
  — ⭐ gui/utils/provider_manager.py — загрузка от API с кэшированием
  — ⭐ Пагинация: 10 моделей на страницу + кнопки [1] [2] [3]...
  — Настраиваемое количество моделей на страницу (ui.models_per_page)

Фаза 5: 📋 Контрольные точки в GUI (в планах, опционально)
Фаза 6: 📋 Загрузка документов (в планах)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 ИСТОРИЯ ИЗМЕНЕНИЙ:

19.03.2026:
- Добавлена кнопка "Стоп" в чат (chat_runner.py)
- Реализована система выбора провайдеров через user-config.yaml
- Добавлена пагинация для списка моделей
- Файлы: user-config.yaml, models-cache.yaml исключены из git

TODO:
- [ ] ПРОВЕРИТЬ работу пагинации (кликабельность dropdown)
- [ ] Добавить тесты Playwright для автоматической проверки
- [ ] Реализовать fallback на статический список при недоступности API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gradio as gr
from gui.utils.config_manager import config_manager
from gui.utils.pipeline_runner import PipelineRunner
from gui.utils.log_watcher import LogWatcher
from gui.utils.chat_runner import ChatRunner
from gui.utils.provider_manager import provider_manager

# ─────────────────────────────────────────────────────────────
# Глобальные объекты для работы с пайплайном и чатом
# ─────────────────────────────────────────────────────────────
pipeline_runner = PipelineRunner()
chat_runner = ChatRunner()
log_watcher: LogWatcher | None = None
pipeline_status: str = "Готов к запуску"
pipeline_output: str = ""
chat_status: str = "Готов"

# ─────────────────────────────────────────────────────────────
# Загрузка данных из конфигов при старте (Фаза 2)
# ─────────────────────────────────────────────────────────────

# Проекты
PLACEHOLDER_PROJECTS = ["— выберите проект —"] + config_manager.get_projects()

# Модули
PLACEHOLDER_MODULES = ["fiction", "screenplay", "posts", "nonfiction (заглушка)"]

# Модели: только OpenRouter и Ollama
AVAILABLE_PROVIDERS = ["openrouter", "ollama"]

# Отображаемые имена провайдеров
PROVIDER_DISPLAY_NAMES = {
    "openrouter": "OpenRouter",
    "ollama": "Ollama (локальный)",
}

# Список отображаемых имён для radio (только существующие провайдеры)
PROVIDER_RADIO_CHOICES = [
    PROVIDER_DISPLAY_NAMES.get(p, p) for p in AVAILABLE_PROVIDERS
]

# Маппинг: отображаемое имя → ключ провайдера
def get_provider_key(display_name: str) -> str:
    for key, display in PROVIDER_DISPLAY_NAMES.items():
        if display == display_name:
            return key
    return display_name  # fallback

# Получаем все доступные модели для dropdown (отображаемые имена)
AVAILABLE_MODELS = config_manager.get_models_for_dropdown()

# Текущий активный проект используется через gr.State внутри build_ui()


def save_chat_to_file(history: list, project_name: str) -> str:
    """
    Сохраняет историю чата в файл.
    Формат: projects/{project_name}/chats/YYYY-MM-DD_chat.md
    Все сообщения за один день добавляются в один файл.
    """
    if not project_name:
        return "[WARN] Проект не выбран - чат не сохранён"
    
    try:
        from datetime import datetime
        
        # Формируем путь к директории чатов проекта
        project_chats_dir = config_manager.projects_dir / project_name / "chats"
        project_chats_dir.mkdir(parents=True, exist_ok=True)
        
        # Формируем имя файла только с датой (один файл на день)
        date_str = datetime.now().strftime("%Y-%m-%d")
        chat_file = project_chats_dir / f"{date_str}_chat.md"
        
        # Берём только последнее сообщение из истории для добавления
        if not history:
            return "[WARN] История чата пуста"
        
        last_entry = history[-1]
        user_msg, assistant_msg = last_entry if len(last_entry) == 2 else (last_entry[0], "")
        
        # Формируем строки для новых сообщений
        new_lines = []
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if user_msg:
            new_lines.append(f"**Пользователь** ({timestamp}):")
            new_lines.append(f"{user_msg}")
            new_lines.append("")
        if assistant_msg:
            new_lines.append(f"**Агент** ({timestamp}):")
            new_lines.append(f"{assistant_msg}")
            new_lines.append("")
            new_lines.append("---")
            new_lines.append("")
        
        new_content = "\n".join(new_lines)
        
        # Если файл существует - дописываем, иначе создаём с заголовком
        if chat_file.exists():
            existing_content = chat_file.read_text(encoding="utf-8")
            content = existing_content.rstrip() + "\n\n" + new_content
        else:
            # Создаём новый файл с заголовком
            header_lines = [
                f"# Лог чата - {project_name}",
                "",
                f"> Дата: {date_str}",
                f"> Проект: {project_name}",
                "",
                "---",
                "",
                new_content
            ]
            content = "\n".join(header_lines)
        
        # Записываем файл
        chat_file.write_text(content, encoding="utf-8")
        
        return f"[OK] Сообщение добавлено в {chat_file.name}"
        
    except Exception as e:
        return f"[ERROR] Ошибка сохранения: {type(e).__name__}"


def save_idea_to_file(message: str, project_name: str) -> str:
    """
    Сохраняет вводные данные пользователя в input/idea.md.
    Сохраняет текст КАК ЕСТЬ, без обработки LLM.
    Формат: projects/{project_name}/input/idea.md
    """
    if not project_name:
        return "[WARN] Проект не выбран - вводные не сохранены"
    
    if not message or not message.strip():
        return "[WARN] Пустое сообщение - нечего сохранять"
    
    try:
        from datetime import datetime
        
        # Формируем путь к директории input проекта
        project_input_dir = config_manager.projects_dir / project_name / "input"
        project_input_dir.mkdir(parents=True, exist_ok=True)
        
        idea_file = project_input_dir / "idea.md"
        
        # Формируем новую секцию с датой
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_section = f"""## Добавлено: {timestamp}

{message.strip()}

---
"""
        
        # Если файл существует - дописываем, иначе создаем с заголовком
        if idea_file.exists():
            existing_content = idea_file.read_text(encoding="utf-8")
            content = existing_content.rstrip() + "\n\n" + new_section
        else:
            content = f"""# Вводные для проекта: {project_name}

{new_section}"""
        
        idea_file.write_text(content, encoding="utf-8")
        return f"[OK] Вводные сохранены в {project_name}/input/idea.md"
        
    except Exception as e:
        return f"[ERROR] Не удалось сохранить вводные: {str(e)}"


# Роли
ROLES = [
    ("Оркестратор", "orchestrator"),
    ("Генератор",   "generator"),
    ("Критик",      "critic"),
    ("Писатель",    "writer"),
    ("Редактор",    "editor"),
    ("Корректор",   "proofreader"),
]

# Контрольные точки
CHECKPOINT_LABELS = [
    ("structure_generation",  "После генерации вариантов"),
    ("critic_evaluation",     "После выбора критиком"),
    ("writing",               "После написания"),
    ("style_editing",         "После редактуры"),
    ("proofreading",          "После корректуры"),
    ("finalization",          "После финализации"),
]

# Загружаем состояние чекпоинтов из config
def get_enabled_checkpoints() -> list[str]:
    enabled = []
    for key, label in CHECKPOINT_LABELS:
        if config_manager.get_checkpoint_enabled(key):
            enabled.append(label)
    return enabled

ENABLED_CHECKPOINTS = get_enabled_checkpoints()

# Базы знаний
WORKSPACE_LABELS = config_manager.get_workspace_labels()  # [(label, id), ...]
ENABLED_WORKSPACES = config_manager.get_enabled_workspaces()  # [id, ...]

# Получаем все доступные модели для dropdown
AVAILABLE_MODELS = config_manager.get_models_for_dropdown()

# ─────────────────────────────────────────────────────────────
# Стартовое сообщение в чате
# ─────────────────────────────────────────────────────────────

PLACEHOLDER_CHAT_MSG = (
    "👋 Добро пожаловать в систему генерации литературного контента!\n\n"
    "**Команды чата:**\n"
    "• `/find <запрос>` — поиск в базе знаний (пример: `/find диалог шторм`)\n"
    "• `/help` — показать все команды\n\n"
    "Опишите вашу идею или используйте 💾 Вводные для сохранения ввода."
)

# ─────────────────────────────────────────────────────────────
# Обработчики событий
# ─────────────────────────────────────────────────────────────

def on_workspace_change(selected_labels: list):
    """Изменение выбранных баз знаний."""
    # Получаем все workspace
    all_workspaces = config_manager.get_workspace_labels()
    selected_ids = []
    for label, ws_id in all_workspaces:
        # label в формате "name (id)"
        if label in selected_labels:
            selected_ids.append(ws_id)
    
    # Обновляем каждый workspace
    for label, ws_id in all_workspaces:
        enabled = ws_id in selected_ids
        config_manager.set_workspace_enabled(ws_id, enabled)
    
    return f"💾 Базы знаний обновлены: {len(selected_ids)} включено"


def refresh_workspaces():
    """Обновить список баз знаний из конфига."""
    # Перечитываем конфиг
    labels = config_manager.get_workspace_labels()
    enabled = config_manager.get_enabled_workspaces()
    
    labels_list = [label for label, _ in labels]
    selected = [label for label, ws_id in labels if ws_id in enabled]
    
    return gr.update(choices=labels_list, value=selected), f"🔄 Обновлено: {len(labels_list)} баз"


def on_checkpoint_change(selected_labels: list):
    """Изменение контрольных точек."""
    # Маппинг label -> key
    label_to_key = {label: key for key, label in CHECKPOINT_LABELS}
    
    # Обновляем все чекпоинты
    for key, label in CHECKPOINT_LABELS:
        enabled = label in selected_labels
        config_manager.set_checkpoint_enabled(key, enabled)
    
    return f"💾 Контрольные точки обновлены: {len(selected_labels)} включено"


def search_knowledge_base(query: str) -> str:
    """Поиск в базе знаний и форматирование результатов."""
    try:
        import sys
        import importlib.util
        from pathlib import Path
        
        ROOT_DIR = Path(__file__).parent.parent
        sys.path.insert(0, str(ROOT_DIR / "scripts"))
        
        # Импортируем функцию поиска
        spec = importlib.util.spec_from_file_location("query_knowledge", ROOT_DIR / "scripts" / "query-knowledge.py")
        query_knowledge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(query_knowledge)
        
        # Загружаем конфиг
        import yaml
        config_path = ROOT_DIR / "config" / "knowledge-bases.yaml"
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # Ищем только в активных workspace
        workspaces = [w for w in config.get("workspaces", []) if w.get("enabled", True)]
        if not workspaces:
            return "⚠️ Нет активных баз знаний. Включите базы в левой панели."
        
        all_results = []
        for workspace in workspaces:
            results = query_knowledge.query_anythingllm(workspace, query, top_k=3)
            if results:
                all_results.extend(results)
        
        if not all_results:
            return f"🔍 По запросу \"{query}\" ничего не найдено."
        
        # Формируем ответ
        output = f"📚 **Результаты поиска: \"{query}\"**\n\n"
        for i, result in enumerate(all_results[:5], 1):
            source = result.get('source', 'неизвестно')
            text = result.get('text', '')[:400]  # Обрезаем длинный текст
            output += f"**{i}. {source}**\n{text}...\n\n"
        
        return output
        
    except Exception as e:
        return f"❌ Ошибка поиска: {e}"


def on_chat_submit(message, history, project_name: str = "", content_type: str = "fiction"):
    """
    Обычный чат с LLM.
    Плавный диалог с контекстом истории, без сохранения в idea.md.
    
    Специальные команды:
    - /find <запрос> или /search <запрос> — поиск в базе знаний
    """
    if not message.strip():
        return "Пожалуйста, напишите сообщение."
    
    # Обработка команд поиска
    msg_lower = message.strip().lower()
    if msg_lower.startswith('/find ') or msg_lower.startswith('/search '):
        query = message[message.find(' ')+1:].strip()
        if query:
            return search_knowledge_base(query)
        else:
            return "❌ Укажите запрос после команды. Например: `/find диалог в стиле нуар`"
    
    # Обработка команды помощи
    if msg_lower == '/help':
        return """📖 **Команды чата:**

`/find <запрос>` или `/search <запрос>` — поиск в базе знаний
Примеры:
- `/find техника диалогов`
- `/search описание шторма`
- `/find характеристика героя`

Остальные сообщения — обычный диалог с ассистентом."""
    
    try:
        from scripts.utils.llm_client import LLMClient
        
        # Создаём клиент для оркестратора
        client = LLMClient(role="orchestrator")
        
        # Диалоговый системный промпт — естественное общение
        system_prompt = """Ты — творческий собеседник и помощник писателя. 

Общайся естественно, как человек:
- Отвечай живым языком, без шаблонов и формальных вставок
- Поддерживай разговор, задавай вопросы, предлагай идеи
- Если пользователь просит создать вводные из разговора — собери всё обсуждённое в структурированный вид
- Не используй markdown-заголовки вроде "**Вводные:**" или "**Жанр:**" в обычном разговоре
- Просто помогай развивать идею в свободной форме

Если пользователь спрашивает про техники письма, стили, диалоги — предложи использовать команду /find для поиска в базе знаний."""
        
        # Формируем контекст из истории диалога (исключаем placeholder)
        messages = []
        if history and len(history) > 0:
            for user_msg, assistant_msg in history:
                # Пропускаем placeholder-сообщение (где user_msg is None)
                if user_msg is not None:
                    messages.append({"role": "user", "content": user_msg})
                if assistant_msg and not assistant_msg.startswith("👋 Добро пожаловать"):
                    messages.append({"role": "assistant", "content": assistant_msg})
        
        # Добавляем текущее сообщение
        messages.append({"role": "user", "content": message})
        
        # Вызываем LLM с полным контекстом диалога
        response = client.call(
            system_prompt=system_prompt,
            user_message=messages
        )
        
        return response
        
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}\n\nПопробуйте ещё раз позже."


def on_run_click(project_name: str, content_type: str):
    """
    Кнопка «Запустить» — запускает пайплайн.
    """
    global pipeline_runner, log_watcher, pipeline_status, pipeline_output
    
    if not project_name:
        return "❌ Сначала выберите проект"
    
    if pipeline_runner.is_running:
        return "⏳ Пайплайн уже запущен"
    
    # Проверяем наличие вводных
    idea_file = config_manager.projects_dir / project_name / "input" / "idea.md"
    if not idea_file.exists():
        return f"❌ Нет вводных: {project_name}/input/idea.md"
    
    # Сбрасываем статус
    pipeline_status = "Запуск..."
    pipeline_output = ""
    
    # Функция обновления вывода
    def on_output(line: str):
        global pipeline_output
        pipeline_output += line + "\n"
    
    # Функция завершения
    def on_finish(returncode: int):
        global pipeline_status
        if returncode == 0:
            pipeline_status = "✅ Завершено"
        else:
            pipeline_status = f"❌ Ошибка (код {returncode})"
    
    # Запускаем пайплайн
    try:
        pipeline_runner.run(
            project_name=project_name,
            module=content_type,
            on_output=on_output,
            on_finish=on_finish
        )
        pipeline_status = "⏳ Выполняется..."
        
        # Запускаем наблюдение за логом
        log_file = config_manager.projects_dir / project_name / "project-log.md"
        if log_file.exists():
            log_watcher = LogWatcher(
                log_path=log_file,
                on_update=lambda lines: None,  # Можно добавить обработку
                poll_interval=2.0
            )
            log_watcher.start()
        
        return f"▶ Пайплайн запущен: {project_name} ({content_type})"
        
    except Exception as e:
        return f"❌ Ошибка запуска: {str(e)}"


def on_stop_click():
    """Кнопка «Стоп» — останавливает пайплайн."""
    global pipeline_runner, log_watcher, pipeline_status
    
    if not pipeline_runner.is_running:
        return "⏹ Пайплайн не запущен"
    
    pipeline_runner.stop()
    if log_watcher:
        log_watcher.stop()
    
    pipeline_status = "⏹ Остановлен"
    return "⏹ Пайплайн остановлен"


def on_pause_click():
    """Кнопка «Пауза» — пока не реализовано полностью."""
    return "⏸ Пауза (будет в Фазе 5 с контрольными точками)"


def get_pipeline_status():
    """Возвращает текущий статус и вывод пайплайна."""
    global pipeline_runner, pipeline_status, pipeline_output
    
    status = pipeline_status
    output = pipeline_output[-2000:] if len(pipeline_output) > 2000 else pipeline_output  # Последние 2000 символов
    
    if pipeline_runner.is_running:
        status_icon = "⏳"
    elif "✅" in status:
        status_icon = "✅"
    elif "❌" in status:
        status_icon = "❌"
    else:
        status_icon = "⏹"
    
    return f"{status_icon} **Статус**: {status}\n\n```\n{output}\n```"


def on_status_click():
    """Кнопка «Статус»."""
    config_summary = []
    mode = config_manager.get_mode()
    config_summary.append(f"Режим: {mode}")
    config_summary.append(f"Провайдер: {config_manager.get_provider()}")
    if mode == "orchestra":
        config_summary.append(f"Оркестратор: {config_manager.get_orchestra_model() or 'не задана'}")
    else:
        agents = config_manager.get_agents_config()
        for role, model in agents.items():
            config_summary.append(f"  {role}: {model or '—'}")
    config_summary.append(f"Баз знаний: {len(config_manager.get_enabled_workspaces())}")

    return (
        "📊 **Текущая конфигурация**:\n```\n" + "\n".join(config_summary) + "\n```"
    )

def on_test_connection(provider_key):
    """Проверка соединения с выбранным провайдером"""
    if not provider_key:
        return "❌ Провайдер не выбран"

    # Тестовые модели для каждого провайдера
    TEST_MODELS = {
        "openrouter": "openai/gpt-3.5-turbo",
        "ollama": "llama2",
    }

    test_model = TEST_MODELS.get(provider_key)
    if not test_model:
        return f"❌ Провайдер {provider_key} не поддерживается"

    try:
        import openai
        import os

        # Получаем API ключ
        api_key = os.environ.get("OPENROUTER_API_KEY", "") if provider_key == "openrouter" else "dummy"

        # Настраиваем base_url для провайдера
        if provider_key == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        elif provider_key == "ollama":
            base_url = "http://localhost:11434/v1"
        else:
            return f"❌ Неизвестный провайдер: {provider_key}"

        # Проверяем наличие API ключа для облачных провайдеров
        if provider_key == "openrouter" and not api_key:
            return "❌ OpenRouter: API ключ не задан (OPENROUTER_API_KEY)"

        # Создаем OpenAI клиента с нужным base_url
        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        # Делаем тестовый запрос
        response = client.chat.completions.create(
            model=test_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Reply with a single word."},
                {"role": "user", "content": "Say 'OK' if you hear me."}
            ],
            temperature=0.7,
            max_tokens=10
        )

        answer = response.choices[0].message.content

        if answer and "OK" in answer.upper():
            return f"✅ {provider_key}: Соединение успешно!"
        elif answer:
            return f"✅ {provider_key}: Ответ получен: {answer[:50]}..."
        return f"❌ {provider_key}: Пустой ответ от API"

    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            return f"⚠️ {provider_key}: Лимит запросов исчерпан"
        elif "api_key" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            return f"❌ {provider_key}: API ключ не задан или неверный"
        elif "400" in error_msg:
            return f"❌ {provider_key}: Неверный запрос"
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return f"❌ {provider_key}: Не удалось подключиться (проверьте сеть)"
        return f"❌ {provider_key}: {error_msg[:100]}"

# ─────────────────────────────────────────────────────────────
# Функции для мультиагентного селектора моделей
# ─────────────────────────────────────────────────────────────

def on_provider_change_simple(provider_display: str):
    """
    Обновляет текст под провайдером при смене.
    Возвращает: строку "Выбран: {provider_key}"
    """
    provider_key = get_provider_key(provider_display)
    return f"Выбран: {provider_key}"


def on_show_models_click(provider_display: str, providers_data: dict):
    """
    Формирует HTML-список моделей для отображения.
    Возвращает: HTML-строку со списком моделей
    """
    provider_key = get_provider_key(provider_display)

    # Получаем модели для провайдера
    if provider_key not in providers_data:
        return "<p>⚠️ Нет моделей для этого провайдера</p>"

    provider_models = providers_data[provider_key]

    # Формируем HTML-список моделей
    models_html = f"<h3 style='margin-top: 0;'>МОДЕЛИ {provider_key.upper()}</h3>"
    models_html += "<div style='max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #f9f9f9;'>"

    for model in provider_models:
        model_id = model.get("id", "")
        model_name = model.get("name", model_id)
        models_html += f"<div style='padding: 8px; border-bottom: 1px solid #ddd; font-family: monospace; font-size: 13px;'>{model_id}</div>"

    models_html += "</div>"
    models_html += "<p style='margin-top: 10px; color: #666; font-size: 12px;'>💡 <strong>Совет:</strong> Скопируйте ID модели (Ctrl+C) и вставьте в текстовое поле</p>"

    return models_html


def on_models_loaded_click():
    """
    Читает config/models.yaml и формирует Markdown-таблицу.
    Всегда 6 строк: Мультиагент (оркестратор) + Agent 1-5.
    В зависимости от mode заполняется либо первая строка, либо строки 1-5.
    """
    config = config_manager.get_model_config()
    mode = config.get("mode", "не задан")
    provider = config.get("provider", "не задан")

    result = f"**Режим:** {mode} | **Провайдер:** {provider}\n\n"

    # Модель оркестратора (первая строка)
    orchestra = config.get("orchestra", {})
    orchestra_model = ""
    if mode == "orchestra" and isinstance(orchestra, dict):
        orchestra_model = orchestra.get("model", "")

    # Модели агентов (строки 1-5)
    agents = config.get("agents", {})
    agent_roles = [
        ("generator",   "Генератор"),
        ("critic",      "Критик"),
        ("writer",      "Писатель"),
        ("editor",      "Редактор"),
        ("proofreader", "Корректор"),
    ]

    result += "| Агент | Роль | Модель |\n"
    result += "|-------|------|--------|\n"

    # Строка 1: Мультиагент / Оркестратор
    orch_display = f"`{orchestra_model}`" if orchestra_model else "—"
    result += f"| Мультиагент | Оркестратор | {orch_display} |\n"

    # Строки 2-6: Agent 1-5
    for i, (key, label) in enumerate(agent_roles, 1):
        if mode == "multi-agent":
            model = agents.get(key, "")
            model_display = f"`{model}`" if model else "—"
        else:
            model_display = "—"
        result += f"| Agent {i} | {label} | {model_display} |\n"

    return result


    # ─────────────────────────────────────────────────────────────
    # Построение интерфейса (simple-only, OpenRouter по умолчанию)
    # ─────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Система создания литературного контента") as app:

        # ─── ЗАГОЛОВОК ─────────────────────────────────────────
        gr.Markdown("## 📖 Система автоматизации создания литературного контента")
        gr.Markdown("🟡 **Фаза 2**: YAML-конфиги подключены. Изменения автоматически сохраняются.")

        # ─── ВЕРХНЯЯ ПАНЕЛЬ ────────────────────────────────────
        with gr.Row():
            with gr.Column(scale=3):
                # Убран dropdown, теперь проект вводится в поле чата
                gr.Markdown("<!-- project selection moved to chat block -->")
            with gr.Column(scale=2):
                module_dropdown = gr.Dropdown(
                    label="Тип контента",
                    choices=PLACEHOLDER_MODULES,
                    value=PLACEHOLDER_MODULES[0],
                    interactive=True,
                )
            with gr.Column(scale=1, min_width=120):
                gr.Markdown("<!-- new project button moved to sidebar -->")

        gr.Markdown("---")

        # ─── ОСНОВНАЯ ЗОНА ──────────────────────────────────────
        with gr.Row():

            # ─── ЛЕВАЯ ПАНЕЛЬ ────────────────────────────────────
            with gr.Column(scale=1, min_width=280):

                # Блок: Новый проект
                gr.Markdown("**🆕 НОВЫЙ ПРОЕКТ**")
                new_project_name = gr.Textbox(
                    label="Название",
                    placeholder="my-story",
                    info="латиница, цифры, дефис",
                )
                new_project_type = gr.Dropdown(
                    label="Тип",
                    choices=PLACEHOLDER_MODULES[:3],
                    value="fiction",
                )
                create_project_btn = gr.Button("✅ Создать проект", variant="primary")
                new_project_status = gr.Markdown()

                # Блок: Модели
                gr.Markdown("**⚙️ МОДЕЛИ**")

                # Кнопка проверки соединения
                test_btn = gr.Button("Proverit soedinenie", variant="secondary", size="sm")
                test_status = gr.Markdown(value="⏳ Нажмите для проверки соединения")

                # Инициализация текущего провайдера
                init_simple_prov, init_simple_mod = config_manager.get_simple_model()
                if not init_simple_prov or init_simple_prov not in AVAILABLE_PROVIDERS:
                    init_simple_prov = AVAILABLE_PROVIDERS[0]

                # Загружаем актуальные модели от включённых провайдеров
                PROVIDERS_DATA = provider_manager.fetch_models()

                # 1. Провайдер (Radio buttons)
                provider_radio = gr.Radio(
                    label="Провайдер",
                    choices=PROVIDER_RADIO_CHOICES,
                    value=PROVIDER_DISPLAY_NAMES.get(init_simple_prov, PROVIDER_RADIO_CHOICES[0]),
                    interactive=True
                )

                # 2. Текст под провайдером
                provider_status_text = f"Выбран: {init_simple_prov}"
                provider_status = gr.Markdown(value=provider_status_text)

                # 3. Кнопка открытия модального окна
                show_models_btn = gr.Button("📋 Показать все модели", variant="secondary", size="sm")

                # 4. Область для отображения списка моделей
                models_display = gr.HTML(value="", elem_id="models-list-display")

                # 5. Кнопка "Модели выбраны" — читает файл и показывает таблицу
                models_loaded_btn = gr.Button("✅ Модели выбраны", variant="primary", size="sm")

                # 6. Область отображения загруженных моделей
                models_loaded_display = gr.Markdown(value="")

                # Блок: Базы знаний
                gr.Markdown("**🗃️ БАЗЫ ЗНАНИЙ**")
                workspace_labels_list = [label for label, _ in WORKSPACE_LABELS]
                workspace_selected = [label for label, ws_id in WORKSPACE_LABELS if ws_id in ENABLED_WORKSPACES]
                
                knowledge_checkboxes = gr.CheckboxGroup(
                    label="",
                    choices=workspace_labels_list,
                    value=workspace_selected,
                    interactive=True,
                )
                workspace_status = gr.Markdown()
                with gr.Row():
                    gr.Button("📁 Загрузить документы", size="sm", variant="secondary")
                    refresh_btn = gr.Button("🔄 Обновить", size="sm", variant="secondary")

                # Блок: Контрольные точки
                gr.Markdown("**⏸️ КОНТРОЛЬНЫЕ ТОЧКИ**")
                checkpoint_labels_list = [label for _, label in CHECKPOINT_LABELS]
                
                checkpoint_checks = gr.CheckboxGroup(
                    label="",
                    choices=checkpoint_labels_list,
                    value=ENABLED_CHECKPOINTS,
                    interactive=True,
                )
                checkpoint_status = gr.Markdown()

                # Блок: Действия
                gr.Markdown("**▶ ДЕЙСТВИЯ**")
                with gr.Row():
                    run_btn    = gr.Button("▶ Запустить", variant="primary", size="sm")
                    pause_btn  = gr.Button("⏸ Пауза",    variant="secondary", size="sm")
                with gr.Row():
                    stop_btn   = gr.Button("⏹ Стоп",     variant="stop", size="sm")
                    status_btn = gr.Button("📊 Статус",   variant="secondary", size="sm")

            # ─── ЦЕНТРАЛЬНАЯ ОБЛАСТЬ ─────────────────────────────
            with gr.Column(scale=3):

                # Чат
                with gr.Group():
                    gr.Markdown("**💬 ЧАТ**")
                    # Поле для ввода имени проекта (новый подход)
                    with gr.Row():
                        project_name_input = gr.Textbox(
                            label="Проект",
                            placeholder="Vvedite nazvanie (latinice)",
                            scale=3,
                        )
                        set_project_btn = gr.Button("💾 Save", variant="secondary", size="sm")
                        current_project_display = gr.Markdown("**Текущий проект:** не выбран")
                    
                    # Статус сохранения чата
                    chat_save_status = gr.Markdown()
                    
                    # Gradio >=4.44 ожидает формат списка пар (user, assistant)
                    chatbot = gr.Chatbot(
                        value=[(None, PLACEHOLDER_CHAT_MSG)],
                        height=600,
                        show_label=False,
                        layout="bubble",
                    )
                    with gr.Row():
                        chat_stop_btn = gr.Button("⏹", variant="stop", size="sm", min_width=40, interactive=False)
                        chat_input = gr.Textbox(
                            placeholder="Опишите вашу идею...",
                            show_label=False,
                            scale=5,
                            lines=2,
                        )
                        chat_send_btn = gr.Button("Отправить", variant="primary", scale=1)
                        save_idea_btn = gr.Button("💾 Vvodnye", variant="secondary", scale=1)
                    
                    # Статус сохранения вводных
                    idea_save_status = gr.Markdown()

                # Состояние текущего проекта (внутри Blocks для правильной работы)
                current_project_state = gr.State(value=None)

                # Статус
                with gr.Group():
                    gr.Markdown("**📡 СТАТУС**")
                    status_output = gr.Markdown(
                        value="Выберите проект и настройте параметры слева.",
                    )
                    progress_bar = gr.Slider(
                        label="Прогресс",
                        minimum=0, maximum=100, value=0, step=1,
                        interactive=False,
                    )

        # ─────────────────────────────────────────────────────────
        # Подключение обработчиков событий (Фаза 2)
        # ─────────────────────────────────────────────────────────

        # ═════════════════════════════════════════════════════════════
        # Обработчики событий для мультиагентного селектора моделей
        # ═════════════════════════════════════════════════════════════

        # 1. Смена провайдера → обновление текста
        provider_radio.change(
            on_provider_change_simple,
            inputs=[provider_radio],
            outputs=[provider_status]
        )

        # 2. Кнопка "Показать все модели" → переключение контента
        _models_visible = [False]

        def toggle_models_display(provider_display):
            """Переключает контент: если показан — очищает, если скрыт — показывает модели"""
            if _models_visible[0]:
                _models_visible[0] = False
                return ""
            else:
                _models_visible[0] = True
                providers_data = provider_manager.fetch_models()
                return on_show_models_click(provider_display, providers_data)

        show_models_btn.click(
            toggle_models_display,
            inputs=[provider_radio],
            outputs=[models_display]
        )

        # 3. Кнопка "✅ Модели выбраны" → чтение конфига и отображение таблицы
        models_loaded_btn.click(
            on_models_loaded_click,
            outputs=[models_loaded_display]
        )

        # Изменение баз знаний
        knowledge_checkboxes.change(
            on_workspace_change,
            inputs=knowledge_checkboxes,
            outputs=workspace_status
        )
        
        # Обновление списка баз знаний
        refresh_btn.click(
            refresh_workspaces,
            outputs=[knowledge_checkboxes, workspace_status]
        )

        # Изменение чекпоинтов
        checkpoint_checks.change(
            on_checkpoint_change,
            inputs=checkpoint_checks,
            outputs=checkpoint_status
        )

        # Установка текущего проекта
        def set_current_project_display(project_name):
            """Обновляет отображение текущего проекта."""
            if not project_name or not project_name.strip():
                return "**Текущий проект:** не выбран"
            return f"**Текущий проект:** {project_name.strip()}"

        def set_current_project_state(project_name):
            """Сохраняет имя проекта в состояние."""
            if not project_name or not project_name.strip():
                return None
            return project_name.strip()

        set_project_btn.click(
            set_current_project_display,
            inputs=project_name_input,
            outputs=current_project_display
        ).then(
            set_current_project_state,
            inputs=project_name_input,
            outputs=current_project_state
        )

        # Состояние для типа контента
        current_content_type = gr.State(value="fiction")
        
        # Синхронизация module_dropdown с состоянием
        def update_content_type(content_type):
            return content_type
        
        module_dropdown.change(
            update_content_type,
            inputs=module_dropdown,
            outputs=current_content_type
        )
        
        # ═════════════════════════════════════════════════════════════
        # ЧАТ с асинхронной обработкой и кнопкой "Стоп"
        # ═════════════════════════════════════════════════════════════
        
        import time
        
        def chat_with_stop(message, history, project_name, content_type):
            """
            Генератор для чата с возможностью отмены.
            Использует yield для обновления интерфейса во время ожидания.
            """
            global chat_status
            
            if not message.strip():
                yield history, "", gr.update(interactive=True), gr.update(interactive=False)
                return
            
            if chat_runner.is_running:
                yield history, "⏳ Запрос уже выполняется...", gr.update(interactive=True), gr.update(interactive=False)
                return
            
            # Добавляем сообщение пользователя в историю с индикатором ожидания
            history = history + [(message, "⏳ *Ожидание ответа...*")]
            chat_status = "⏳ Ожидание ответа..."
            
            # Блокируем отправку, активируем стоп
            yield history, "⏳ Отправлено, ожидаю ответ...", gr.update(interactive=False), gr.update(interactive=True)
            
            # Флаг для отслеживания завершения
            response_received = [False]
            response_value = [None]
            
            def on_response(response):
                response_value[0] = response
                response_received[0] = True
            
            def on_finish():
                response_received[0] = True
            
            def on_cancelled():
                response_value[0] = "⏹ **Процесс диалога остановлен**"
                response_received[0] = True
            
            # Запускаем запрос асинхронно
            chat_runner.run(
                message=message,
                history=history[:-1],
                project_name=project_name,
                content_type=content_type,
                on_response=on_response,
                on_finish=on_finish,
                on_cancelled=on_cancelled
            )
            
            # Ждем завершения с проверкой каждую 100мс
            max_wait = 300  # Максимум 30 секунд (300 * 0.1)
            waited = 0
            while not response_received[0] and chat_runner.is_running and waited < max_wait:
                time.sleep(0.1)
                waited += 1
            
            # Получаем ответ
            if response_value[0] is None:
                response_value[0] = chat_runner.get_response()
            
            # Обновляем историю с полученным ответом
            if history and len(history) > 0:
                if response_value[0]:
                    history[-1] = (history[-1][0], response_value[0])
                else:
                    history[-1] = (history[-1][0], "⚠️ *Не удалось получить ответ*")
            
            # Сохраняем чат в файл
            save_status = save_chat_to_file(history, project_name)
            chat_status = "Готов"
            
            # Разблокируем отправку, деактивируем стоп
            yield history, save_status, gr.update(interactive=True), gr.update(interactive=False)
        
        def stop_chat_and_update(history, project_name):
            """Останавливает запрос и обновляет чат."""
            global chat_status
            
            was_running = chat_runner.is_running
            
            if was_running:
                chat_runner.stop()
                chat_status = "⏹ Остановлено"
                time.sleep(0.2)  # Даем время на остановку
            
            # Проверяем, не пришел ли ответ
            response = chat_runner.get_response()
            
            if history and len(history) > 0:
                if response:
                    history[-1] = (history[-1][0], response)
                elif was_running:
                    history[-1] = (history[-1][0], "⏹ **Процесс диалога остановлен**")
            
            # Сохраняем чат в файл
            save_status = save_chat_to_file(history, project_name) if was_running else ""
            
            return history, save_status, gr.update(interactive=True), gr.update(interactive=False)
        
        # Обработчик отправки сообщения (генератор)
        chat_send_btn.click(
            chat_with_stop,
            inputs=[chat_input, chatbot, current_project_state, current_content_type],
            outputs=[chatbot, chat_save_status, chat_send_btn, chat_stop_btn]
        )
        
        # Обработчик нажатия Enter в поле ввода (генератор)
        chat_input.submit(
            chat_with_stop,
            inputs=[chat_input, chatbot, current_project_state, current_content_type],
            outputs=[chatbot, chat_save_status, chat_send_btn, chat_stop_btn]
        )
        
        # Обработчик кнопки "Стоп"
        chat_stop_btn.click(
            stop_chat_and_update,
            inputs=[chatbot, current_project_state],
            outputs=[chatbot, chat_save_status, chat_send_btn, chat_stop_btn]
        )
        
        # Обработчик сохранения вводных
        save_idea_btn.click(
            save_idea_to_file,
            inputs=[chat_input, current_project_state],
            outputs=idea_save_status
        )

        # Кнопки действий
        status_btn.click(get_pipeline_status, outputs=status_output)
        
        run_btn.click(
            on_run_click,
            inputs=[current_project_state, current_content_type],
            outputs=status_output
        )
        
        pause_btn.click(on_pause_click, outputs=status_output)
        stop_btn.click(on_stop_click, outputs=status_output)
        
        # Проверка соединения с выбранным провайдером
        def test_provider_connection(provider_display):
            """Конвертирует display name в key и тестирует соединение"""
            provider_key = get_provider_key(provider_display)
            return on_test_connection(provider_key)

        test_btn.click(
            test_provider_connection,
            inputs=[provider_radio],
            outputs=[test_status]
        )
        
        # Автообновление статуса каждые 2 секунды (для отображения прогресса пайплайна)
        def auto_refresh_status():
            return get_pipeline_status()
        
        # Запускаем периодическое обновление статуса
        import threading
        def status_refresh_loop():
            import time
            while True:
                time.sleep(2.0)
                try:
                    # Обновляем статус через queue (если нужно)
                    pass
                except:
                    pass
        
        # Запускаем фоновый поток обновления
        refresh_thread = threading.Thread(target=status_refresh_loop, daemon=True)
        refresh_thread.start()

        # ─── ОБРАБОТЧИКИ СОЗДАНИЯ ПРОЕКТА ──────────────────────
        def create_new_project(name: str, module: str):
            """Создать новый проект с базовой структурой."""
            if not name.strip():
                return (
                    "[ERROR] Vvedite nazvanie proekta",
                    name,
                )
            
            # Проверка на допустимые символы
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', name.strip()):
                return (
                    "[ERROR] Tolko latinskie bukvy, cifry, defis",
                    name,
                )
            
            project_path = config_manager.projects_dir / name.strip()
            if project_path.exists():
                return (
                    f"[ERROR] Proekt '{name}' uzhe sushchestvuet",
                    "",  # очистить поле для нового ввода
                )
            
            # Создаём структуру проекта
            try:
                (project_path / "input").mkdir(parents=True)
                (project_path / "variants").mkdir()
                (project_path / "selected").mkdir()
                (project_path / "chapters").mkdir()
                (project_path / "output").mkdir()
                (project_path / "chats").mkdir()
                
                # Создаём idea.md с заглушкой
                idea_content = f"""# Вводные для проекта: {name.strip()}

**Тип контента:** {module}
**Дата создания:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Описание идеи
(Заполните здесь описание вашей идеи...)

## Требования
- Жанр:
- Объём:
- Особые требования:
"""
                (project_path / "input" / "idea.md").write_text(idea_content, encoding="utf-8")
                
                # Создаём project-log.md
                (project_path / "project-log.md").write_text(
                    f"# Лог проекта: {name.strip()}\n\n",
                    encoding="utf-8"
                )
                
                return (
                    f"[OK] Proekt '{name}' sozdan!",
                    "",  # очистить поле названия
                )
            except Exception as e:
                return (
                    f"[ERROR] Oshibka: {e}",
                    "",  # очистить поле для нового ввода
                )

        def create_new_project_status(name: str, module: str):
            """Возвращает только статус создания проекта."""
            result = create_new_project(name, module)
            return result[0]  # только статус

        def create_new_project_clear(name: str, module: str):
            """Возвращает только новое значение поля названия."""
            result = create_new_project(name, module)
            return result[1]  # только поле названия

        create_project_btn.click(
            create_new_project_status,
            inputs=[new_project_name, new_project_type],
            outputs=new_project_status
        ).then(
            create_new_project_clear,
            inputs=[new_project_name, new_project_type],
            outputs=new_project_name
        )

    return app


def free_port(port: int) -> bool:
    """
    Освобождает порт, завершая процессы, которые его используют.

    Args:
        port: номер порта для освобождения

    Returns:
        True если порт был освобожден или уже свободен, False при ошибке
    """
    import platform
    import subprocess

    try:
        if platform.system() == "Windows":
            # Находим процессы на порту
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout:
                # Извлекаем PID из вывода
                lines = result.stdout.strip().split('\n')
                pids = set()
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids.add(pid)

                # Завершаем процессы
                for pid in pids:
                    print(f"[INFO] Завершение процесса {pid} на порту {port}...")
                    subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)

                # Ждем освобождения порта
                import time
                time.sleep(1)
                print(f"[OK] Порт {port} освобожден")
                return True
            else:
                # Порт свободен
                return True

        else:  # Linux/Mac
            result = subprocess.run(
                f'lsof -ti:{port}',
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        print(f"[INFO] Завершение процесса {pid} на порту {port}...")
                        subprocess.run(f'kill -9 {pid}', shell=True)

                import time
                time.sleep(1)
                print(f"[OK] Порт {port} освобожден")
                return True
            else:
                return True

    except Exception as e:
        print(f"[WARNING] Не удалось освободить порт {port}: {e}")
        return False


def main():
    """
    Точка входа.
    
    Рекомендации по запуску:
    1. Обычный запуск (блокирует терминал, открывает браузер):
       python gui/app.py
    
    2. Запуск из IDE без блокировки (фоновый режим):
       python gui/app.py --no-block
    
    3. Остановка сервера: Ctrl+C в терминале или закрыть вкладку браузера
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-block", action="store_true",
                        help="Не блокировать терминал (для запуска из IDE)")
    parser.add_argument("--port", type=int, default=7860,
                        help="Порт для сервера (по умолчанию 7860)")
    parser.add_argument("--skip-free-port", action="store_true",
                        help="Пропустить автоматическую очистку порта (не рекомендуется)")
    args = parser.parse_args()

    # Автоматически освобождаем порт перед запуском (если не указан флаг --skip-free-port)
    if not args.skip_free_port:
        print(f"[1/2] Освобождаем порт {args.port}...")
        if free_port(args.port):
            print(f"[OK] Порт {args.port} освобождён")
        else:
            print(f"[WARNING] Не удалось гарантированно освободить порт {args.port}")
        print(f"[2/2] Запускаем GUI...")

    app = build_ui()

    # Открываем в Firefox вместо браузера по умолчанию (Chrome вызывает Svelte DOM баг)
    import webbrowser
    try:
        firefox = webbrowser.get("C:/Program Files/Mozilla Firefox/firefox.exe %s")
        webbrowser.register("firefox", None, firefox)
    except webbrowser.Error:
        pass

    # Для запуска из IDE: не блокируем терминал
    if args.no_block:
        print(f">>> GUI zapuschen na http://127.0.0.1:{args.port}")
        print("    Dlya ostanovki: Ctrl+C ili zakroyte terminal.")
        app.launch(
            server_name="127.0.0.1",
            server_port=args.port,
            inbrowser=False,
            prevent_thread_lock=True,
            show_error=True,
        )
        webbrowser.get("firefox").open(f"http://127.0.0.1:{args.port}")
        # Держим процесс живым
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n>>> GUI ostanovlen.")
    else:
        # Обычный запуск: блокируем, открываем браузер
        app.launch(
            server_name="127.0.0.1",
            server_port=args.port,
            inbrowser=False,
            show_error=True,
        )
        webbrowser.get("firefox").open(f"http://127.0.0.1:{args.port}")


if __name__ == "__main__":
    main()
