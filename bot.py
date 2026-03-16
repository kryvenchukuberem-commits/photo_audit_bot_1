import hashlib
import io
import requests
from datetime import datetime

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters


TOKEN = "8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg"
ADMIN_ID = 1060311805

SCRIPT_URL = "1A5nSVtca1DK6wKnmSZC79LMcM5e0_FBxJINGcxYqjDY"


def normalize_phone(phone):
    return phone.replace(" ", "").replace("-", "")


def save_to_sheet(data):

    try:
        requests.post(SCRIPT_URL, json=data)
    except:
        print("Помилка запису в таблицю")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    button = KeyboardButton("Поділитися номером", request_contact=True)

    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True)

    await update.message.reply_text(
        "Натисніть кнопку щоб поділитися номером телефону",
        reply_markup=keyboard
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.message.from_user
    contact = update.message.contact

    phone = normalize_phone(contact.phone_number)

    data = {
        "name": user.first_name,
        "phone": phone,
        "username": user.username or "",
        "telegram_id": user.id,
        "last_photo": "",
        "photo_status": "",
        "photo_hash": ""
    }

    save_to_sheet(data)

    await update.message.reply_text("✅ Ви додані в систему")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.message.from_user
    username = user.username or ""

    photo = update.message.photo[-1]

    file = await context.bot.get_file(photo.file_id)

    bio = io.BytesIO()

    await file.download_to_memory(out=bio)

    bio.seek(0)

    file_hash = hashlib.sha256(bio.read()).hexdigest()

    bio.seek(0)

    data = {
        "name": user.first_name,
        "phone": "",
        "username": username,
        "telegram_id": user.id,
        "last_photo": datetime.now().isoformat(),
        "photo_status": "+",
        "photo_hash": file_hash
    }

    save_to_sheet(data)

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=bio,
        caption=f"📸 Фото від @{username} | ID:{user.id}"
    )

    await update.message.reply_text("✅ Фото прийнято")


async def reminder(context: ContextTypes.DEFAULT_TYPE):

    print("Reminder check")


def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.job_queue.run_repeating(reminder, interval=86400, first=10)

    print("Bot started")

    app.run_polling()


if __name__ == "__main__":
    main()
