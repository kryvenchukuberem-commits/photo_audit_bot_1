import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот працює ✅")

def main():
    application = Application.builder().token(8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
