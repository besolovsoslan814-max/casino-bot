from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    get_or_create_partner, ensure_user, get_user,
    get_partner_by_code, withdraw_partner_earnings, add_withdrawal, get_balance
)
from keyboards.kb import back_to_menu
from config import ADMIN_ID, MIN_WITHDRAW

router = Router()


class PartnerWithdraw(StatesGroup):
    waiting_amount = State()


@router.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return
    ref_code = args[1].strip()
    uid = message.from_user.id
    name = message.from_user.username or message.from_user.first_name

    partner = await get_partner_by_code(ref_code)
    if not partner or partner["user_id"] == uid:
        await ensure_user(uid, name)
        return

    existing = await get_user(uid)
    await ensure_user(uid, name, ref_by=partner["user_id"] if not existing else None)

    if not existing:
        await message.answer(
            f"👋 Тебя пригласил партнёр!\n"
            f"Добро пожаловать в <b>Stars Casino</b> 🎰\n\n"
            f"Пополни баланс и начни играть!",
            parse_mode="HTML",
        )
    else:
        await message.answer("👋 Добро пожаловать обратно!")


@router.callback_query(F.data == "partner")
async def partner_menu(call: CallbackQuery):
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    partner = await get_or_create_partner(uid)

    bot_info = await call.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={partner['ref_code']}"

    await call.message.edit_text(
        f"🤝 <b>Партнёрская программа</b>\n\n"
        f"Приглашай игроков — получай <b>50%</b> от прибыли казино с каждого твоего реферала!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"📊 Статистика:\n"
        f"  👥 Рефералов: <b>{partner['referrals']}</b>\n"
        f"  💰 Заработано всего: <b>{partner['earnings']} ⭐</b>\n"
        f"  💳 Доступно к выводу: <b>{partner['pending']} ⭐</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Для вывода партнёрских ⭐ напиши /partner_withdraw",
        parse_mode="HTML",
        reply_markup=back_to_menu(),
    )
    await call.answer()


@router.message(Command("partner_withdraw"))
async def partner_withdraw_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    partner = await get_or_create_partner(uid)
    if partner["pending"] < MIN_WITHDRAW:
        await message.answer(
            f"❌ Минимум для вывода: {MIN_WITHDRAW} ⭐\n"
            f"Доступно: <b>{partner['pending']} ⭐</b>",
            parse_mode="HTML",
        )
        return
    await message.answer(
        f"💸 Доступно: <b>{partner['pending']} ⭐</b>\n\nВведи сумму для вывода:",
        parse_mode="HTML",
    )
    await state.set_state(PartnerWithdraw.waiting_amount)


@router.message(PartnerWithdraw.waiting_amount)
async def partner_withdraw_exec(message: Message, state: FSMContext):
    uid = message.from_user.id
    partner = await get_or_create_partner(uid)
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    if amount < MIN_WITHDRAW:
        await message.answer(f"❌ Минимум {MIN_WITHDRAW} ⭐")
        return
    if amount > partner["pending"]:
        await message.answer(f"❌ Недостаточно. Доступно: {partner['pending']} ⭐")
        return

    await withdraw_partner_earnings(uid, amount)
    name = message.from_user.username or message.from_user.first_name

    await message.answer(
        f"✅ <b>Заявка на вывод партнёрских средств</b>\n\n"
        f"Сумма: <b>{amount} ⭐</b>\n"
        f"Обработаем в ближайшее время.",
        parse_mode="HTML",
        reply_markup=back_to_menu(),
    )
    await message.bot.send_message(
        ADMIN_ID,
        f"🤝 <b>Вывод партнёра</b>\n\n"
        f"👤 {name} | <code>{uid}</code>\n"
        f"💸 Сумма: <b>{amount} ⭐</b>",
        parse_mode="HTML",
    )
    await state.clear()
