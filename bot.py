import os
import sqlite3
import hashlib
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

# --- Database setup ---
conn = sqlite3.connect("photos.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS photos (
    user_id INTEGER,
    username TEXT,
    photo_hash TEXT,
    month TEXT,
    date TEXT
)
""")
conn.commit()

def get_current_month():
    return datetime.now().strftime("%Y-%m")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Вітаю! Надішліть одне актуальне фото.\n"
        "Повторні або старі фото не приймаються."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    current_month = get_current_month()

    # Перевірка: чи вже здавав фото цього місяця
    cursor.execute("SELECT * FROM photos WHERE user_id=? AND month=?", (user_id, current_month))
    if cursor.fetchone():
        await update.message.reply_text("❌ Ви вже здали фото цього місяця.")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    # Хеш фото
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Перевірка повтору
    cursor.execute("SELECT * FROM photos WHERE photo_hash=?", (file_hash,))
    if cursor.fetchone():
        await update.message.reply_text("❌ Це фото вже надсилалось раніше.")
        os.remove(file_path)
        return

    # Зберігаємо
    cursor.execute(
        "INSERT INTO photos VALUES (?, ?, ?, ?, ?)",
        (user_id, username, file_hash, current_month, datetime.now().isoformat())
    )
    conn.commit()

    os.remove(file_path)

    await update.message.reply_text("✅ Фото прийнято. Дякуємо!")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

from telegram.ext import Application

application = Application.builder().token("8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg
").build()
