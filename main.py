import asyncio
import logging
import os  # Імпортуємо os для перевірки середовища
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession 
from config import BOT_TOKEN  # Будемо використовувати змінну з конфігу
from database.db_handler import init_db
from handlers import client, admin

logging.basicConfig(level=logging.INFO)

async def main():
    # Ініціалізація бази даних
    init_db()
    print("💾 База даних успішно ініціалізована!")

    # Перевіряємо, чи запущено бота на сервері PythonAnywhere.
    # PythonAnywhere автоматично створює змінну оточення 'PYTHONANYWHERE_SITE'
    IS_SERVER = os.environ.get('PYTHONANYWHERE_SITE') is not None

    if IS_SERVER:
        # На сервері створюємо сесію з проксі
        print("🌐 Запуск на сервері PythonAnywhere (через проксі)...")
        session = AiohttpSession(proxy="http://proxy.server:3128")
        bot = Bot(token=BOT_TOKEN, session=session)
    else:
        # На ПК запускаємо напряму без жодних проксі-сесій
        print("💻 Запуск локально на ПК (без проксі)...")
        bot = Bot(token=BOT_TOKEN)

    dp = Dispatcher()
    
    # Важливо: admin роутер вище за client, щоб команди адміна не перехоплювалися клієнтськими текстовими хендлерами
    dp.include_router(admin.router)
    dp.include_router(client.router)

    print("🚀 Бот запущений через Long Polling...")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот зупинений.")