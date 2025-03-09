import openai
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import stripe
from datetime import datetime
import os
from dotenv import load_dotenv
import sqlite3
import json
import logging  # Для логирования

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получаем ключи API из переменных окружения
API_TOKEN = os.getenv('API_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')

# Инициализация Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Инициализация бота и OpenAI
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация клиента OpenAI
client = openai.Client(api_key=OPENAI_API_KEY)

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
                    paid BOOLEAN,
                    chat_history TEXT
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
            cursor.execute('INSERT INTO users (user_id, requests, paid, chat_history) VALUES (?, ?, ?, ?)',
                           (user_id, 0, False, json.dumps([])))  # Начинаем с пустой истории
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
            cursor.execute('UPDATE users SET requests = ? WHERE user_id = ?', (requests, user_id))
            conn.commit()
            logger.info(f"Запросы пользователя {user_id} увеличены до {requests}.")

    # Получение статуса оплаты
    def check_payment(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT paid FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else False

    # Обновление статуса оплаты
    def update_payment_status(self, user_id, paid):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET paid = ? WHERE user_id = ?', (paid, user_id))
            conn.commit()
            logger.info(f"Статус оплаты пользователя {user_id} обновлен: {paid}.")

    # Получение истории чатов пользователя
    def get_chat_history(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT chat_history FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return json.loads(result[0]) if result else []

    # Обновление истории чатов пользователя
    def update_chat_history(self, user_id, chat_history):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET chat_history = ? WHERE user_id = ?', (json.dumps(chat_history), user_id))
            conn.commit()
            logger.info(f"История чата пользователя {user_id} обновлена.")


# Инициализация базы данных
db = UserDatabase()

# Генерация клиентского токена для Apple Pay/Google Pay
def create_payment_intent():
    try:
        # Создаем платежный запрос
        intent = stripe.PaymentIntent.create(
            amount=1000,  # Стоимость в центах, 1000 = $10
            currency="usd",
            payment_method_types=["card", "apple_pay", "google_pay"],
        )
        logger.info("Платежный запрос создан.")
        return intent.client_secret
    except Exception as e:
        logger.error(f"Ошибка при создании платежа: {str(e)}")
        return None

# Чат с GPT
async def chat_with_gpt(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} написал: {message.text}")

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    # Проверяем, оплатил ли пользователь
    if not db.check_payment(user_id):
        await message.answer("⚠ Вы не оплатили подписку! Пожалуйста, произведите оплату.")
        logger.info(f"Пользователь {user_id} не оплатил подписку.")
        return

    # Проверяем количество использованных запросов
    if db.get_user_requests(user_id) >= 100:  # Лимит 100 запросов
        await message.answer("❌ Вы исчерпали лимит бесплатных запросов. Пожалуйста, оплатите подписку для продолжения.")
        logger.info(f"Пользователь {user_id} исчерпал лимит запросов.")
        await generate_payment_token(message)
        return

    # Получаем историю чата
    chat_history = db.get_chat_history(user_id)

    # Добавляем новое сообщение пользователя в историю
    chat_history.append({"role": "user", "content": message.text})

    try:
        await message.answer("⏳ Думаю...")
        logger.info(f"Бот думает над ответом для пользователя {user_id}.")
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=chat_history  # Передаем всю историю
        )
        reply = response.choices[0].message.content
        await message.answer(reply)
        logger.info(f"Бот ответил пользователю {user_id}: {reply}")

        # Добавляем ответ GPT в историю
        chat_history.append({"role": "assistant", "content": reply})
        db.update_chat_history(user_id, chat_history)

        # Увеличиваем счетчик запросов
        db.increment_user_requests(user_id)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка при обработке запроса пользователя {user_id}: {str(e)}")

# Генерация токена для платежа
async def generate_payment_token(message: Message):
    client_secret = create_payment_intent()
    if client_secret:
        await message.answer(f"Для оплаты используйте ссылку или QR код для {client_secret}")
        logger.info(f"Платежный токен создан для пользователя {message.from_user.id}.")
    else:
        await message.answer("❌ Не удалось создать платежный запрос.")
        logger.error(f"Не удалось создать платежный запрос для пользователя {message.from_user.id}.")

# Обработчик сообщений
@dp.message()
async def handle_message(message: Message):
    await chat_with_gpt(message)

# Запуск бота
async def main():
    logger.info("Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())