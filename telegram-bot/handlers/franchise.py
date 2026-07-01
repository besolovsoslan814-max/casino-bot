import logging

from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    ensure_user, get_or_create_partner,
    create_franchise, get_franchise_by_owner, activate_franchise,
)
from keyboards.kb import back_to_menu
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

FRANCHISE_PRICE = 1000  # Stars


class FranchiseState(StatesGroup):
    waiting_token = State()


# ── Info / menu ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "franchise")
async def franchise_info(call: CallbackQuery):
    uid = call.from_user.id
    existing = await get_franchise_by_owner(uid)

    if existing:
        emoji = {"active": "✅", "pending": "⏳", "suspended": "🚫"}.get(
            existing["status"], "❓"
        )
        text = (
            f"🏢 <b>Твоя франшиза</b>\n\n"
            f"Бот: <b>@{existing['bot_username'] or '...'}</b>\n"
            f"Статус: {emoji} <b>{existing['status'].upper()}</b>\n\n"
            f"Все игроки твоего бота привязаны к тебе как рефералы.\n"
            f"Ты получаешь <b>50%</b> от каждого их проигрыша.\n\n"
            f"Заработок → кнопка <b>🤝 Партнёрка</b> в главном меню."
        )
        kb = back_to_menu()
    else:
        text = (
            f"🏢 <b>Франшиза Stars Casino</b>\n\n"
            f"Открой своё казино на базе нашего движка!\n\n"
            f"<b>Что ты получаешь:</b>\n"
            f"• Полноценный казино-бот со всеми играми 🎰\n"
            f"• Работает на нашем сервере — ничего не настраивать\n"
            f"• <b>50% от каждого проигрыша</b> игроков твоего бота\n"
            f"• Автоматический запуск сразу после оплаты\n\n"
            f"<b>Как это работает:</b>\n"
            f"1️⃣ Создай бота через @BotFather → /newbot\n"
            f"2️⃣ Оплати <b>{FRANCHISE_PRICE} ⭐</b>\n"
            f"3️⃣ Пришли нам токен бота\n"
            f"4️⃣ Бот запустится автоматически! 🚀\n\n"
            f"💰 Стоимость: <b>{FRANCHISE_PRICE} Telegram Stars</b>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Купить за {FRANCHISE_PRICE} ⭐",
                callback_data="franchise:buy",
            )],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu")],
        ])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


# ── Purchase ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "franchise:buy")
async def franchise_buy(call: CallbackQuery):
    if await get_franchise_by_owner(call.from_user.id):
        await call.answer("У тебя уже есть франшиза!", show_alert=True)
        return
    await call.message.answer_invoice(
        title="🏢 Франшиза Stars Casino",
        description="Свой казино-бот со всеми играми. 50% прибыли от твоих игроков — тебе.",
        payload=f"franchise:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="Франшиза", amount=FRANCHISE_PRICE)],
    )
    await call.answer()


def _is_franchise_payment(m: Message) -> bool:
    return (
        m.successful_payment is not None
        and m.successful_payment.invoice_payload.startswith("franchise:")
    )


@router.message(_is_franchise_payment)
async def franchise_paid(message: Message, state: FSMContext):
    await message.answer(
        f"✅ <b>Оплата {FRANCHISE_PRICE} ⭐ получена!</b>\n\n"
        f"Теперь пришли <b>токен своего бота</b>.\n\n"
        f"Как получить токен:\n"
        f"• Открой @BotFather\n"
        f"• Напиши /newbot → придумай имя → скопируй токен\n\n"
        f"Токен выглядит так:\n"
        f"<code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</code>",
        parse_mode="HTML",
    )
    await state.set_state(FranchiseState.waiting_token)


# ── Token submission ──────────────────────────────────────────────────────────

@router.message(FranchiseState.waiting_token)
async def franchise_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    uid = message.from_user.id
    name = message.from_user.username or message.from_user.first_name

    if ":" not in token or len(token) < 30:
        await message.answer(
            "❌ Это не похоже на токен бота.\n"
            "Токен: <code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</code>\n\n"
            "Попробуй снова:",
            parse_mode="HTML",
        )
        return

    # Validate token via Telegram API
    try:
        test_bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        info = await test_bot.get_me()
        await test_bot.session.close()
        bot_username = info.username
        bot_id = info.id
    except Exception:
        await message.answer(
            "❌ Токен недействителен или бот уже запущен где-то ещё.\n"
            "Убедись что токен правильный и бот нигде не работает.",
            parse_mode="HTML",
        )
        return

    # Save to DB
    fid = await create_franchise(uid, token, bot_username, bot_id)
    await get_or_create_partner(uid)  # ensure partner record exists for earnings

    # Start franchise bot using the shared dispatcher stored in franchise_runner
    from franchise_runner import start_franchise_bot, MAIN_DP
    launched_username = None
    if MAIN_DP is not None:
        launched_username = await start_franchise_bot(MAIN_DP, token, uid)
        if launched_username:
            await activate_franchise(fid)

    if launched_username:
        reply = (
            f"🎉 <b>Франшиза активирована!</b>\n\n"
            f"Твой бот: @{launched_username}\n\n"
            f"Уже работает — зайди и нажми /start 🚀\n\n"
            f"Все твои игроки автоматически привязаны к тебе как рефералы.\n"
            f"Заработок отслеживай через <b>🤝 Партнёрка</b>."
        )
    else:
        reply = (
            f"⏳ <b>Токен принят!</b>\n\n"
            f"Бот @{bot_username} будет активирован администратором "
            f"в течение нескольких минут."
        )

    await message.answer(reply, parse_mode="HTML", reply_markup=back_to_menu())
    await message.bot.send_message(
        ADMIN_ID,
        f"🏢 <b>Новая франшиза #{fid}</b>\n\n"
        f"👤 {name} | <code>{uid}</code>\n"
        f"🤖 @{bot_username} | id: {bot_id}\n"
        f"Статус: {'✅ активна' if launched_username else '⏳ ожидает'}",
        parse_mode="HTML",
    )
    await state.clear()
