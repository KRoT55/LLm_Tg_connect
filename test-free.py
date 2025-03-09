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
import requests
import re
from pydub import AudioSegment
import speech_recognition as sr
import whisper
import torch
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import os
from datetime import datetime, timedelta
import sqlite3
import json
import logging
from cryptography.fernet import Fernet
import requests
import re
from pydub import AudioSegment
from langdetect import detect

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

# Фильтр для обработки эмодзи в логах (без удаления кириллицы)
class EmojiFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'msg'):
            try:
                # Убираем только эмодзи, оставляя кириллицу
                record.msg = re.sub(r'[^\w\s,.!?а-яА-Я]', '', str(record.msg))
            except:
                pass
        return True

# Применяем фильтр только к StreamHandler (чтобы не портить файловые логи)
for handler in logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.addFilter(EmojiFilter())

# Загрузка переменных окружения
load_dotenv()

# Получаем ключи API из переменных окружения
API_TOKEN = os.getenv('API_TOKEN')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')  # Ключ для шифрования
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.getenv('PAYPAL_SECRET')
NOWPAYMENTS_API_KEY = os.getenv('NOWPAYMENTS_API_KEY')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')  # Для Hugging Face API
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')  # По умолчанию localhost
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY')  # Для Gemini API
SPEECH_RECOGNITION_API_KEY = os.getenv('SPEECH_RECOGNITION_API_KEY')

# Инициализация Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация шифрования
cipher_suite = Fernet(ENCRYPTION_KEY.encode())
# Загрузка модели Whisper
def load_whisper_model():
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"CUDA доступна, устройство: {device_name}")
        device = "cuda"
    else:
        logger.info("CUDA не доступна, будет использоваться CPU.")
        device = "cpu"

    model = whisper.load_model("large-v3").to(device)
    logger.info(f"Модель Whisper загружена на: {device}")
    return model

whisper_model = load_whisper_model()

