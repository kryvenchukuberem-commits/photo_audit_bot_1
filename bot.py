import os
import sqlite3
import hashlib
from datetime import datetime
import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# ------------------- Налаштування -------------------
TOKEN = "8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg"
ADMIN_ID = 1060311805


# ------------------- Папка для фото -------------------
os.makedirs("photos", exist_ok=True)


# ------------------- Підключення до бази -------------------
conn = sqlite3.connect("photos.db", check_same_thread=False)
cursor = conn.cursor()

# створення таблиці
cursor.execute("""
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    photo_hash TEXT,
    month TEXT,
    date TEXT,
    verified INTEGER DEFAULT 0,
    reminder_sent INTEGER DEFAULT 0
)
""")
conn.commit()


# ------------------- Допоміжні функції -------------------
def get_current_month():
    return datetime.now().strftime("%Y-%m")


# ------------------- Команди -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Вітаю!\n\n"
        "Надішліть своє фото.\n"
        "Ви можете надсилати до 2 фото на місяць.\n"
        "Бот нагадає тим, хто забуде."
    )


# ------------------- Обробка фото -------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.message.from_user
    user_id = user.id
    username = user.username or "unknown"

    current_month = get_current_month()

    # перевірка ліміту
    cursor.execute(
        "SELECT COUNT(*) FROM photos WHERE user_id=? AND month=? AND verified=1",
        (user_id, current_month)
    )

    photo_count = cursor.fetchone()[0]

    if photo_count >= 2:

        await update.message.reply_text(
            "❌ Ви вже надіслали 2 фото цього місяця."
        )

        return

    photo = update.message.photo[-1]

    file = await context.bot.get_file(photo.file_id)

    file_path = f"photos/{photo.file_id}.jpg"

    await file.download_to_drive(file_path)

    # створення хешу
    with open(file_path, "rb") as f:

        file_hash = hashlib.sha256(f.read()).hexdigest()

    # перевірка дублю
    cursor.execute(
        "SELECT id FROM photos WHERE photo_hash=?",
        (file_hash,)
    )

    if cursor.fetchone():

        os.remove(file_path)

        await update.message.reply_text(
            "❌ Це фото вже надсилалось раніше."
        )

        return

    # запис у базу
    cursor.execute(
        """INSERT INTO photos
        (user_id, username, photo_hash, month, date, verified, reminder_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            username,
            file_hash,
            current_month,
            datetime.now().isoformat(),
            1,
            0
        )
    )

    conn.commit()

    # надсилання адміну
    try:

        with open(file_path, "rb") as f:

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=f,
                caption=f"📸 Фото від @{username}\nID: {user_id}"
            )

    except Exception as e:

        print(f"Помилка надсилання адміну: {e}")

    os.remove(file_path)

    await update.message.reply_text(
        f"✅ Фото прийнято!\n"
        f"Використано {photo_count + 1}/2 цього місяця."
    )


# ------------------- Нагадування -------------------
async def send_monthly_reminder(app):

    current_month = get_current_month()

    cursor.execute(
        "SELECT DISTINCT user_id, username FROM photos"
    )

    users = cursor.fetchall()

    for user_id, username in users:

        # чи є фото цього місяця
        cursor.execute(
            "SELECT id FROM photos WHERE user_id=? AND month=? AND verified=1",
            (user_id, current_month)
        )

        has_photo = cursor.fetchone()

        # чи було нагадування
        cursor.execute(
            "SELECT id FROM photos WHERE user_id=? AND month=? AND reminder_sent=1",
            (user_id, current_month)
        )

        reminder_sent = cursor.fetchone()

        if not has_photo and not reminder_sent:

            try:

                await app.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Нагадування @{username}\n"
                         f"Будь ласка надішліть фото за {current_month}"
                )

                cursor.execute(
                    """INSERT INTO photos
                    (user_id, username, photo_hash, month, date, verified, reminder_sent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        username,
                        "",
                        current_month,
                        datetime.now().isoformat(),
                        0,
                        1
                    )
                )

                conn.commit()

            except Exception as e:

                print(f"Не вдалося надіслати {user_id}: {e}")


# ------------------- Запуск бота -------------------
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # планувальник
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        lambda: asyncio.create_task(send_monthly_reminder(app)),
        'cron',
        day=1,
        hour=10,
        minute=0
    )

    scheduler.start()

    print("Bot started...")

    app.run_polling()


if __name__ == "__main__":
    main()
