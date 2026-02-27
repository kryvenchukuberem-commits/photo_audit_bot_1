import os
import hashlib
import asyncio
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import gspread
from google.oauth2.service_account import Credentials

# ------------------- Налаштування -------------------
TOKEN = "8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg"
ADMIN_ID = 1060311805
SPREADSHEET_ID = "1A5nSVtca1DK6wKnmSZC79LMcM5e0_FBxJINGcxYqjDY"

# ------------------- Google підключення -------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ------------------- Назви колонок -------------------
COLS = {
    "name": "ім'я_клінера",               # cleaner_name
    "phone": "телефон",                   # phone
    "username": "телеграм_ник",           # username
    "user_id": "айді",                    # user_id
    "last_photo_date": "дата_останнього_фото",  # last_photo_date
    "photo_status": "статус_фото",       # photo_status
    "last_photo_hash": "хеш_фото"        # last_photo_hash
}

# ------------------- Допоміжні функції -------------------
def normalize_phone(phone):
    return phone.replace(" ", "").replace("-", "")

def get_all_records():
    return sheet.get_all_records()

def get_col_index(name):
    headers = sheet.row_values(1)
    return headers.index(COLS[name]) + 1

def add_user_if_not_exists(user_id, username, phone="", name=""):
    records = get_all_records()
    for index, row in enumerate(records, start=2):
        if row.get(COLS["user_id"]) == user_id:
            return index  # користувач вже є
    # Якщо немає, додаємо новий рядок
    sheet.append_row([name, phone, username, user_id, "", "", ""])
    return len(records) + 2

# ------------------- START -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton("Поділитися номером", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Натисніть кнопку щоб поділитися номером телефону.",
        reply_markup=keyboard
    )

# ------------------- Реєстрація через контакт -------------------
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    contact = update.message.contact

    phone = normalize_phone(contact.phone_number)
    user_id = user.id
    username = user.username or ""
    name = user.first_name or ""

    index = None
    records = get_all_records()
    # перевіряємо чи є користувач за телефоном
    for idx, row in enumerate(records, start=2):
        table_phone = normalize_phone(str(row[COLS["phone"]]))
        if table_phone == phone:
            sheet.update_cell(idx, get_col_index("username"), username)
            sheet.update_cell(idx, get_col_index("user_id"), user_id)
            index = idx
            break

    if not index:
        # додаємо нового користувача
        index = add_user_if_not_exists(user_id, username, phone, name)

    await update.message.reply_text("✅ Реєстрація успішна! Тепер можете надсилати фото.")

# ------------------- Обробка фото -------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or ""
    name = user.first_name or ""

    # додаємо користувача якщо його немає
    user_row_index = add_user_if_not_exists(user_id, username, "", name)

    records = get_all_records()
    row = records[user_row_index - 2]

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Перевірка дубля
    if row.get(COLS["last_photo_hash"]) == file_hash:
        os.remove(file_path)
        await update.message.reply_text("❌ Це фото вже надсилалось раніше.")
        return

    # Оновлюємо таблицю
    sheet.update_cell(user_row_index, get_col_index("last_photo_date"), datetime.now().isoformat())
    sheet.update_cell(user_row_index, get_col_index("photo_status"), "+")
    sheet.update_cell(user_row_index, get_col_index("last_photo_hash"), file_hash)

    # Відправка адміну
    try:
        with open(file_path, "rb") as f:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=f,
                caption=f"📸 Фото від @{username}"
            )
    except Exception as e:
        print("Помилка надсилання адміну:", e)

    os.remove(file_path)
    await update.message.reply_text("✅ Фото прийнято.")

# ------------------- Персональні нагадування -------------------
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    records = get_all_records()
    today = datetime.now()

    for row in records:
        uid = row.get(COLS["user_id"])
        last_date_str = row.get(COLS["last_photo_date"])
        if uid and last_date_str:
            last_date = datetime.fromisoformat(last_date_str)
            days_passed = (today - last_date).days
            if days_passed >= 30:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="📢 Будь ласка, надішліть нове фото."
                    )
                except:
                    pass

# ------------------- Очищення старих фото через 60 днів -------------------
async def clean_old_photo_data():
    records = get_all_records()
    today = datetime.now()

    for index, row in enumerate(records, start=2):
        last_date_str = row.get(COLS["last_photo_date"])
        if last_date_str:
            last_date = datetime.fromisoformat(last_date_str)
            if (today - last_date).days > 60:
                # очищаємо тільки фото-дані
                sheet.update_cell(index, get_col_index("last_photo_date"), "")
                sheet.update_cell(index, get_col_index("photo_status"), "")
                sheet.update_cell(index, get_col_index("last_photo_hash"), "")

# ------------------- Запуск -------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(send_reminders(app)), 'interval', hours=24)
    scheduler.add_job(lambda: asyncio.create_task(clean_old_photo_data()), 'interval', hours=24)
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()
