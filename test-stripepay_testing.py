import openai
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import stripe
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import sqlite3
import json
import logging
from cryptography.fernet import Fernet  # Для шифрования данных
import requests  # Для работы с API PayPal и NowPayments

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
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')  # Ключ для шифрования
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.getenv('PAYPAL_SECRET')
NOWPAYMENTS_API_KEY = os.getenv('NOWPAYMENTS_API_KEY')

# Инициализация Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Инициализация бота и OpenAI
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация клиента OpenAI
client = openai.Client(api_key=OPENAI_API_KEY)

# Инициализация шифрования
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# Системный промпт для GPT
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
                    paid BOOLEAN,
                    chat_history TEXT,  -- Зашифрованная история чата
                    last_request_time TEXT  -- Время последнего запроса
                )
            ''')
            conn.commit()
            logger.info("База данных и таблица созданы или уже существуют.")

    # Шифрование данных
    def encrypt_data(self, data):
        return cipher_suite.encrypt(data.encode()).decode()

    # Дешифрование данных
    def decrypt_data(self, data):
        return cipher_suite.decrypt(data.encode()).decode()

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
            cursor.execute('INSERT INTO users (user_id, requests, paid, chat_history, last_request_time) VALUES (?, ?, ?, ?, ?)',
                           (user_id, 0, False, self.encrypt_data(json.dumps([])), datetime.now().isoformat()))
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
            if result:
                return json.loads(self.decrypt_data(result[0]))
            return []

    # Обновление истории чатов пользователя
    def update_chat_history(self, user_id, chat_history):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET chat_history = ? WHERE user_id = ?',
                           (self.encrypt_data(json.dumps(chat_history)), user_id))
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

# Создание платежа через PayPal
def create_paypal_payment():
    try:
        # Получаем токен доступа PayPal
        auth_response = requests.post(
            "https://api.paypal.com/v1/oauth2/token",
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={"grant_type": "client_credentials"}
        )
        access_token = auth_response.json()["access_token"]

        # Создаем платеж
        payment_response = requests.post(
            "https://api.paypal.com/v1/payments/payment",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json={
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "transactions": [{
                    "amount": {"total": "10.00", "currency": "USD"},
                    "description": "Оплата подписки"
                }],
                "redirect_urls": {
                    "return_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel"
                }
            }
        )
        return payment_response.json()["links"][1]["href"]  # Ссылка на оплату
    except Exception as e:
        logger.error(f"Ошибка при создании платежа PayPal: {str(e)}")
        return None

# Создание платежа через NowPayments (криптовалюта)
def create_nowpayments_invoice():
    try:
        response = requests.post(
            "https://api.nowpayments.io/v1/invoice",
            headers={"x-api-key": NOWPAYMENTS_API_KEY},
            json={
                "price_amount": 10,
                "price_currency": "usd",
                "order_id": "subscription_123",
                "order_description": "Оплата подписки",
                "ipn_callback_url": "https://example.com/callback",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            }
        )
        return response.json()["invoice_url"]  # Ссылка на оплату
    except Exception as e:
        logger.error(f"Ошибка при создании инвойса NowPayments: {str(e)}")
        return None

# Чат с GPT
async def chat_with_gpt(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} написал: {message.text}")

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    # Сбрасываем лимит запросов, если прошло больше 24 часов
    db.reset_requests_if_needed(user_id)

    # Проверяем количество использованных запросов
    if db.get_user_requests(user_id) >= 20:  # Лимит 20 запросов
        await message.answer("❌ Вы исчерпали лимит бесплатных запросов на сегодня. Пожалуйста, оплатите подписку для продолжения.")
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
            model="gpt-4-turbo",  # Более мощная модель
            messages=[{"role": "system", "content": system_prompt}, *chat_history],
            temperature=0.7,  # Креативность
            max_tokens=1024,  # Длина ответа
            top_p=0.9,  # Баланс между детерминированностью и креативностью
            frequency_penalty=0.3,  # Меньше повторений
            presence_penalty=0.6  # Больше разнообразия
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
    # Предлагаем пользователю выбрать метод оплаты
    await message.answer("Выберите метод оплаты:", reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Stripe")],
            [types.KeyboardButton(text="PayPal")],
            [types.KeyboardButton(text="Криптовалюта (NowPayments)")]
        ],
        resize_keyboard=True
    ))

# Обработчик выбора метода оплаты
@dp.message(lambda message: message.text in ["Stripe", "PayPal", "Криптовалюта (NowPayments)"])
async def handle_payment_method(message: Message):
    user_id = message.from_user.id
    method = message.text

    if method == "Stripe":
        client_secret = create_payment_intent()
        if client_secret:
            await message.answer(f"Для оплаты используйте ссылку или QR код для {client_secret}")
        else:
            await message.answer("❌ Не удалось создать платежный запрос.")
    elif method == "PayPal":
        payment_url = create_paypal_payment()
        if payment_url:
            await message.answer(f"Для оплаты используйте ссылку: {payment_url}")
        else:
            await message.answer("❌ Не удалось создать платеж PayPal.")
    elif method == "Криптовалюта (NowPayments)":
        invoice_url = create_nowpayments_invoice()
        if invoice_url:
            await message.answer(f"Для оплаты используйте ссылку: {invoice_url}")
        else:
            await message.answer("❌ Не удалось создать инвойс NowPayments.")

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