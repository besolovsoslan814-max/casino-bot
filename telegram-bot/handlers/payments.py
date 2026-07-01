from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice, PreCheckoutQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    ensure_user, get_balance, record_deposit,
    add_withdrawal, get_user, add_crypto_deposit
)
from keyboards.kb import (
    deposit_keyboard, back_to_menu,
    crypto_currency_keyboard, crypto_amount_keyboard
)
from config import ADMIN_ID, MIN_DEPOSIT, MIN_WITHDRAW, CRYPTO_WALLETS, STARS_PER_USDT

router = Router()


class WithdrawState(StatesGroup):
    waiting_amount = State()


class CryptoState(StatesGroup):
    waiting_confirm = State()


# ── Stars deposit ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "deposit")
async def cb_deposit(call: CallbackQuery):
    await call.message.edit_text(
        f"💳 <b>Пополнение Stars</b>\n\n"
        f"Минимум: <b>{MIN_DEPOSIT} ⭐</b>\n"
        f"Зачисление мгновенное.\n\nВыбери сумму:",
        reply_markup=deposit_keyboard(), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery):
    amount = int(call.data.split(":")[1])
    await call.message.answer_invoice(
        title=f"Пополнение {amount} ⭐",
        description=f"Зачислить {amount} Stars на счёт Stars Casino",
        payload=f"deposit:{call.from_user.id}:{amount}",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=amount)],
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if parts[0] == "deposit" and len(parts) == 3:
        user_id, amount = int(parts[1]), int(parts[2])
        await ensure_user(user_id, message.from_user.username or message.from_user.first_name)
        await record_deposit(user_id, amount)
        bal = await get_balance(user_id)
        await message.answer(
            f"✅ <b>Пополнено!</b>\n\n+{amount} ⭐ | Баланс: <b>{bal} ⭐</b>\n\nУдачи! 🎰",
            parse_mode="HTML",
        )


# ── Crypto deposit ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "deposit:crypto")
async def cb_deposit_crypto(call: CallbackQuery):
    configured = [cur for cur, addr in CRYPTO_WALLETS.items() if addr]
    if not configured:
        await call.answer(
            "❌ Крипто-пополнение временно недоступно. Используй Stars.", show_alert=True
        )
        return
    await call.message.edit_text(
        f"₿ <b>Пополнение криптой</b>\n\n"
        f"Курс: <b>1 USDT = {STARS_PER_USDT} ⭐</b>\n"
        f"После оплаты — свяжись с администратором для зачисления.\n\n"
        f"Выбери валюту:",
        reply_markup=crypto_currency_keyboard(), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto:"))
async def cb_crypto_currency(call: CallbackQuery):
    currency = call.data[7:]  # strip "crypto:"
    wallet = CRYPTO_WALLETS.get(currency, "")
    if not wallet:
        await call.answer("❌ Этот способ временно недоступен", show_alert=True)
        return
    await call.message.edit_text(
        f"₿ <b>Крипто — {currency}</b>\n\nВыбери сумму пополнения в USD:",
        reply_markup=crypto_amount_keyboard(currency), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto_amount:"))
async def cb_crypto_amount(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    currency = parts[1]
    usd = int(parts[2])
    stars = usd * STARS_PER_USDT
    wallet = CRYPTO_WALLETS.get(currency, "")

    dep_id = await add_crypto_deposit(call.from_user.id, currency, usd, stars)
    name = call.from_user.username or call.from_user.first_name

    await call.message.edit_text(
        f"₿ <b>Заявка #{dep_id} создана</b>\n\n"
        f"Валюта: <b>{currency}</b>\n"
        f"Сумма: <b>${usd}</b> → <b>{stars} ⭐</b>\n\n"
        f"Переведи на адрес:\n<code>{wallet}</code>\n\n"
        f"⚠️ После отправки напиши <b>@{(await call.bot.get_me()).username}</b> и "
        f"укажи номер заявки <b>#{dep_id}</b> и хэш транзакции — "
        f"администратор зачислит Stars вручную.",
        parse_mode="HTML", reply_markup=back_to_menu(),
    )
    await call.bot.send_message(
        ADMIN_ID,
        f"₿ <b>Новая крипто-заявка #{dep_id}</b>\n\n"
        f"👤 {name} | <code>{call.from_user.id}</code>\n"
        f"💱 {currency}: ${usd} → <b>{stars} ⭐</b>",
        parse_mode="HTML",
    )
    await call.answer()


# ── Stars withdraw ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "withdraw")
async def cb_withdraw(call: CallbackQuery, state: FSMContext):
    user = await get_user(call.from_user.id)
    if not user or user["balance"] < MIN_WITHDRAW:
        await call.answer(
            f"❌ Минимум {MIN_WITHDRAW} ⭐. Твой баланс: {user['balance'] if user else 0} ⭐",
            show_alert=True,
        )
        return
    await call.message.edit_text(
        f"💸 <b>Вывод Stars</b>\n\n"
        f"Баланс: <b>{user['balance']} ⭐</b>\n"
        f"Минимум: {MIN_WITHDRAW} ⭐\n\nВведи сумму:",
        parse_mode="HTML", reply_markup=back_to_menu(),
    )
    await state.set_state(WithdrawState.waiting_amount)
    await call.answer()


@router.message(WithdrawState.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи число.")
        return
    if amount < MIN_WITHDRAW:
        await message.answer(f"❌ Минимум {MIN_WITHDRAW} ⭐")
        return
    if amount > user["balance"]:
        await message.answer(f"❌ Недостаточно. Баланс: {user['balance']} ⭐")
        return
    wid = await add_withdrawal(message.from_user.id, amount)
    bal = await get_balance(message.from_user.id)
    name = message.from_user.username or message.from_user.first_name
    await message.answer(
        f"✅ <b>Заявка #{wid} принята!</b>\n\nСумма: <b>{amount} ⭐</b>\nОстаток: <b>{bal} ⭐</b>",
        parse_mode="HTML", reply_markup=back_to_menu(),
    )
    await message.bot.send_message(
        ADMIN_ID,
        f"📤 <b>Вывод #{wid}</b>\n👤 {name} | <code>{message.from_user.id}</code>\n"
        f"💸 <b>{amount} ⭐</b>",
        parse_mode="HTML",
    )
    await state.clear()
