async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    current_month = get_current_month()

    Перевірка: скільки фото вже надіслано цього місяця
    cursor.execute(
        "SELECT COUNT(*) FROM photos WHERE user_id=? AND month=?",
        (user_id, current_month)
    )
    photo_count = cursor.fetchone()[0]

    if photo_count >= 2:
        await update.message.reply_text("❌ Ви вже здали 2 фото цього місяця.")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    Хеш фото
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

   Перевірка повтору фото
    cursor.execute("SELECT * FROM photos WHERE photo_hash=?", (file_hash,))
    if cursor.fetchone():
        await update.message.reply_text("❌ Це фото вже надсилалось раніше.")
        os.remove(file_path)
        return

    Зберігаємо в базу
    cursor.execute(
        "INSERT INTO photos VALUES (?, ?, ?, ?, ?)",
        (user_id, username, file_hash, current_month, datetime.now().isoformat())
    )
    conn.commit()

    os.remove(file_path)

    remaining = 2 - (photo_count + 1)

    if remaining > 0:
        await update.message.reply_text(
            f"✅ Фото прийнято!\n"
            f"Ви ще можете надіслати {remaining} фото цього місяця."
        )
    else:
        await update.message.reply_text(
            "✅ Фото прийнято!\n"
            "Ліміт на цей місяць вичерпано."
        )
