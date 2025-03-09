
import openai
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message

# 🔹 Вставь свои ключи
API_TOKEN = ""
OPENAI_API_KEY = ""


# 🔹 Инициализация бота и OpenAI клиента
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
client = openai.Client(api_key=OPENAI_API_KEY)  # Новый клиент OpenAI

async def chat_with_gpt(message: Message):
    try:
        await message.answer("⏳ Думаю...")  # Показываем, что бот обрабатывает запрос

        # Новый вызов OpenAI API
        response = client.chat.completions.create(
            model="gpt-4-turbo",  # Можно заменить на "gpt-3.5-turbo"
            messages=[{"role": "user", "content": message.text}]
        )

        reply = response.choices[0].message.content
        await message.answer(reply)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")  # Показываем ошибку пользователю

# Обработчик сообщений
@dp.message()
async def handle_message(message: Message):
    await chat_with_gpt(message)

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
