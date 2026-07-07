# handlers/client.py
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta

from language_str import TEXTS
from database import db_handler as db
from config import ADMIN_GROUP_ID

router = Router()

class SupportStates(StatesGroup):
    waiting_for_message = State()


# =====================================================================
# 🛡️ ЗАХИСТ ВІД СПАМУ ТА УМОВНА АПЕЛЯЦІЯ (ВЕРХНІЙ ХЕНДЛЕР)
# =====================================================================
@router.message(lambda message: db.is_banned(message.from_user.id))
async def handle_banned_user_everywhere(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    lang = db.get_user_lang(user_id) or "uk"

    ban_info = db.get_ban_info(user_id)
    if not ban_info:
        await message.answer(TEXTS[lang]["action_banned"])
        return

    status = ban_info["appeal_status"]
    
    if status == "rejected":
        text = "❌ Вашу апеляцію було відхилено. Доступ заблоковано остаточно." if lang == "uk" else "❌ Your appeal was rejected. Permanently banned."
        await message.answer(text)
        return

    if status == "pending":
        text = "⏳ Ваша апеляція вже розглядається адміністрацією. Будь ласка, очікуйте." if lang == "uk" else "⏳ Your appeal is currently under review. Please wait."
        await message.answer(text)
        return

    banned_at = datetime.strptime(ban_info["banned_at"], "%Y-%m-%d %H:%M:%S")
    time_passed = datetime.now() - banned_at
    cooldown_time = timedelta(minets=10)

    if time_passed < cooldown_time:
        seconds_left = int((cooldown_time - time_passed).total_seconds())
        minutes_left = seconds_left // 60
        
        if minutes_left > 0:
            text = f"🚫 Ви заблоковані за порушення правил. Подати апеляцію можна через {minutes_left} хв." if lang == "uk" else f"🚫 You are banned. You can submit an appeal in {minutes_left} min."
        else:
            text = f"🚫 Ви заблоковані за порушення правил. Подати апеляцію можна через {seconds_left} сек." if lang == "uk" else f"🚫 You are banned. You can submit an appeal in {seconds_left} sec."
        await message.answer(text)
    else:
        text = "⚠️ Термін очікування завершено. Ви можете подати одну одноразову апеляцію на розблокування:" if lang == "uk" else "⚠️ Cooldown period over. You can submit one single appeal for unbanning:"
        btn_text = "📩 Подати апеляцію" if lang == "uk" else "📩 Submit appeal"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data=f"user_send_appeal:{user_id}")]
        ])
        await message.answer(text, reply_markup=kb)


def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇦 Українська", callback_data="set_lang_uk"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")
        ]
    ])

def get_main_menu(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=TEXTS[lang]["btn_support"], callback_data="contact_support")],
        [InlineKeyboardButton(text=TEXTS[lang]["btn_faq"], callback_data="open_faq")],
        [InlineKeyboardButton(text=TEXTS[lang]["btn_links"], url="https://tiz.swedka121.com/")]
    ])

def get_back_keyboard(lang: str):
    text = "⬅️ Назад" if lang == "uk" else "⬅️ Back"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="back_to_menu")]
    ])

def get_cancel_keyboard(lang: str):
    text = "❌ Скасувати" if lang == "uk" else "❌ Cancel"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="back_to_menu")]
    ])


