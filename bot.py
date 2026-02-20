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
        "Вітаю! Надішліть фото.\n"
        "Повторні фото не приймаються."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username
    current_month = get_current_month()

    # Отримуємо найбільшу версію фото
    photo = update.message.photo[-1]
    file = await photo.get_file()

    # Отримуємо байти фото
    file_bytes = await file.download_as_bytearray()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Перевірка повторного фото
    cursor.execute("SELECT 1 FROM photos WHERE photo_hash=?", (file_hash,))
    if cursor.fetchone():
        await update.message.reply_text("❌ Це фото вже надсилалось раніше.")
        return

    # Зберігаємо фото
    cursor.execute(
        "INSERT INTO photos VALUES (?, ?, ?, ?, ?)",
        (user_id, username, file_hash, current_month, datetime.now().isoformat())
    )
    conn.commit()

    await update.message.reply_text("✅ Фото прийнято. Дякуємо!")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
