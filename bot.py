import os
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from fpdf import FPDF
from PIL import Image

# Загружаем переменные из .env
load_dotenv()

# Получаем токен
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Папка для хранения файлов
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Словарь для хранения данных пользователей
user_data = {}

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Присылай фото, и я сделаю из них PDF!")

def handle_photo(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Инициализация данных пользователя
    if user_id not in user_data:
        user_data[user_id] = {'photos': [], 'file_name': ''}

    # Сохранение фото
    photo = update.message.photo[-1]
    file = context.bot.getFile(photo.file_id)
    file_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{len(user_data[user_id]['photos'])}.jpg")
    file.download(file_path)
    user_data[user_id]['photos'].append(file_path)

    update.message.reply_text("Фото сохранено! Теперь напиши, как хочешь назвать свой файл (без расширения).")

def set_filename(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Если у пользователя нет фото, попросим загрузить фото
    if user_id not in user_data or not user_data[user_id]['photos']:
        update.message.reply_text("Загрузи фото, прежде чем задавать название.")
        return

    # Сохраняем имя файла
    user_data[user_id]['file_name'] = update.message.text
    update.message.reply_text(f"Название файла установлено: {user_data[user_id]['file_name']}.\nЯ создаю PDF!")

    # Создаем PDF
    create_pdf(user_id, update, context)

def create_pdf(user_id, update: Update, context: CallbackContext):
    # Если имя файла не задано, используем имя по умолчанию
    file_name = user_data[user_id]['file_name'] or "output"
    photos = user_data[user_id]['photos']

    # Создание PDF
    pdf = FPDF()
    for image_path in photos:
        img = Image.open(image_path)
        pdf.add_page()
        pdf.image(image_path, x=10, y=10, w=190)  # Подгоняем под размер страницы

    # Сохранение PDF
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{file_name}.pdf")
    pdf.output(pdf_path)

    # Отправка PDF пользователю
    with open(pdf_path, "rb") as pdf_file:
        context.bot.send_document(chat_id=update.message.chat_id, document=pdf_file)

    # Удаление временных файлов
    for photo in photos:
        os.remove(photo)
    os.remove(pdf_path)
    
    # Очистка данных пользователя
    user_data[user_id] = {'photos': [], 'file_name': ''}

    update.message.reply_text(f"PDF с названием '{file_name}.pdf' отправлен!")

def main():
    # Настройка бота
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Хендлеры
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, set_filename))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