async def create_new_support_topic(bot: Bot, user_id: int, full_name: str, mention_html: str, lang: str):
    new_topic = await bot.create_forum_topic(chat_id=ADMIN_GROUP_ID, name=f"{full_name} ({user_id})")
    db.set_topic(user_id, new_topic.message_thread_id)

    info_text = (
        f"📥 **Нове звернення! / New Ticket!**\n"
        f"👤 **Користувач:** {mention_html} (ID: `{user_id}`)\n"
        f"🌐 **Мова:** {'🇺🇦 Українська' if lang == 'uk' else '🇬🇧 English'}\n"
        f"———\n"
        f"ℹ️ *Топік створено автоматично при вході користувача в бота.*"
    )
    await bot.send_message(chat_id=ADMIN_GROUP_ID, text=info_text, message_thread_id=new_topic.message_thread_id, parse_mode="HTML")
    return new_topic.message_thread_id


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if db.is_banned(user_id):
        return await message.answer(TEXTS["uk"]["action_banned"])

    await bot.set_my_commands([
        BotCommand(command="start", description="Перезапустити бота / Restart"),
        BotCommand(command="help", description="Допомога / Help FAQ")
    ])

    lang = db.get_user_lang(user_id) or "uk" 
    topic_id = db.get_topic_by_user(user_id)

    if not topic_id:
        try:
            await create_new_support_topic(bot=bot, user_id=user_id, full_name=message.from_user.full_name, mention_html=message.from_user.mention_html(), lang=lang)
        except Exception as e:
            logging.error(f"Не вдалося створити топік для {user_id} при старті: {e}")

    lang_db = db.get_user_lang(user_id)
    if lang_db:
        await message.answer(TEXTS[lang_db]["main_menu"], reply_markup=get_main_menu(lang_db), parse_mode="Markdown")
    else:
        await message.answer(TEXTS["uk"]["welcome"], reply_markup=get_lang_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    lang = db.get_user_lang(user_id) or "uk"

    if db.is_banned(user_id):
        return await message.answer(TEXTS[lang]["action_banned"])

    await message.answer(TEXTS[lang]["faq_text"], reply_markup=get_main_menu(lang), parse_mode="Markdown")


@router.callback_query(F.data.startswith("set_lang_"))
async def callback_select_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[2]
    user_id = callback.from_user.id
    db.set_user_lang(user_id, lang)

    await callback.message.edit_text(text=TEXTS[lang]["main_menu"], reply_markup=get_main_menu(lang), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "open_faq")
async def callback_faq(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_lang(user_id) or "uk"
    try:
        await callback.message.edit_text(text=TEXTS[lang]["faq_text"], reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def callback_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    lang = db.get_user_lang(user_id) or "uk"
    await callback.message.edit_text(text=TEXTS[lang]["main_menu"], reply_markup=get_main_menu(lang), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "contact_support")
async def callback_support(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_lang(user_id) or "uk"

    if db.is_banned(user_id):
        await callback.message.edit_text(TEXTS[lang]["action_banned"])
        await callback.answer()
        return 

    await callback.message.edit_text(text=TEXTS[lang]["support_activated"], reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")
    await state.set_state(SupportStates.waiting_for_message)
    await callback.answer()


@router.message(SupportStates.waiting_for_message)
async def forward_to_admin_group(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    lang = db.get_user_lang(user_id) or "uk"

    if db.is_banned(user_id):
        await message.answer(TEXTS[lang]["action_banned"])
        await state.clear()
        return

    topic_id = db.get_topic_by_user(user_id)

    try:
        if not topic_id:
            topic_id = await create_new_support_topic(bot, user_id, message.from_user.full_name, message.from_user.mention_html(), lang)

        try:
            await message.forward(chat_id=ADMIN_GROUP_ID, message_thread_id=topic_id)
        except TelegramBadRequest as e:
            if "message thread not found" in str(e).lower():
                db.delete_topic(user_id) 
                topic_id = await create_new_support_topic(bot, user_id, message.from_user.full_name, message.from_user.mention_html(), lang)
                await message.forward(chat_id=ADMIN_GROUP_ID, message_thread_id=topic_id)
            else:
                raise e

        await message.answer(TEXTS[lang]["msg_sent"], reply_markup=get_main_menu(lang))
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка пересилання: {e}")
        await message.answer("❌ Сталася помилка при надсиланні повідомлення.")
        await state.clear()


@router.callback_query(F.data.startswith("user_send_appeal:"))
async def callback_user_send_appeal(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    lang = db.get_user_lang(user_id) or "uk"
    
    ban_info = db.get_ban_info(user_id)
    if not ban_info or ban_info["appeal_status"] != "none":
        await callback.answer("❌ Апеляція вже обробляється або недоступна.", show_alert=True)
        return

    db.update_appeal_status(user_id, "pending")

    confirm_text = (
        "✅ **Вашу апеляцію успішно надіслано!**\nМенеджери розглянуть її найближчим часом. Очікуйте на сповіщення."
        if lang == "uk" else
        "✅ **Your appeal has been successfully sent!**\nManagers will review it shortly. Please wait for notification."
    )
    await callback.message.edit_text(text=confirm_text, parse_mode="Markdown")
    await callback.answer()

    admin_card = (
        f"⚖️ <b>НОВА АПЕЛЯЦІЯ НА РОЗБАН</b>\n"
        f"———\n"
        f"👤 <b>Користувач:</b> {callback.from_user.mention_html()}\n"
        f"🆔 <b>ID користувача:</b> <code>{user_id}</code>\n"
        f"🌐 <b>Мова інтерфейсу:</b> {lang.upper()}\n"
        f"🕒 <b>Час бану:</b> {ban_info['banned_at']}\n"
        f"———\n"
        f"📋 <i>Прийміть рішення щодо розблокування користувача:</i>"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Розбанити", callback_data=f"admin_approve_unban:{user_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"admin_reject_unban:{user_id}")
        ]
    ])

    try:
        await bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_card, reply_markup=admin_kb, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не вдалося надіслати картку апеляції в General: {e}")