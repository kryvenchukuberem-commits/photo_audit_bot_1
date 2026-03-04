import os
import json
import hashlib
import io
from datetime import datetime

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials

# ================== НАЛАШТУВАННЯ ==================

TOKEN = "8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg"
ADMIN_ID = 1060311805
SPREADSHEET_ID = "1A5nSVtca1DK6wKnmSZC79LMcM5e0_FBxJINGcxYqjDY"

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ================== GOOGLE SHEETS ПІДКЛЮЧЕННЯ ==================

json_creds_str = os.environ.get("GOOGLE_CREDENTIALS")

if not json_creds_str:
    raise Exception("Не знайдено змінну середовища GOOGLE_CREDENTIALS")

json_creds = json.loads(json_creds_str)
creds = Credentials.from_service_account_info(json_creds, scopes=scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

print("✅ Google Sheets підключено")

# ================== ДОПОМІЖНІ ==================

def get_headers():
    return sheet.row_values(1)

def get_col(name):
    return get_headers().index(name) + 1

def get_all():
    return sheet.get_all_records()

def normalize_phone(phone):
    return phone.replace(" ", "").replace("-", "")

# ================== /START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton("Поділитися номером", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True)

    await update.message.reply_text(
        "Натисніть кнопку щоб поділитися номером телефону",
        reply_markup=keyboard
    )

# ================== ОБРОБКА КОНТАКТУ ==================

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    contact = update.message.contact

    phone = normalize_phone(contact.phone_number)
    user_id = user.id
    username = user.username or ""
    name = user.first_name or ""

    records = get_all()

    for i, row in enumerate(records, start=2):
        if normalize_phone(str(row["телефон"])) == phone:
            sheet.update_cell(i, get_col("телеграм_ник"), username)
            sheet.update_cell(i, get_col("айді"), user_id)
            await update.message.reply_text("✅ Реєстрація оновлена")
            return

    sheet.append_row([name, phone, username, user_id, "", "", ""])
    await update.message.reply_text("✅ Ви додані в систему")

# ================== ОБРОБКА ФОТО ==================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or ""
    name = user.first_name or ""

    records = get_all()
    user_row = None

    for i, row in enumerate(records, start=2):
        if str(row["айді"]) == str(user_id):
            user_row = i
            break

    if not user_row:
        sheet.append_row([name, "", username, user_id, "", "", ""])
        user_row = len(records) + 2

    current_month = datetime.now().strftime("%Y-%m")
    count = 0

    for row in records:
        if str(row["айді"]) == str(user_id):
            if row["дата_останнього_фото"] and row["дата_останнього_фото"].startswith(current_month):
                count += 1

    if count >= 2:
        await update.message.reply_text("❌ Ліміт 2 фото на місяць")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)

    file_hash = hashlib.sha256(bio.read()).hexdigest()
    bio.seek(0)

    for row in records:
        if row["хеш_фото"] == file_hash:
            await update.message.reply_text("❌ Фото вже надсилалось")
            return

    sheet.update_cell(user_row, get_col("дата_останнього_фото"), datetime.now().isoformat())
    sheet.update_cell(user_row, get_col("статус_фото"), "+")
    sheet.update_cell(user_row, get_col("хеш_фото"), file_hash)

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=bio,
        caption=f"📸 Фото від @{username} | ID: {user_id}"
    )

    await update.message.reply_text("✅ Фото прийнято")

# ================== НАГАДУВАННЯ ==================

async def reminder(context: ContextTypes.DEFAULT_TYPE):
    records = get_all()
    today = datetime.now()

    for row in records:
        if row["айді"]:
            telegram_id = int(row["айді"])
            last_photo = row["дата_останнього_фото"]

            if not last_photo:
                try:
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text="📢 Нагадування: надішліть фото"
                    )
                except:
                    pass
                continue

            try:
                last_date = datetime.fromisoformat(last_photo)
            except:
                continue

            delta_days = (today - last_date).days

            if delta_days >= 30:
                try:
                    await context.bot.send_message(
                        chat_id=telegram_id,
                        text="📢 Нагадування: надішліть нове фото"
                    )
                except:
                    pass

# ================== ЗАПУСК ==================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.job_queue.run_repeating(reminder, interval=86400, first=10)

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
