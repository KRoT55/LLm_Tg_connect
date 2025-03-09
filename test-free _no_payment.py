import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import sqlite3
import json
import logging
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),  # Логи в файл с кодировкой UTF-8
        logging.StreamHandler()  # Логи в консоль
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получаем ключи API из переменных окружения
API_TOKEN = os.getenv('API_TOKEN')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')  # По умолчанию localhost

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Системный промпт для ИИ
system_prompt = """
Ты — профессиональный AI-консультант. Твоя задача — давать подробные, информативные и структурированные ответы. 
1. Давай примеры, разборы, пошаговые инструкции.  
2. Оформляй ответ логично: списки, абзацы, заголовки.  
3. Используй эмодзи 😊, чтобы делать текст более живым и наглядным.  
4. Если информация логически разделяется на категории, представь её в виде таблицы, используя Markdown-формат. 📊  
5. Упоминай важные нюансы и возможные риски.  
6. Если вопрос требует рассуждений — используй аналитику и факты.  
7. Будь дружелюбным, но профессиональным.  
"""

# Класс для работы с базой данных
class UserDatabase:
    def __init__(self, db_name='users.db'):
        self.db_name = db_name
        self.create_db()

    # Создание базы данных и таблицы
    def create_db(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, 
                    requests INTEGER, 
                    chat_history TEXT,  -- История чата
                    last_request_time TEXT  -- Время последнего запроса
                )
            ''')
            conn.commit()
            logger.info("База данных и таблица созданы или уже существуют.")

    # Проверка, существует ли пользователь в базе
    def user_exists(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
            return cursor.fetchone() is not None

    # Создание пользователя с начальной информацией
    def create_user(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (user_id, requests, chat_history, last_request_time) VALUES (?, ?, ?, ?)',
                (user_id, 0, json.dumps([]), datetime.now().isoformat()))
            conn.commit()
            logger.info(f"Пользователь {user_id} создан.")

    # Получение количества запросов пользователя
    def get_user_requests(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT requests FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0

    # Увеличение количества запросов пользователя
    def increment_user_requests(self, user_id):
        requests = self.get_user_requests(user_id) + 1
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET requests = ?, last_request_time = ? WHERE user_id = ?',
                           (requests, datetime.now().isoformat(), user_id))
            conn.commit()
            logger.info(f"Запросы пользователя {user_id} увеличены до {requests}.")

    # Получение истории чатов пользователя
    def get_chat_history(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT chat_history FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return []

    # Обновление истории чатов пользователя
    def update_chat_history(self, user_id, chat_history):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET chat_history = ? WHERE user_id = ?',
                           (json.dumps(chat_history), user_id))
            conn.commit()
            logger.info(f"История чата пользователя {user_id} обновлена.")

    # Получение времени последнего запроса
    def get_last_request_time(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_request_time FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return datetime.fromisoformat(result[0]) if result else datetime.now()

    # Сброс лимита запросов через 24 часа
    def reset_requests_if_needed(self, user_id):
        last_request_time = self.get_last_request_time(user_id)
        if datetime.now() - last_request_time > timedelta(days=1):
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET requests = 0 WHERE user_id = ?', (user_id,))
                conn.commit()
                logger.info(f"Лимит запросов пользователя {user_id} сброшен.")


# Инициализация базы данных
db = UserDatabase()

# Функция для работы с Ollama API
async def ollama_chat(messages, model="llama2"):
    try:
        # Преобразуем сообщения в формат, понятный Llama
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                formatted_messages.append({"role": "system", "content": msg["content"]})
            elif msg["role"] == "user":
                formatted_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                formatted_messages.append({"role": "assistant", "content": msg["content"]})

        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            headers={"Content-Type": "application/json"},
            json={"model": model, "messages": formatted_messages},
            stream=True  # Включаем потоковый режим
        )

        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        # Декодируем строку и парсим JSON
                        json_data = json.loads(line.decode('utf-8'))
                        if "message" in json_data and "content" in json_data["message"]:
                            full_response += json_data["message"]["content"]
                    except json.JSONDecodeError:
                        logger.error(f"Ошибка декодирования JSON: {line}")
                        continue

            if full_response:
                return full_response
            else:
                return "Получен пустой ответ от модели."
        else:
            logger.error(f"Ошибка Ollama API: {response.status_code}, {response.text}")
            return f"Ошибка Ollama API: {response.status_code}"
    except Exception as e:
        logger.error(f"Ошибка при запросе к Ollama: {str(e)}")
        return f"Произошла ошибка при обработке запроса: {str(e)}"


async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} написал: {message.text}")

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    # Сбрасываем лимит запросов, если прошло больше 24 часов
    db.reset_requests_if_needed(user_id)

    # Проверяем количество использованных запросов
    if db.get_user_requests(user_id) >= 20:  # Лимит 20 запросов
        await message.answer("❌ Вы исчерпали лимит бесплатных запросов на сегодня. Попробуйте завтра.")
        logger.info(f"Пользователь {user_id} исчерпал лимит запросов.")
        return

    # Получаем историю чата
    chat_history = db.get_chat_history(user_id)

    # Если это первое сообщение, добавляем системный промпт
    if not chat_history:
        chat_history.append({"role": "system", "content": system_prompt})

    # Добавляем новое сообщение пользователя в историю
    chat_history.append({"role": "user", "content": message.text})

    try:
        await message.answer("⏳ Думаю...")
        logger.info(f"Бот думает над ответом для пользователя {user_id}.")

        # Ограничиваем историю чата, чтобы не превысить лимит токенов
        if len(chat_history) > 10:  # Если история больше 10 сообщений
            # Сохраняем системный промпт и последние N сообщений
            limited_history = [chat_history[0]] + chat_history[-9:]
        else:
            limited_history = chat_history

        reply = await ollama_chat(limited_history, "llama2")

        # Проверяем, что ответ не пустой
        if not reply or reply.strip() == "":
            reply = "Извините, модель не смогла сгенерировать ответ. Пожалуйста, попробуйте переформулировать вопрос."

        await message.answer(reply)
        logger.info(f"Бот ответил пользователю {user_id}: {reply}")

        # Добавляем ответ AI в историю
        chat_history.append({"role": "assistant", "content": reply})
        db.update_chat_history(user_id, chat_history)

        # Увеличиваем счетчик запросов
        db.increment_user_requests(user_id)

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса пользователя {user_id}: {str(e)}")
        await message.answer(f"❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз.")

# Чат с моделью
async def chat_with_ai(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} написал: {message.text}")

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    # Сбрасываем лимит запросов, если прошло больше 24 часов
    db.reset_requests_if_needed(user_id)

    # Проверяем количество использованных запросов
    if db.get_user_requests(user_id) >= 20:  # Лимит 20 запросов
        await message.answer("❌ Вы исчерпали лимит бесплатных запросов на сегодня. Попробуйте завтра.")
        logger.info(f"Пользователь {user_id} исчерпал лимит запросов.")
        return

    # Получаем историю чата
    chat_history = db.get_chat_history(user_id)

    # Если это первое сообщение, добавляем системный промпт
    if not chat_history:
        chat_history.append({"role": "system", "content": system_prompt})

    # Добавляем новое сообщение пользователя в историю
    chat_history.append({"role": "user", "content": message.text})

    try:
        await message.answer("⏳ Думаю...")
        logger.info(f"Бот думает над ответом для пользователя {user_id}.")

        # Ограничиваем историю чата, чтобы не превысить лимит токенов
        if len(chat_history) > 10:  # Если история больше 10 сообщений
            # Сохраняем системный промпт и последние N сообщений
            limited_history = [chat_history[0]] + chat_history[-9:]
        else:
            limited_history = chat_history

        reply = await ollama_chat(limited_history, "llama2")

        # Проверяем, что ответ не пустой
        if not reply or reply.strip() == "":
            reply = "Извините, модель не смогла сгенерировать ответ. Пожалуйста, попробуйте переформулировать вопрос."

        await message.answer(reply)
        logger.info(f"Бот ответил пользователю {user_id}: {reply}")

        # Добавляем ответ AI в историю
        chat_history.append({"role": "assistant", "content": reply})
        db.update_chat_history(user_id, chat_history)

        # Увеличиваем счетчик запросов
        db.increment_user_requests(user_id)

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса пользователя {user_id}: {str(e)}")
        await message.answer(f"❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз.")

# Обработчик команды /start
@dp.message(lambda message: message.text == "/start")
async def cmd_start(message: Message):
    user_id = message.from_user.id

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    await message.answer(
        "👋 Привет! Я AI-консультант на базе модели Llama 2. "
        "Вы можете задать мне вопросы или попросить совета. "
    )

# Обработчик команды /help
@dp.message(lambda message: message.text == "/help")
async def cmd_help(message: Message):
    await message.answer(
        "🔍 Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/clear - Очистить историю чата\n"
        "/help - Показать эту справку\n\n"
        "ℹ️ Вы можете использовать до 20 бесплатных запросов в день."
    )

# Обработчик команды /clear
@dp.message(lambda message: message.text == "/clear")
async def cmd_clear(message: Message):
    user_id = message.from_user.id

    # Создаем новую историю только с системным промптом
    new_history = [{"role": "system", "content": system_prompt}]
    db.update_chat_history(user_id, new_history)

    await message.answer("🧹 История чата очищена!")

# Обработчик всех остальных сообщений
@dp.message()
async def handle_message(message: Message):
    # Проверяем, есть ли в сообщении текст
    if not message.text:
        await message.answer("Я могу обрабатывать только текстовые сообщения.")
        return

    # Проверяем, не является ли сообщение командой
    if message.text.startswith("/"):
        await message.answer("❓ Неизвестная команда. Используйте /help для списка команд.")
        return

    await chat_with_ai(message)

# Запуск бота
async def main():
    logger.info("Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())