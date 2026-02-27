import os
import hashlib
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
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

# ------------------- Допоміжні -------------------
def get_all_records():
    return sheet.get_all_records()

def get_col_index(col_name):
    headers = sheet.row_values(1)
    return headers.index(col_name) + 1

def normalize_phone(phone):
    return phone.replace(" ", "").replace("-", "")

# ------------------- START -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton("Поділитися номером", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Натисніть кнопку щоб поділитися номером телефону.",
        reply_markup=keyboard
    )

# ------------------- Реєстрація -------------------
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    contact = update.message.contact

    phone = normalize_phone(contact.phone_number)
    user_id = user.id
    username = user.username or ""
    name = user.first_name or ""

    records = get_all_records()

    for index, row in enumerate(records, start=2):
        if normalize_phone(str(row["телефон"])) == phone:
            sheet.update_cell(index, get_col_index("телеграм_ник"), username)
            sheet.update_cell(index, get_col_index("айді"), user_id)
            await update.message.reply_text("✅ Реєстрація успішна.")
            return

    # якщо номера немає — додаємо нового користувача
    sheet.append_row([name, phone, username, user_id, "", "", ""])
    await update.message.reply_text("✅ Ви додані до системи.")

# ------------------- Фото -------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or ""
    name = user.first_name or ""

    records = get_all_records()
    user_row = None

    for index, row in enumerate(records, start=2):
        if row["айді"] == user_id:
            user_row = index
            break

    if not user_row:
        sheet.append_row([name, "", username, user_id, "", "", ""])
        user_row = len(records) + 2

    # Перевірка двох фото на місяць
    current_month = datetime.now().strftime("%Y-%m")
    count_this_month = 0
    for row in records:
        if str(row["айді"]) == str(user_id) and row["дата_останнього_фото"].startswith(current_month):
            count_this_month += 1
    if count_this_month >= 2:
        await update.message.reply_text("❌ Ви вже надіслали 2 фото цього місяця.")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Перевірка дубля
    for row in records:
        if row["хеш_фото"] == file_hash:
            os.remove(file_path)
            await update.message.reply_text("❌ Це фото вже надсилалось.")
            return

    # Оновлюємо таблицю
    sheet.update_cell(user_row, get_col_index("дата_останнього_фото"), datetime.now().isoformat())
    sheet.update_cell(user_row, get_col_index("статус_фото"), "+")
    sheet.update_cell(user_row, get_col_index("хеш_фото"), file_hash)

    # Відправка адміну
    with open(file_path, "rb") as f:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=f,
            caption=f"📸 Фото від @{username}"
        )

    os.remove(file_path)
    await update.message.reply_text(f"✅ Фото прийнято. Використано {count_this_month + 1}/2 цього місяця.")

# ------------------- Нагадування -------------------
async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    records = get_all_records()
    today = datetime.now()

    for row in records:
        uid = row["айді"]
        last_date = row["дата_останнього_фото"]

        if uid and last_date:
            last = datetime.fromisoformat(last_date)
            if (today - last).days >= 30:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="📢 Нагадування: надішліть нове фото."
                    )
                except:
                    pass

# ------------------- Запуск -------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Нагадування кожні 24 години
    app.job_queue.run_repeating(reminder_job, interval=86400, first=10)

    app.run_polling()

if __name__ == "__main__":
    main()
