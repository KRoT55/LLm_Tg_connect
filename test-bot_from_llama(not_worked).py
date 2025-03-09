import telegram

TOKEN = ''
bot = telegram.Bot(TOKEN)

def greet(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text='Hello!')

updater = telegram.Updater(token=TOKEN, use_context=True)
updater.dispatcher.add_handler(telegram.CommandHandler('greet', greet))
updater.start_polling()