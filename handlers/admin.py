# handlers/admin.py
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import os
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', 0))
from database import db_handler as db
from language_str import TEXTS

router = Router()

# =====================================================================
# 📌 КОМАНДА /close (ЗАКРЫТИЕ ТТИКЕТА)
# =====================================================================
@router.message(F.chat.id == ADMIN_GROUP_ID, Command("close"))
async def cmd_close_ticket(message: Message, bot: Bot):
    if not message.message_thread_id:
        return

    user_id = db.get_user_by_topic(message.message_thread_id)
    if user_id:
        lang = db.get_user_lang(user_id) or "uk"
        try:
            await bot.send_message(chat_id=user_id, text=TEXTS[lang]["ticket_closed"])
        except Exception:
            pass

        db.delete_topic(user_id)
        try:
            await bot.close_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=message.message_thread_id)
        except Exception:
            await message.answer("Топік закрито в базі, але не вдалося закрити його в TG.")
    else:
        await message.answer("Користувача для цього топіка не знайдено.")


# =====================================================================
# 🚫 КОМАНДА /ban (БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ)
# =====================================================================
@router.message(F.chat.id == ADMIN_GROUP_ID, Command("ban"))
async def cmd_ban_user(message: Message, bot: Bot):
    if not message.message_thread_id:
        await message.answer("❌ Цю команду можна виконати тільки всередині конкретного топіка користувача.")
        return

    user_id = db.get_user_by_topic(message.message_thread_id)
    if user_id:
        db.add_to_blacklist(user_id)
        db.delete_topic(user_id)
        await message.answer(
            f"🚫 **Користувач ID `{user_id}` успішно забанений.**\n"
            f"⏳ Відлік 10 хвилин до можливості апеляції розпочато.\n"
            f"🔒 Цей топік буде закрито.",
            parse_mode="Markdown"
        )
        try:
            await bot.close_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=message.message_thread_id)
        except Exception:
            pass
    else:
        await message.answer("❌ Не вдалося знайти користувача для блокування у базі даних.")


# =====================================================================
# 🔓 КОМАНДА /unban ID (РУЧНОЙ РАЗБАН В GENERAL)
# =====================================================================
@router.message(F.chat.id == ADMIN_GROUP_ID, Command("unban"))
async def cmd_unban_user(message: Message, bot: Bot):
    from handlers.client import create_new_support_topic

    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Будь ласка, вкажіть ID користувача.\nПриклад: `/unban 123456789`", parse_mode="Markdown")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID користувача має бути числовим значенням.")
        return

    if db.is_banned(user_id):
        db.remove_from_blacklist(user_id)
        
        lang = db.get_user_lang(user_id) or "uk"
        notify_text = (
            "🎉 **Вас було успішно розблоковано менеджером!**\nТепер ви знову можете користуватися підтримкою."
            if lang == "uk" else
            "🎉 **You have been successfully unbanned by a manager!**\nNow you can use support again."
        )
        try:
            await bot.send_message(chat_id=user_id, text=notify_text, parse_mode="Markdown")
        except Exception:
            pass

        await message.answer(f"✅ Користувача ID `{user_id}` успішно розбанено через команду.")

        try:
            user_chat = await bot.get_chat(user_id)
            await create_new_support_topic(
                bot=bot,
                user_id=user_id,
                full_name=user_chat.full_name,
                mention_html=user_chat.mention_html(),
                lang=lang
            )
        except Exception as e:
            logging.error(f"Не вдалося створити новий топік після ручного розбану {user_id}: {e}")
            await message.answer("⚠️ Користувача розбанено, але не вдалося автоматично створити для нього топік.")
    else:
        await message.answer("ℹ️ Цей користувач не знайдений у списку заблокованих.")


