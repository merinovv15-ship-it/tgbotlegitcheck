import os
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from PIL import Image

# ================== НАСТРОЙКИ ==================
TOKEN = "8529330545:AAHeAZDLR4TSI8f_F0ePWYjn7qsSu4q40XY"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Путь к фото водяного знака - просто положите файл с этим именем в папку с ботом
WATERMARK_PATH = os.path.join(BASE_DIR, "watermark.png")

# Состояния для ConversationHandler
PHOTO_1, PHOTO_2, PHOTO_3, PHOTO_4 = range(4)

# Хранилище для временных файлов
user_photos = {}

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы с ботом"""
    # Проверяем наличие водяного знака
    watermark_exists = os.path.exists(WATERMARK_PATH)

    await update.message.reply_text(
        "🖼️ **Привет! Я бот для создания коллажей из 4 фото!**\n\n"
        "📸 **Как это работает:**\n"
        "1. Отправьте мне 4 фото по очереди\n"
        "2. Я создам коллаж 2x2 (4 квадрата)\n" +
        ("3. Добавлю ваше фото как водяной знак чуть ниже центра\n\n" if watermark_exists else "\n") +
        "**Начнем с первого фото:**"
    )
    return PHOTO_1


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение фото от пользователя"""
    user_id = update.message.from_user.id
    photo_file = await update.message.photo[-1].get_file()

    # Создаем папку для пользователя
    user_folder = os.path.join(BASE_DIR, f"temp_{user_id}")
    os.makedirs(user_folder, exist_ok=True)

    # Определяем, какое по счету это фото
    if user_id not in user_photos:
        user_photos[user_id] = []
        photo_index = 0
    else:
        photo_index = len(user_photos[user_id])

    # Сохраняем фото
    photo_path = os.path.join(user_folder, f"photo_{photo_index + 1}.jpg")
    await photo_file.download_to_drive(photo_path)
    user_photos[user_id].append(photo_path)

    # Запрашиваем следующее фото или создаем коллаж
    if len(user_photos[user_id]) < 4:
        await update.message.reply_text(
            f"✅ Фото {len(user_photos[user_id])} принято!\n"
            f"Осталось отправить {4 - len(user_photos[user_id])} фото.\n\n"
            f"Отправьте **следующее фото**:"
        )
        return PHOTO_1 + len(user_photos[user_id])
    else:
        await update.message.reply_text("🔄 Все фото получены! Создаю коллаж...")
        return await create_collage(update, context, user_id)


def resize_and_crop(image, target_size):
    """Увеличивает изображение сохраняя пропорции и обрезает по центру"""
    # Вычисляем соотношения сторон
    target_ratio = target_size[0] / target_size[1]
    image_ratio = image.width / image.height

    # Определяем, как масштабировать изображение
    if image_ratio > target_ratio:
        # Широкое изображение - масштабируем по высоте
        new_height = target_size[1]
        new_width = int(image.width * (new_height / image.height))
    else:
        # Высокое изображение - масштабируем по ширине
        new_width = target_size[0]
        new_height = int(image.height * (new_width / image.width))

    # Ресайзим изображение
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Обрезаем по центру до целевого размера
    left = (new_width - target_size[0]) // 2
    top = (new_height - target_size[1]) // 2
    right = left + target_size[0]
    bottom = top + target_size[1]

    cropped_image = resized_image.crop((left, top, right, bottom))

    return cropped_image


