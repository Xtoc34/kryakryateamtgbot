import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession 
from database.db_handler import init_db
from handlers import client, admin
from aiohttp import web

logging.basicConfig(level=logging.INFO)

async def handle_ping(request):
    return web.Response(text="OK", status=200)

async def main():
    init_db()
    print("💾 База даних успішно ініціалізована!")

    IS_PA_SERVER = os.environ.get('PYTHONANYWHERE_SITE') is not None
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    
    if not BOT_TOKEN:
        from config import BOT_TOKEN as LOCAL_TOKEN
        BOT_TOKEN = LOCAL_TOKEN

    if IS_PA_SERVER:
        print("🌐 Запуск на сервері PythonAnywhere (через проксі)...")
        session = AiohttpSession(proxy="http://proxy.server:3128")
        bot = Bot(token=BOT_TOKEN, session=session)
    else:
        print("💻 Запуск напряму (без проксі)...")
        bot = Bot(token=BOT_TOKEN)

    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(client.router)

    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Веб-сервер для пинга запущен на порту {port}")

    print("🚀 Бот запущений через Long Polling...")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот зупинений.")