# =====================================================================
# ⚖️ ОБРАБОТКА КНОПОК АПЕЛЛЯЦИИ ИЗ ЧАТА GENERAL
# =====================================================================
@router.callback_query(F.data.startswith("admin_approve_unban:"))
async def callback_admin_approve_unban(callback: CallbackQuery, bot: Bot):
    from handlers.client import create_new_support_topic
    user_id = int(callback.data.split(":")[1])
    
    if not db.is_banned(user_id):
        await callback.answer("❌ Користувач вже не в бані або апеляцію оброблено.", show_alert=True)
        return

    db.remove_from_blacklist(user_id)
    
    updated_text = callback.message.text + f"\n\n<b>✅ Рішення: Апеляцію схвалено, користувача РОЗБАНЕНО.</b> (Адмін: {callback.from_user.full_name})"
    await callback.message.edit_text(text=updated_text, parse_mode="HTML", reply_markup=None)
    await callback.answer("Користувача розбанено!")

    lang = db.get_user_lang(user_id) or "uk"
    notify_text = (
        "🎉 **Вашу апеляцію було схвалено! Вас розблоковано.**\nТепер ви знову можете звертатися до підтримки."
        if lang == "uk" else
        "🎉 **Your appeal has been approved! You are unbanned.**\nNow you can use support again."
    )
    try:
        await bot.send_message(chat_id=user_id, text=notify_text, parse_mode="Markdown")
    except Exception:
        pass

    try:
        user_chat = await bot.get_chat(user_id)
        await create_new_support_topic(
            bot=bot,
            user_id=user_id,
            full_name=user_chat.full_name,
            mention_html=user_chat.mention_html(),
            lang=lang
        )
    except Exception as e:
        logging.error(f"Не вдалося створити топік після схвалення апеляції {user_id}: {e}")


@router.callback_query(F.data.startswith("admin_reject_unban:"))
async def callback_admin_reject_unban(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    
    ban_info = db.get_ban_info(user_id)
    if not ban_info or ban_info["appeal_status"] != "pending":
        await callback.answer("❌ Цю апеляцію вже було оброблено або дані застаріли.", show_alert=True)
        return

    db.update_appeal_status(user_id, "rejected")
    
    updated_text = callback.message.text + f"\n\n<b>❌ Рішення: Апеляцію ВІДХИЛЕНО. Бан залишається назавжди.</b> (Адмін: {callback.from_user.full_name})"
    await callback.message.edit_text(text=updated_text, parse_mode="HTML", reply_markup=None)
    await callback.answer("Апеляцію відхилено.")


# =====================================================================
# 💬 ХЕНДЛЕР ОТВЕТА МЕНЕДЖЕРА (СТРОГО В САМОМ КОНЦЕ И ИГНОРИРУЕТ КОМАНДЫ)
# =====================================================================
@router.message(F.chat.id == ADMIN_GROUP_ID, lambda msg: not msg.text or not msg.text.startswith("/"))
async def handle_admin_reply(message: Message, bot: Bot):
    if not message.message_thread_id or message.from_user.is_bot:
        return

    user_id = db.get_user_by_topic(message.message_thread_id)
    if not user_id:
        return

    lang = db.get_user_lang(user_id) or "uk"
    prefix = "👨‍💻 **Відповідь менеджера:**\n\n" if lang == "uk" else "👨‍💻 **Manager's answer:**\n\n"

    try:
        if message.text:
            await bot.send_message(chat_id=user_id, text=f"{prefix}{message.text}", parse_mode="Markdown")
        elif message.photo:
            await bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
        elif message.document:
            await bot.send_document(chat_id=user_id, document=message.document.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
        elif message.voice:
            await bot.send_message(chat_id=user_id, text=prefix, parse_mode="Markdown")
            await bot.send_voice(chat_id=user_id, voice=message.voice.file_id)
        elif message.video_note:
            await bot.send_message(chat_id=user_id, text=prefix, parse_mode="Markdown")
            await bot.send_video_note(chat_id=user_id, video_note=message.video_note.file_id)
        elif message.video:
            await bot.send_video(chat_id=user_id, video=message.video.file_id, caption=f"{prefix}{message.caption or ''}", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Не вдалося надіслати повідомлення користувачу.\nПомилка: {e}")