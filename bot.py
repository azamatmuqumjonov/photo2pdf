import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from PIL import Image
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Константы для этапов диалога
PHOTOS, ASK_NAME, GENERATE_PDF = range(3)

# Папка для временных файлов
TEMP_FOLDER = "temp"

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

# Хранилище загруженных фотографий для каждого пользователя
user_photos = {}

async def start_or_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Приветственное сообщение или продолжение работы"""
    user_id = update.message.chat_id
    
    if user_id not in user_photos:
        user_photos[user_id] = []
        await update.message.reply_text("Привет! Отправь мне фотографии, которые нужно объединить в PDF.")
        logger.info(f"Пользователь {user_id} начал новую сессию.")
    else:
        await update.message.reply_text("Ты уже в процессе. Отправляй фото или напиши /done для завершения.")
        logger.info(f"Пользователь {user_id} продолжает сессию.")

    return PHOTOS

async def receive_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка загруженных фотографий"""
    user_id = update.message.chat_id
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = os.path.join(TEMP_FOLDER, f"{user_id}_{len(user_photos[user_id])}.jpg")
    await file.download_to_drive(file_path)

    user_photos[user_id].append(file_path)
    logger.info(f"Пользователь {user_id} загрузил фото: {file_path}")

    if len(user_photos[user_id]) == 1:
        await update.message.reply_text("Фото получено. Можешь отправить ещё или напиши /done, чтобы продолжить.")
    return PHOTOS

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает имя для PDF"""
    user_id = update.message.chat_id
    if not user_photos[user_id]:
        await update.message.reply_text("Ты не отправил ни одной фотографии. Начни сначала с /start.")
        logger.warning(f"Пользователь {user_id} попытался завершить без загрузки фото.")
        return ConversationHandler.END

    logger.info(f"Пользователь {user_id} завершил загрузку фото. Переход к выбору имени PDF.")
    await update.message.reply_text("Как назвать PDF?")
    return ASK_NAME

async def generate_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Генерирует PDF и отправляет пользователю"""
    user_id = update.message.chat_id
    pdf_name = update.message.text
    pdf_path = os.path.join(TEMP_FOLDER, f"{pdf_name}.pdf")
    images = []

    logger.info(f"Пользователь {user_id} запросил создание PDF с именем '{pdf_name}'.")

    for file_path in user_photos[user_id]:
        img = Image.open(file_path)
        img = img.convert("RGB")
        images.append(img)

    if images:
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        await update.message.reply_document(document=open(pdf_path, "rb"), filename=f"{pdf_name}.pdf")
        logger.info(f"PDF '{pdf_name}' создан и отправлен пользователю {user_id}.")

        # Удаление временных файлов
        for file_path in user_photos[user_id]:
            os.remove(file_path)
        os.remove(pdf_path)
        logger.info(f"Временные файлы для пользователя {user_id} удалены.")

    user_photos.pop(user_id, None)
    await update.message.reply_text("PDF готов! Если хочешь создать ещё, просто отправь новые фото.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущей операции"""
    user_id = update.message.chat_id
    user_photos.pop(user_id, None)
    logger.info(f"Пользователь {user_id} отменил операцию.")
    await update.message.reply_text("Операция отменена. Отправь фото, чтобы начать сначала.")
    return ConversationHandler.END

def main():
    """Запуск бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Токен Telegram бота не найден. Убедитесь, что файл .env содержит TELEGRAM_BOT_TOKEN.")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.ALL & ~filters.COMMAND, start_or_resume)],
        states={
            PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photos),
                CommandHandler("done", ask_name),
            ],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_pdf)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    logger.info("Бот запущен и готов к работе.")
    application.run_polling()

if __name__ == "__main__":
    main()
