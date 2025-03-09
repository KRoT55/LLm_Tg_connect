import openai
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
import requests
import json
from datetime import datetime

# 🔹 Вставь свои ключи
API_TOKEN =
OPENAI_API_KEY =
NOWPAYMENTS_API_KEY =




# 🔹 Инициализация бота и OpenAI
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
client = openai.Client(api_key=OPENAI_API_KEY)

# 🔹 Проверка транзакции
def check_payment(invoice_id):
    url = f'https://api.nowpayments.io/v1/invoice/{invoice_id}'
    headers = {'Authorization': f'Bearer {NOWPAYMENTS_API_KEY}'}
    response = requests.get(url, headers=headers)
    data = response.json()

    # Если статус "paid" — подтверждаем оплату
    return data['status'] == 'paid'

# 🔹 Чат с GPT
async def chat_with_gpt(message: Message):
    user_id = message.from_user.id

    # Проверяем, оплатил ли пользователь
    if not check_payment(user_id):  # Здесь будет проверка статуса транзакции
        await message.answer("⚠ Вы не оплатили подписку! Пожалуйста, произведите оплату.")
        return

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

# 🔹 Обработчик сообщений
@dp.message()
async def handle_message(message: Message):
    await chat_with_gpt(message)

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