async def create_collage(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Создание коллажа 2x2 с водяным знаком"""
    try:
        # Размер итогового изображения
        collage_width, collage_height = 1000, 1000

        # Создаем белый фон для коллажа
        collage = Image.new('RGB', (collage_width, collage_height), 'white')

        # Размер каждого фото (половина ширины и высоты)
        photo_width = collage_width // 2
        photo_height = collage_height // 2
        photo_size = (photo_width, photo_height)

        # Координаты для 4 фото
        positions = [
            (0, 0),  # Верхний левый
            (photo_width, 0),  # Верхний правый
            (0, photo_height),  # Нижний левый
            (photo_width, photo_height)  # Нижний правый
        ]

        # Размещаем каждое фото на коллаже
        for i, photo_path in enumerate(user_photos[user_id]):
            if i >= 4:  # Максимум 4 фото
                break

            # Открываем и обрабатываем фото
            photo = Image.open(photo_path)

            # Увеличиваем фото сохраняя пропорции и обрезаем
            resized_photo = resize_and_crop(photo, photo_size)

            # Размещаем фото на коллаже
            collage.paste(resized_photo, positions[i])

        # Добавляем водяной знак (если файл существует)
        watermark_exists = os.path.exists(WATERMARK_PATH)
        if watermark_exists:
            collage_with_watermark = add_center_watermark(collage)
        else:
            collage_with_watermark = collage

        # Сохраняем результат
        user_folder = os.path.join(BASE_DIR, f"temp_{user_id}")
        output_path = os.path.join(user_folder, "collage_result.png")
        collage_with_watermark.save(output_path, "PNG", quality=95)

        # Отправляем результат
        caption = "🎉 **Ваш коллаж готов кумыс красава!**\n\n4 фото объединены в сетку 2x2"
        if watermark_exists:
            caption += " с вашим водяным знаком"
        caption += "\n\nЧтобы создать новый коллаж, отправьте /start"

        with open(output_path, 'rb') as result_file:
            await update.message.reply_photo(
                photo=InputFile(result_file),
                caption=caption
            )

        # Очищаем временные файлы
        cleanup_user_files(user_id)

    except Exception as e:
        logging.error(f"Error creating collage: {e}")
        await update.message.reply_text("❌ Ошибка при создании коллажа. Попробуйте снова /start")
        cleanup_user_files(user_id)

    return ConversationHandler.END


def add_center_watermark(image):
    """Добавляет водяной знак чуть ниже центра изображения"""
    try:
        # Загружаем водяной знак
        watermark = Image.open(WATERMARK_PATH)

        # Конвертируем в RGBA если нужно (для прозрачности)
        if watermark.mode != 'RGBA':
            watermark = watermark.convert('RGBA')

        # Размер основного изображения
        image_width, image_height = image.size

        # Размер водяного знака (20% от ширины изображения)
        watermark_size = int(image_width * 0.30)

        # Ресайзим водяной знак сохраняя пропорции
        watermark_ratio = watermark.width / watermark.height
        new_width = watermark_size
        new_height = int(watermark_size / watermark_ratio)

        # Убедимся что размеры не нулевые
        new_width = max(70, new_width)
        new_height = max(50, new_height)

        watermark_resized = watermark.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Позиция по центру по горизонтали, но чуть ниже по вертикали
        x = (image_width - new_width) // 2
        y = (image_height - new_height) // 2 + int(image_height * 0.03)  # Смещение на 5% вниз

        # Конвертируем основное изображение в RGBA
        if image.mode != 'RGBA':
            image_rgba = image.convert('RGBA')
        else:
            image_rgba = image

        # Вставляем водяной знак
        image_rgba.paste(watermark_resized, (x, y), watermark_resized)

        return image_rgba.convert('RGB')

    except Exception as e:
        logging.error(f"Error adding watermark: {e}")
        return image


def cleanup_user_files(user_id: int):
    """Очистка временных файлов"""
    try:
        user_folder = os.path.join(BASE_DIR, f"temp_{user_id}")
        if os.path.exists(user_folder):
            for file in os.listdir(user_folder):
                file_path = os.path.join(user_folder, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(user_folder)
        if user_id in user_photos:
            del user_photos[user_id]
    except Exception as e:
        logging.error(f"Error cleaning up files: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    user_id = update.message.from_user.id
    cleanup_user_files(user_id)
    await update.message.reply_text("❌ Операция отменена. Для начала отправьте /start")
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь по боту"""
    watermark_exists = os.path.exists(WATERMARK_PATH)

    help_text = """
🖼️ **Коллаж-бот: создание сетки 2x2 из фото**

✨ **Команды:**
/start - Начать создание коллажа
/help - Эта справка
/watermark - Информация о водяном знаке
/cancel - Отменить текущую операцию

📸 **Процесс:**
1. Отправьте /start
2. Пришлите 4 фото по очереди
3. Получите коллаж 2x2
""" + ("""
🎨 **Водяной знак:**
Ваше фото 'watermark.png' автоматически добавляется как БОЛЬШОЙ знак чуть ниже центра
""" if watermark_exists else """
ℹ️ **Водяной знак:**
Чтобы добавить водяной знак, положите файл 'watermark.png' в папку с ботом
""") + """
🔄 **Особенности:**
• Фото увеличиваются и обрезаются для заполнения квадратов
• Сохраняются пропорции изображений
• Нет белых полей - все квадраты полностью заполнены
• Водяной знак расположен чуть ниже центра

💡 **Совет:** Используйте PNG с прозрачным фоном для водяного знака!
    """
    await update.message.reply_text(help_text)


async def watermark_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о водяном знаке"""
    watermark_exists = os.path.exists(WATERMARK_PATH)

    if watermark_exists:
        try:
            with open(WATERMARK_PATH, 'rb') as watermark_file:
                await update.message.reply_photo(
                    photo=InputFile(watermark_file),
                    caption="✅ **Текущий водяной знак**\n\n"
                            "Это фото добавляется в каждый коллаж как БОЛЬШОЙ водяной знак чуть ниже центра.\n"
                            "Чтобы изменить, замените файл 'watermark.png' в папке с ботом."
                )
        except Exception as e:
            await update.message.reply_text(f"✅ Водяной знак установлен, но не удалось показать: {e}")
    else:
        await update.message.reply_text(
            "❌ **Водяной знак не установлен**\n\n"
            "Чтобы добавить водяной знак:\n"
            "1. Положите файл 'watermark.png' в папку с ботом\n"
            "2. Перезапустите бота (если нужно)\n"
            "3. Водяной знак будет автоматически добавляться как БОЛЬШОЙ знак чуть ниже центра каждого коллажа"
        )


def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()

    # ConversationHandler для основного потока создания коллажа
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHOTO_1: [MessageHandler(filters.PHOTO, receive_photo)],
            PHOTO_2: [MessageHandler(filters.PHOTO, receive_photo)],
            PHOTO_3: [MessageHandler(filters.PHOTO, receive_photo)],
            PHOTO_4: [MessageHandler(filters.PHOTO, receive_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("watermark", watermark_info))
    application.add_handler(CommandHandler("cancel", cancel))

    # Проверяем наличие водяного знака при запуске
    if os.path.exists(WATERMARK_PATH):
        logging.info(f"✅ Водяной знак найден: {WATERMARK_PATH}")
        logging.info("✅ Размер водяного знака: 20% от ширины коллажа (большой)")
        logging.info("✅ Позиция: чуть ниже центра (смещение 5% вниз)")
    else:
        logging.info("ℹ️ Водяной знак не найден. Коллажи будут создаваться без водяного знака")

    logging.info("🤖 Бот запущен! Ожидание команд...")
    application.run_polling()


if __name__ == '__main__':
    main()