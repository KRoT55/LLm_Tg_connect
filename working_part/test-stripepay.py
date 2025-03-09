import openai
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
import stripe
from datetime import datetime

# Вставь свои ключи
API_TOKEN = ""
OPENAI_API_KEY = ""
STRIPE_SECRET_KEY = ""  # Секретный ключ Stripe

# Инициализация Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Инициализация бота и OpenAI
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация клиента OpenAI
client = openai.Client(api_key=OPENAI_API_KEY)

# Словарь для хранения количества запросов пользователей
user_requests = {}

# Генерация клиентского токена для Apple Pay/Google Pay
def create_payment_intent():
    try:
        # Создаем платежный запрос
        intent = stripe.PaymentIntent.create(
            amount=1000,  # Стоимость в центах, 1000 = $10
            currency="usd",
            payment_method_types=["card", "apple_pay", "google_pay"],
        )
        return intent.client_secret
    except Exception as e:
        print(f"Ошибка при создании платежа: {str(e)}")
        return None

# Чат с GPT
async def chat_with_gpt(message: Message):
    user_id = message.from_user.id

    # Проверяем, оплатил ли пользователь
    if not check_payment(user_id):
        await message.answer("⚠ Вы не оплатили подписку! Пожалуйста, произведите оплату.")
        return

    # Проверяем количество использованных запросов
    if user_requests.get(user_id, 0) >= 10:  # Лимит 10 запросов
        await message.answer("❌ Вы исчерпали лимит бесплатных запросов. Пожалуйста, оплатите подписку для продолжения.")
        await generate_payment_token(message)
        return

    # Увеличиваем счетчик запросов
    user_requests[user_id] = user_requests.get(user_id, 0) + 1

    try:
        await message.answer("⏳ Думаю...")
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": message.text}]
        )
        reply = response.choices[0].message.content
        await message.answer(reply)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Проверка оплаты (условно)
def check_payment(user_id):
    # В реальной ситуации тут должно быть обращение к Stripe API
    # для проверки состояния платежа.
    return True  # Для демонстрации всегда возвращаем True

# Обработчик сообщений
@dp.message()
async def handle_message(message: Message):
    await chat_with_gpt(message)

# Генерация токена для платежа
async def generate_payment_token(message: Message):
    client_secret = create_payment_intent()
    if client_secret:
        await message.answer(f"Для оплаты используйте ссылку или QR код для {client_secret}")
    else:
        await message.answer("❌ Не удалось создать платежный запрос.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
