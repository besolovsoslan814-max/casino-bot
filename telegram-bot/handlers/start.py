from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from database.db import ensure_user, get_user, get_top_players
from keyboards.kb import main_menu, back_to_menu
from config import (
    SLOTS_COMBOS, DICE_SIX_MULT, BASKET_MULT, DARTS_MULT,
    BOWLING_MULT, COIN_WIN_MULT, COIN_WIN_CHANCE, MINES_HOUSE_EDGE,
)

router = Router()


def profile_text(user: dict) -> str:
    won = user.get("games_won") or 0
    lost = user.get("games_lost") or 0
    total_g = won + lost
    pnl = user["total_out"] - user["total_in"]
    sign = "+" if pnl >= 0 else ""
    return (
        f"👤 <b>{user['username'] or 'Игрок'}</b>\n"
        f"⭐ Баланс: <b>{user['balance']} ⭐</b>\n"
        f"📥 Внесено: {user['total_in']} ⭐  |  📤 Выплачено: {user['total_out']} ⭐\n"
        f"📊 PnL: <b>{sign}{pnl} ⭐</b>  |  🎮 Игр: {total_g} (✅{won}/❌{lost})"
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user

    # Detect franchise bots — auto-link new users to the franchise owner
    ref_by: int | None = None
    from franchise_runner import FRANCHISE_BOT_MAP
    if message.bot.id in FRANCHISE_BOT_MAP:
        ref_by = FRANCHISE_BOT_MAP[message.bot.id]

    await ensure_user(user.id, user.username or user.first_name, ref_by=ref_by)
    db_user = await get_user(user.id)
    await message.answer(
        f"🎰 <b>Stars Casino</b>\n\n"
        + profile_text(db_user)
        + "\n\nВыбери игру или пополни баланс 👇",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    user = call.from_user
    await ensure_user(user.id, user.username or user.first_name)
    db_user = await get_user(user.id)
    await call.message.edit_text(
        f"🎰 <b>Stars Casino</b>\n\n"
        + profile_text(db_user)
        + "\n\nВыбери игру 👇",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "mystats")
async def cb_mystats(call: CallbackQuery):
    user = call.from_user
    await ensure_user(user.id, user.username or user.first_name)
    db_user = await get_user(user.id)
    await call.message.edit_text(
        f"📊 <b>Твоя статистика</b>\n\n" + profile_text(db_user),
        reply_markup=back_to_menu(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "leaderboard")
async def cb_leaderboard(call: CallbackQuery):
    top = await get_top_players(10)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for i, p in enumerate(top):
        name = p["username"] or f"ID:{p['user_id']}"
        lines.append(f"{medals[i]} <b>{name}</b> — {p['balance']} ⭐")
    text = "🏆 <b>Топ игроков по балансу</b>\n\n" + "\n".join(lines or ["Пока никого нет"])
    await call.message.edit_text(text, reply_markup=back_to_menu(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "rules")
async def cb_rules(call: CallbackQuery):
    slots_combos = "\n".join(
        f"  {v['emoji']} {v['name']}: × {v['mult']}" for v in SLOTS_COMBOS.values()
    )
    win_pct = int(COIN_WIN_CHANCE * 100)
    text = (
        "📖 <b>Правила и честные шансы</b>\n\n"
        f"🎰 <b>Слоты</b> — трёх одинаковых:\n{slots_combos}\n\n"
        f"🎲 <b>Кости</b> — только 6 → × {DICE_SIX_MULT} (шанс 16.7%)\n\n"
        f"🪙 <b>Монетка</b> — × {COIN_WIN_MULT} при победе | шанс {win_pct}%\n\n"
        f"🚀 <b>Краш</b> — 99% крашится до ×1.5 | 1% достигает ×10\n\n"
        f"📦 <b>Кейсы</b> — 0.5% джекпот | 30% частичный | 69.5% ничего\n\n"
        f"🎯 <b>Дартс</b> — яблочко (6) → × {DARTS_MULT} (шанс 16.7%)\n\n"
        f"🎳 <b>Боулинг</b> — страйк (6) → × {BOWLING_MULT} (шанс 16.7%)\n\n"
        f"🏀 <b>Баскет</b> — попадание (4/5) → × {BASKET_MULT} (шанс 40%)\n\n"
        f"💣 <b>Мины</b> — поле 5×5, house edge {int(MINES_HOUSE_EDGE*100)}%\n\n"
        f"✅ <b>Все шансы открыты и неизменны.</b>"
    )
    await call.message.edit_text(text, reply_markup=back_to_menu(), parse_mode="HTML")
    await call.answer()
