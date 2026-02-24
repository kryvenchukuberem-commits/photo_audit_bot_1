import os
import sqlite3
import hashlib
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = os.getenv("YOUR_TOKEN_HERE")

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
        "Вітаю! Ви можете надіслати до 2 фото на місяць."
        "Повторні або старі фото не приймаються."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    current_month = get_current_month()

    # Перевірка: скільки фото вже надіслав користувач цього місяця
    cursor.execute(
        "SELECT COUNT(*) FROM photos WHERE user_id=? AND month=?",
        (user_id, current_month)
    )
    photo_count = cursor.fetchone()[0]

    if photo_count >= 2:
        await update.message.reply_text("❌ Ви вже надіслали 2 фото цього місяця.")
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

    await update.message.reply_text(
        f"✅ Фото прийнято! Ви надіслали {photo_count + 1} з 2 можливих фото цього місяця."
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
