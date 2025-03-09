Добавлены три бесплатные модели:

Ollama - локальный сервер для запуска моделей (требует установки на ваш сервер):

Llama 2 - универсальная модель с хорошим балансом производительности
Mistral - более новая и эффективная модель


Hugging Face - API с бесплатными ограничениями:

Используется модель Mistral-7B-Instruct


Google Gemini (бывший PaLM):

Имеет бесплатный уровень использования



Дополнительные улучшения:

Выбор модели для каждого пользователя:

Добавлена команда /model для выбора предпочитаемой модели
Выбор сохраняется в базе данных


Расширенные команды бота:

/start - начальное приветствие
/clear - очистка истории чата
/help - справка по командам


Улучшенный интерфейс:

Кнопки для выбора модели



Для использования кода вам нужно:

Установить Ollama на ваш сервер для локальных моделей (https://ollama.ai/)
Получить бесплатный API ключ Hugging Face (https://huggingface.co/settings/tokens)
Получить бесплатный API ключ Google Gemini (https://ai.google.dev/)
Добавить эти ключи в .env файл:
CopyHUGGINGFACE_API_KEY=ваш_ключ
GOOGLE_AI_API_KEY=ваш_ключ
OLLAMA_HOST=http://localhost:11434  # или URL вашего сервера Ollama


Вся остальная логика работы бота (платежи, ограничения запросов, история чата) сохранена как в оригинальном коде.RetryClaude does not have the ability to run the code it generates yet. Claude does not have internet access. Links provided may not be accurate or up to date.