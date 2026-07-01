from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    ensure_user, create_support_ticket, set_ticket_admin_msg,
    get_ticket, close_ticket
)
from keyboards.kb import back_to_menu, support_admin_keyboard
from config import ADMIN_ID

router = Router()


class SupportState(StatesGroup):
    waiting_message = State()


# ── User side ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "support")
async def cb_support(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "💬 <b>Поддержка</b>\n\n"
        "Напиши своё сообщение — мы ответим как можно скорее.\n\n"
        "Просто отправь текст ниже 👇",
        parse_mode="HTML",
        reply_markup=back_to_menu(),
    )
    await state.set_state(SupportState.waiting_message)
    await call.answer()


@router.message(SupportState.waiting_message)
async def user_support_message(message: Message, state: FSMContext):
    uid = message.from_user.id
    name = message.from_user.username or message.from_user.first_name
    text = message.text or message.caption or "(без текста)"

    await ensure_user(uid, name)
    ticket_id = await create_support_ticket(uid, name, text)

    # Notify admin
    admin_text = (
        f"💬 <b>Тикет #{ticket_id}</b>\n\n"
        f"👤 {name} | <code>{uid}</code>\n\n"
        f"📝 {text}"
    )
    try:
        sent = await message.bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="HTML",
            reply_markup=support_admin_keyboard(ticket_id, uid),
        )
        await set_ticket_admin_msg(ticket_id, sent.message_id)
    except Exception:
        pass

    await message.answer(
        f"✅ <b>Сообщение отправлено!</b>\n\n"
        f"Тикет <b>#{ticket_id}</b> принят. Ответим в ближайшее время.",
        parse_mode="HTML",
        reply_markup=back_to_menu(),
    )
    await state.clear()


# ── Admin side ────────────────────────────────────────────────────────────────

class AdminReplyState(StatesGroup):
    waiting_reply = State()


@router.callback_query(F.data.startswith("support_reply:"))
async def admin_reply_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌", show_alert=True)
        return
    parts = call.data.split(":")
    ticket_id = int(parts[1])
    user_id = int(parts[2])
    ticket = await get_ticket(ticket_id)
    await call.message.edit_text(
        f"💬 <b>Ответ на тикет #{ticket_id}</b>\n\n"
        f"Игрок: {ticket['username']} | <code>{user_id}</code>\n"
        f"Сообщение: {ticket['text']}\n\n"
        f"Введи ответ:",
        parse_mode="HTML",
    )
    await state.set_state(AdminReplyState.waiting_reply)
    await state.update_data(ticket_id=ticket_id, user_id=user_id,
                            ticket_name=ticket["username"] or str(user_id))
    await call.answer()


@router.message(AdminReplyState.waiting_reply)
async def admin_reply_send(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    ticket_id, user_id = data["ticket_id"], data["user_id"]
    reply_text = message.text or message.caption or ""

    try:
        await message.bot.send_message(
            user_id,
            f"💬 <b>Ответ поддержки на тикет #{ticket_id}:</b>\n\n{reply_text}",
            parse_mode="HTML",
            reply_markup=back_to_menu(),
        )
        await close_ticket(ticket_id)
        await message.answer(
            f"✅ Ответ отправлен игроку <b>{data['ticket_name']}</b>.\nТикет #{ticket_id} закрыт.",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("support_close:"))
async def admin_close_ticket(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌", show_alert=True)
        return
    ticket_id = int(call.data.split(":")[1])
    await close_ticket(ticket_id)
    await call.message.edit_text(
        call.message.text + "\n\n✅ <b>Закрыт</b>",
        parse_mode="HTML",
    )
    await call.answer("Тикет закрыт")