# Системный промпт для ИИ
system_prompt = """
Ты — профессиональный AI-консультант. Всегда отвечай на языке запроса - если русский - то русский, если украинский - украинский, если английский - английский. Твоя задача — давать подробные, информативные и структурированные ответы.

1. ФОРМАТ ОТВЕТА:
   - Используй четкие заголовки и подзаголовки для разделения информации.
   - Если информация логически разделяется на категории, используй списки (маркированные или нумерованные).
   - Избегай сложных таблиц в Markdown, так как они могут некорректно отображаться на мобильных устройствах. Вместо этого используй простые списки или абзацы.

2. СОДЕРЖАНИЕ ОТВЕТА:
   - Давай примеры, разборы, пошаговые инструкции.
   - Упоминай важные нюансы и возможные риски.
   - Если вопрос требует рассуждений, используй аналитику и факты.

3. СТИЛЬ:
   - Используй эмодзи 😊, чтобы делать текст более живым и наглядным.
   - Будь дружелюбным, но профессиональным.
   - Избегай излишне сложных терминов, если это не требуется.
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
                    last_request_time TEXT,  -- Время последнего запроса
                    selected_model TEXT DEFAULT "llama"  -- Выбранная модель по умолчанию
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
            cursor.execute(
                'INSERT INTO users (user_id, requests, paid, chat_history, last_request_time, selected_model) VALUES (?, ?, ?, ?, ?, ?)',
                (user_id, 0, False, self.encrypt_data(json.dumps([])), datetime.now().isoformat(), "llama"))
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

    # Получение выбранной модели
    def get_selected_model(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT selected_model FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else "llama"

    # Обновление выбранной модели
    def update_selected_model(self, user_id, model):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET selected_model = ? WHERE user_id = ?', (model, user_id))
            conn.commit()
            logger.info(f"Выбранная модель пользователя {user_id} обновлена: {model}.")


# Инициализация базы данных
db = UserDatabase()
def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"  # По умолчанию английский, если язык не удалось определить
# Функции для работы с бесплатными LLM API

# 1. Ollama - локальный API для запуска моделей (llama, mistral и др.)
async def ollama_chat(messages, model="llama2"):
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 1000
                }
            },
            stream=True
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


# 2. Hugging Face API - бесплатные конечные точки для различных моделей
async def huggingface_chat(messages, model="mistralai/Mistral-7B-Instruct-v0.2"):
    try:
        # Преобразуем формат сообщений в формат, понятный Hugging Face
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"<s>System: {msg['content']}\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n"

        prompt += "Assistant: "

        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers={
                "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
                "Content-Type": "application/json"
            },
            json={"inputs": prompt, "parameters": {"max_new_tokens": 500}},
            stream=True  # Включаем потоковый режим
        )

        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        # Декодируем строку и парсим JSON
                        json_data = json.loads(line.decode('utf-8'))
                        if isinstance(json_data, list) and len(json_data) > 0:
                            full_response += json_data[0]["generated_text"].split("Assistant: ")[-1]
                    except json.JSONDecodeError:
                        logger.error(f"Ошибка декодирования JSON: {line}")
                        continue

            if full_response:
                return full_response
            else:
                return "Получен пустой ответ от модели."
        else:
            logger.error(f"Ошибка Hugging Face API: {response.status_code}, {response.text}")
            return f"Ошибка Hugging Face API: {response.status_code}"
    except Exception as e:
        logger.error(f"Ошибка при запросе к Hugging Face: {str(e)}")
        return f"Произошла ошибка при обработке запроса: {str(e)}"


# 3. Google Gemini API (ранее бесплатная версия PaLM)
async def gemini_chat(messages):
    try:
        # Преобразуем сообщения в формат для Gemini API
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"System: {msg['content']}\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n\n"

        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": GOOGLE_AI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 1024
                }
            },
            stream=True  # Включаем потоковый режим
        )

        if response.status_code == 200:
            # Собираем весь потоковый ответ в одну строку
            full_response = ""
            for line in response.iter_lines():
                if line:
                    full_response += line.decode('utf-8')

            # Декодируем JSON только после того, как весь ответ собран
            try:
                json_data = json.loads(full_response)
                if 'candidates' in json_data and len(json_data['candidates']) > 0:
                    return json_data['candidates'][0]['content']['parts'][0]['text']
                return "Получен пустой ответ от модели."
            except json.JSONDecodeError:
                logger.error(f"Ошибка декодирования JSON: {full_response[:200]}")  # Логируем первые 200 символов для отладки
                return "Ошибка при обработке ответа от модели."
        else:
            logger.error(f"Ошибка Gemini API: {response.status_code}, {response.text}")
            return f"Ошибка Gemini API: {response.status_code}"
    except Exception as e:
        logger.error(f"Ошибка при запросе к Gemini: {str(e)}")
        return f"Произошла ошибка при обработке запроса: {str(e)}"

# Функция для выбора API в зависимости от настроек пользователя
async def chat_with_ai(message: Message, text_override=None):
    user_id = message.from_user.id
    text = text_override if text_override is not None else message.text
    logger.info(f"Пользователь {user_id} написал: {text}")

    # Определяем язык запроса
    language = detect_language(text)
    logger.info(f"Определен язык запроса: {language}")

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    # Сбрасываем лимит запросов, если прошло больше 24 часов
    db.reset_requests_if_needed(user_id)

    # Проверяем количество использованных запросов
    if db.get_user_requests(user_id) >= 20 and not db.check_payment(user_id):  # Лимит 20 запросов
        await message.answer(
            "❌ Вы исчерпали лимит бесплатных запросов на сегодня. Пожалуйста, оплатите подписку для продолжения.")
        logger.info(f"Пользователь {user_id} исчерпал лимит запросов.")
        await generate_payment_token(message)
        return

    # Получаем историю чата
    chat_history = db.get_chat_history(user_id)

    # Если это первое сообщение, добавляем системный промпт
    if not chat_history:
        chat_history.append({"role": "system", "content": system_prompt})

    # Добавляем новое сообщение пользователя в историю
    chat_history.append({"role": "user", "content": text})

    # Получаем выбранную модель пользователя
    selected_model = db.get_selected_model(user_id)

    try:
        await message.answer("⏳ Думаю...")
        logger.info(f"Бот думает над ответом для пользователя {user_id} с моделью {selected_model}.")

        # Ограничиваем историю чата, чтобы не превысить лимит токенов
        if len(chat_history) > 10:  # Если история больше 10 сообщений
            # Сохраняем системный промпт и последние N сообщений
            limited_history = [chat_history[0]] + chat_history[-9:]
        else:
            limited_history = chat_history

        # Добавляем инструкцию о языке ответа
        if language == "ru":
            limited_history.append({"role": "system", "content": "Отвечай на русском языке."})
        elif language == "uk":
            limited_history.append({"role": "system", "content": "Відповідай українською мовою."})
        else:
            limited_history.append({"role": "system", "content": "Respond in English."})

        reply = await chat_with_ai(limited_history, selected_model)

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


# Чат с моделью
async def chat_with_ai(message: Message, text_override=None):
    user_id = message.from_user.id
    text = text_override if text_override is not None else message.text
    logger.info(f"Пользователь {user_id} написал: {text}")

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    # Сбрасываем лимит запросов, если прошло больше 24 часов
    db.reset_requests_if_needed(user_id)

    # Проверяем количество использованных запросов
    if db.get_user_requests(user_id) >= 20 and not db.check_payment(user_id):  # Лимит 20 запросов
        await message.answer(
            "❌ Вы исчерпали лимит бесплатных запросов на сегодня. Пожалуйста, оплатите подписку для продолжения.")
        logger.info(f"Пользователь {user_id} исчерпал лимит запросов.")
        await generate_payment_token(message)
        return

    # Получаем историю чата
    chat_history = db.get_chat_history(user_id)

    # Если это первое сообщение, добавляем системный промпт
    if not chat_history:
        chat_history.append({"role": "system", "content": system_prompt})

    # Добавляем новое сообщение пользователя в историю
    chat_history.append({"role": "user", "content": text})  # Используем text вместо message.text

    # Получаем выбранную модель пользователя
    selected_model = db.get_selected_model(user_id)

    try:
        await message.answer("⏳ Думаю...")
        logger.info(f"Бот думает над ответом для пользователя {user_id} с моделью {selected_model}.")

        # Ограничиваем историю чата, чтобы не превысить лимит токенов
        if len(chat_history) > 10:  # Если история больше 10 сообщений
            # Сохраняем системный промпт и последние N сообщений
            limited_history = [chat_history[0]] + chat_history[-9:]
        else:
            limited_history = chat_history

        reply = await chat_with_ai(limited_history, selected_model)

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


@dp.message(lambda message: message.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} отправил фото.")

    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_path}"

    response = requests.get(file_url)
    image_path = f"temp_image_{user_id}.jpg"
    with open(image_path, "wb") as f:
        f.write(response.content)

    await message.answer("✅ Изображение получено! Обрабатываю...")

    # 👉 1. Распознаем текст на изображении (OCR)
    text = extract_text_from_image(image_path)
    if text.strip():
        await message.answer(f"📄 Распознанный текст:\n{text}")
    else:
        text = "На изображении нет явного текста."

    # 👉 2. Анализируем изображение через AI
    ai_description = classify_image_huggingface(image_path)

    # Объединяем описание
    full_description = f"На изображении: {ai_description}\n{'' if text == 'На изображении нет явного текста.' else 'Текст: ' + text}"

    await message.answer(f"🖼️ AI-анализ изображения:\n{full_description}")

    # 👉 3. Отправляем в LLM
    await chat_with_ai(message, text_override=full_description)


# Обработчик команды /start
@dp.message(lambda message: message.text == "/start")
async def cmd_start(message: Message):
    user_id = message.from_user.id

    # Если пользователя нет в базе данных, создаем его
    if not db.user_exists(user_id):
        db.create_user(user_id)

    await message.answer(
        "👋 Привет! Я AI-консультант на базе бесплатных языковых моделей. "
        "Вы можете задать мне вопросы или попросить совета. "
        "\n\nВы можете выбрать предпочитаемую модель с помощью команды /model"
    )


# Обработчик команды /model
@dp.message(lambda message: message.text == "/model")
async def cmd_model(message: Message):
    await message.answer(
        "Выберите предпочитаемую модель:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Llama 2")],
                [types.KeyboardButton(text="Mistral")],
                [types.KeyboardButton(text="Hugging Face")],
                [types.KeyboardButton(text="Gemini")]
            ],
            resize_keyboard=True
        )
    )


# Обработчик выбора модели
@dp.message(lambda message: message.text in ["Llama 2", "Mistral", "Hugging Face", "Gemini"])
async def handle_model_selection(message: Message):
    user_id = message.from_user.id
    model_name = message.text.lower()

    # Преобразуем название в id модели
    model_id = "llama"  # По умолчанию
    if model_name == "llama 2":
        model_id = "llama"
    elif model_name == "mistral":
        model_id = "mistral"
    elif model_name == "hugging face":
        model_id = "huggingface"
    elif model_name == "gemini":
        model_id = "gemini"

    # Обновляем выбранную модель в базе данных
    db.update_selected_model(user_id, model_id)

    await message.answer(
        f"✅ Вы выбрали модель: {message.text}",
        reply_markup=types.ReplyKeyboardRemove()
    )


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


# Обработчик команды /help
@dp.message(lambda message: message.text == "/help")
async def cmd_help(message: Message):
    await message.answer(
        "🔍 Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/model - Выбрать модель AI\n"
        "/clear - Очистить историю чата\n"
        "/help - Показать эту справку\n\n"
        "ℹ️ Вы можете использовать до 20 бесплатных запросов в день. "
        "Для неограниченного использования приобретите подписку."
    )


# Обработчик команды /clear
@dp.message(lambda message: message.text == "/clear")
async def cmd_clear(message: Message):
    user_id = message.from_user.id

    # Создаем новую историю только с системным промптом
    new_history = [{"role": "system", "content": system_prompt}]
    db.update_chat_history(user_id, new_history)

    await message.answer("🧹 История чата очищена!")


# Обработчик аудиосообщений
@dp.message(lambda message: message.voice)
async def handle_voice_message(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} отправил аудиосообщение.")

    # Скачиваем аудиофайл
    file_info = await bot.get_file(message.voice.file_id)
    file_path = file_info.file_path
    file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_path}"

    # Скачиваем файл
    response = requests.get(file_url)
    with open("temp_audio.ogg", "wb") as f:
        f.write(response.content)

    # Конвертируем аудио в WAV (Whisper поддерживает и .ogg, но для надежности конвертируем)
    audio = AudioSegment.from_file("temp_audio.ogg")
    audio.export("temp_audio.wav", format="wav")

    # Распознаем речь с помощью Whisper
    try:
        result = whisper_model.transcribe("temp_audio.wav", verbose=True)
        text = result.get("text", "").strip()  # Берем текст и убираем лишние пробелы
        if not text:
            await message.answer("❌ Whisper не смог распознать текст. Попробуйте говорить четче.")
            return

        logger.info(f"Распознанный текст: {text}")

        await message.answer(f"🎤 Распознанный текст: {text}")

        # Обрабатываем текст как обычное сообщение
        await chat_with_ai(message, text_override=text)
        logger.info(f"Текст, переданный в chat_with_ai(): {text}")

    except Exception as e:
        logger.error(f"Ошибка при распознавании речи: {e}")
        await message.answer("❌ Не удалось распознать речь.")

# Обработчик всех остальных сообщений
@dp.message()
async def handle_message(message: Message):
    # Проверяем, есть ли в сообщении текст
    if message.text:
        # Проверяем, не является ли сообщение командой
        if message.text.startswith("/"):
            await message.answer("❓ Неизвестная команда. Используйте /help для списка команд.")
            return

        # Обрабатываем текстовое сообщение
        await chat_with_ai(message)
    else:
        # Если это не текстовое сообщение, игнорируем или обрабатываем другие типы сообщений
        await message.answer("Я могу обрабатывать только текстовые и голосовые сообщения.")

# Запуск бота
async def main():
    logger.info("Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())