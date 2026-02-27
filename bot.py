import os
import json
import hashlib
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


# ------------------- ENV -------------------
TOKEN = os.getenv("8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg")
ADMIN_ID = 1060311805
SPREADSHEET_ID = os.getenv("1A5nSVtca1DK6wKnmSZC79LMcM5e0_FBxJINGcxYqjDY")

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1


# ------------------- Допоміжні -------------------

def get_headers():
    return sheet.row_values(1)

def get_col(name):
    return get_headers().index(name) + 1

def get_all():
    return sheet.get_all_records()

def normalize_phone(phone):
    return phone.replace(" ", "").replace("-", "")


# ------------------- START -------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton("Поділитися номером", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True)

    await update.message.reply_text(
        "Натисніть кнопку щоб поділитися номером телефону",
        reply_markup=keyboard
    )


# ------------------- КОНТАКТ -------------------

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


# ------------------- ФОТО -------------------

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

    # ліміт 2 фото на місяць
    current_month = datetime.now().strftime("%Y-%m")
    count = 0
    for row in records:
        if str(row["айді"]) == str(user_id):
            if row["дата_останнього_фото"].startswith(current_month):
                count += 1

    if count >= 2:
        await update.message.reply_text("❌ Ліміт 2 фото на місяць")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    path = f"{photo.file_id}.jpg"
    await file.download_to_drive(path)

    with open(path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # перевірка дубля
    for row in records:
        if row["хеш_фото"] == file_hash:
            os.remove(path)
            await update.message.reply_text("❌ Фото вже надсилалось")
            return

    sheet.update_cell(user_row, get_col("дата_останнього_фото"), datetime.now().isoformat())
    sheet.update_cell(user_row, get_col("статус_фото"), "+")
    sheet.update_cell(user_row, get_col("хеш_фото"), file_hash)

    with open(path, "rb") as f:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=f,
            caption=f"📸 Фото від @{username}"
        )

    os.remove(path)

    await update.message.reply_text("✅ Фото прийнято")


# ------------------- НАГАДУВАННЯ -------------------

async def reminder(context: ContextTypes.DEFAULT_TYPE):
    records = get_all()
    today = datetime.now()

    for row in records:
        if row["айді"] and row["дата_останнього_фото"]:
            last = datetime.fromisoformat(row["дата_останнього_фото"])
            if (today - last).days >= 30:
                try:
                    await context.bot.send_message(
                        chat_id=int(row["айді"]),
                        text="📢 Нагадування: надішліть нове фото"
                    )
                except:
                    pass


# ------------------- ЗАПУСК -------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.job_queue.run_repeating(reminder, interval=86400, first=10)

    app.run_polling()


if __name__ == "__main__":
    main()
