async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username
    current_month = get_current_month()

    # Отримуємо фото
    photo = update.message.photo[-1]
    file = await photo.get_file()

    # Отримуємо байти без збереження на диск
    file_bytes = await file.download_as_bytearray()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Перевірка повторного фото
    cursor.execute("SELECT 1 FROM photos WHERE photo_hash=?", (file_hash,))
    if cursor.fetchone():
        await update.message.reply_text("❌ Це фото вже надсилалось раніше.")
        return

    # Перевірка ліміту 2 фото на місяць
    cursor.execute(
        "SELECT COUNT(*) FROM photos WHERE user_id=? AND month=?",
        (user_id, current_month))
    count = cursor.fetchone()[0]

    if count >= 2:
        await update.message.reply_text(
            "⚠️ Ви вже надіслали 2 фото цього місяця.\n"
            "Спробуйте знову наступного місяця.")
        
        return

    # Зберігаємо фото
    cursor.execute(
        "INSERT INTO photos VALUES (?, ?, ?, ?, ?)",
        (user_id, username, file_hash, current_month, datetime.now().isoformat()))

    conn.commit()

    await update.message.reply_text(
        f"✅ Фото прийнято! ({count + 1}/2 за цей місяць)")
    
    
    def main():
    app = ApplicationBuilder().token("8460126618:AAGXWc7PmSDn5oiW5sKDXb7EogVqQ-P9NJg").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if  __name__== "__main__":
