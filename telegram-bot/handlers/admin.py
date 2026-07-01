import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    get_stats, get_all_user_ids, change_balance, get_user,
    get_top_players, get_recent_games, get_pending_withdrawals,
    ensure_user, get_all_settings, set_setting, SETTING_DEFAULTS,
    get_open_tickets, get_all_franchises,
)
from keyboards.kb import admin_menu, back_to_admin, settings_keyboard
from config import ADMIN_ID, DB_PATH

router = Router()

GAME_ICONS = {
    "slots": "🎰", "dice": "🎲", "mines": "💣", "coin": "🪙",
    "crash": "🚀", "case": "📦", "darts": "🎯", "bowling": "🎳", "basket": "🏀",
}


class AdminStates(StatesGroup):
    find_user    = State()
    balance_uid  = State()
    balance_amt  = State()
    broadcast    = State()
    setting_edit = State()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def hdr() -> str:
    return "🎰 <b>STARS CASINO — АДМИН</b>\n" + "─" * 28 + "\n"


# ── /admin ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    await message.answer(hdr() + "\nВыбери раздел:", reply_markup=admin_menu(), parse_mode="HTML")


@router.callback_query(F.data == "admin:panel")
async def admin_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text(hdr() + "\nВыбери раздел:", reply_markup=admin_menu(), parse_mode="HTML")
    await call.answer()


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    s = await get_stats()
    total_g = s["games_won"] + s["games_lost"]
    wr = round(s["games_won"] / total_g * 100, 1) if total_g else 0
    text = (
        hdr() + f"\n📊 <b>Статистика</b>\n\n"
        f"👥 Игроков:       <b>{s['players']}</b>\n"
        f"🤝 Партнёров:     <b>{s['partners']}</b>\n"
        f"💬 Открытых тик.: <b>{s['open_tickets']}</b>\n"
        f"🎮 Игр всего:     <b>{s['total_games']}</b>\n"
        f"🎮 Игр сегодня:   <b>{s['games_today']}</b>\n\n"
        f"📥 Внесено:       <b>{s['total_in']} ⭐</b>\n"
        f"📤 Выплачено:     <b>{s['total_out']} ⭐</b>\n"
        f"💰 Профит:        <b>{s['profit']} ⭐</b>\n\n"
        f"✅ Побед:  <b>{s['games_won']}</b> ({wr}%) | ❌ Поражений: <b>{s['games_lost']}</b>"
    )
    await call.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await call.answer()


# ── Top ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:top")
async def admin_top(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    top = await get_top_players(10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = []
    for i, p in enumerate(top):
        name = p["username"] or f"ID:{p['user_id']}"
        lines.append(
            f"{medals[i]} <b>{name}</b>\n"
            f"   💰 {p['balance']} ⭐  |  ✅ {p.get('games_won') or 0} / ❌ {p.get('games_lost') or 0}"
        )
    await call.message.edit_text(
        hdr() + "\n🏆 <b>Топ игроков</b>\n\n" + "\n\n".join(lines or ["Пусто"]),
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await call.answer()


# ── Recent games ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:games")
async def admin_games(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    games = await get_recent_games(10)
    lines = []
    for g in games:
        icon = GAME_ICONS.get(g["game"], "🎮")
        net = g["payout"] - g["bet"]
        res = f"{'✅ +' if net >= 0 else '❌ '}{net} ⭐"
        lines.append(f"{icon} <b>{g['username'] or '?'}</b> | {g['bet']} ⭐ | {res}")
    await call.message.edit_text(
        hdr() + "\n🎮 <b>Последние игры</b>\n\n" + "\n".join(lines or ["Нет"]),
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await call.answer()


# ── Withdrawals ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    pending = await get_pending_withdrawals()
    if not pending:
        text = hdr() + "\n📤 <b>Выводы</b>\n\nПодвисших заявок нет ✅"
    else:
        lines = [
            f"#{w['id']} | <b>{w['username'] or '?'}</b> | <code>{w['user_id']}</code>\n"
            f"   💸 {w['amount']} ⭐ | {w.get('method','stars')} | {str(w['requested_at'])[:16]}"
            for w in pending
        ]
        text = hdr() + f"\n📤 <b>Заявки ({len(pending)})</b>\n\n" + "\n\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await call.answer()


# ── Partners ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:partners")
async def admin_partners(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, u.username FROM partners p JOIN users u ON p.user_id = u.user_id "
            "ORDER BY p.earnings DESC LIMIT 10"
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    if not rows:
        text = hdr() + "\n🤝 <b>Партнёры</b>\n\nПока никого нет."
    else:
        lines = [
            f"👤 <b>{p['username'] or p['user_id']}</b> | <code>{p['ref_code']}</code>\n"
            f"   👥 {p['referrals']} реф. | 💰 {p['earnings']} ⭐ | ⏳ {p['pending']} ⭐"
            for p in rows
        ]
        text = hdr() + f"\n🤝 <b>Партнёры ({len(rows)})</b>\n\n" + "\n\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await call.answer()


# ── Crypto ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:crypto")
async def admin_crypto(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT c.*, u.username FROM crypto_deposits c "
            "JOIN users u ON c.user_id = u.user_id "
            "WHERE c.status = 'pending' ORDER BY c.created_at DESC LIMIT 10"
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    if not rows:
        text = hdr() + "\n₿ <b>Крипто-заявки</b>\n\nПодвисших нет ✅"
    else:
        lines = [
            f"#{r['id']} | <b>{r['username'] or '?'}</b> | <code>{r['user_id']}</code>\n"
            f"   {r['currency']} | ${r['amount_fiat']} → <b>{r['stars']} ⭐</b>"
            for r in rows
        ]
        text = hdr() + f"\n₿ <b>Крипто ({len(rows)})</b>\n\n" + "\n\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await call.answer()


# ── Support tickets ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:tickets")
async def admin_tickets(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    tickets = await get_open_tickets(15)
    if not tickets:
        text = hdr() + "\n💬 <b>Тикеты</b>\n\nОткрытых тикетов нет ✅"
    else:
        lines = [
            f"#{t['id']} | <b>{t['username'] or '?'}</b> | <code>{t['user_id']}</code>\n"
            f"   {str(t['created_at'])[:16]} — {t['text'][:60]}"
            for t in tickets
        ]
        text = hdr() + f"\n💬 <b>Открытые тикеты ({len(tickets)})</b>\n\n" + "\n\n".join(lines)
        text += "\n\nНажми «Ответить» на пересланном сообщении или используй кнопку в тикете."
    await call.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await call.answer()


# ── ⚙️ Settings ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:settings")
async def admin_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    current = await get_all_settings()
    await call.message.edit_text(
        hdr() + "\n⚙️ <b>Настройки игр</b>\n\n"
        "Нажми на параметр чтобы изменить:",
        reply_markup=settings_keyboard(current),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("setting:"))
async def setting_select(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    key = call.data[8:]
    current = await get_all_settings()
    val = current.get(key, "?")
    _, label = SETTING_DEFAULTS.get(key, ("", key))
    await call.message.edit_text(
        hdr() + f"\n⚙️ <b>Редактирование</b>\n\n"
        f"Параметр: <b>{label}</b>\n"
        f"Текущее значение: <code>{val}</code>\n\n"
        f"Введи новое значение:",
        parse_mode="HTML",
        reply_markup=back_to_admin(),
    )
    await state.set_state(AdminStates.setting_edit)
    await state.update_data(setting_key=key, setting_label=label)
    await call.answer()


@router.message(AdminStates.setting_edit)
async def setting_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key, label = data["setting_key"], data["setting_label"]
    new_val = message.text.strip()
    # Validate: must be a number
    try:
        float(new_val)
    except ValueError:
        await message.answer("❌ Введи числовое значение (например 1.5 или 0.01)")
        return
    await set_setting(key, new_val)
    current = await get_all_settings()
    await message.answer(
        hdr() + f"\n✅ <b>{label}</b>\nНовое значение: <code>{new_val}</code>\n\n"
        "Другие параметры:",
        reply_markup=settings_keyboard(current),
        parse_mode="HTML",
    )
    await state.clear()


# ── Find user ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:find")
async def admin_find_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text(
        hdr() + "\n🔍 Введи <b>Telegram ID</b>:",
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await state.set_state(AdminStates.find_user)
    await call.answer()


@router.message(AdminStates.find_user)
async def admin_find_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Числовой ID"); return
    user = await get_user(uid)
    if not user:
        await message.answer("❌ Не найден", reply_markup=back_to_admin())
        await state.clear(); return
    won = user.get("games_won") or 0
    lost = user.get("games_lost") or 0
    pnl = user["total_out"] - user["total_in"]
    await message.answer(
        hdr() + f"\n🔍 <b>Профиль</b>\n\n"
        f"👤 {user['username'] or '—'} | <code>{uid}</code>\n"
        f"💰 Баланс: <b>{user['balance']} ⭐</b>\n"
        f"📊 PnL: {'+' if pnl>=0 else ''}{pnl} ⭐\n"
        f"✅ {won} побед  |  ❌ {lost} поражений",
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await state.clear()


# ── Balance adjust ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:balance")
async def admin_balance_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text(
        hdr() + "\n💰 Введи <b>Telegram ID</b>:",
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await state.set_state(AdminStates.balance_uid)
    await call.answer()


@router.message(AdminStates.balance_uid)
async def admin_balance_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Числовой ID"); return
    user = await get_user(uid)
    if not user:
        await message.answer("❌ Не найден"); await state.clear(); return
    await state.update_data(target_uid=uid, target_name=user["username"] or f"ID:{uid}")
    await message.answer(
        f"👤 <b>{user['username'] or uid}</b> | {user['balance']} ⭐\n\n"
        f"Введи изменение (<code>+500</code> или <code>-100</code>):",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.balance_amt)


@router.message(AdminStates.balance_amt)
async def admin_balance_amt(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    try:
        delta = int(message.text.strip().replace(" ", ""))
    except ValueError:
        await message.answer("❌ Пример: +500 или -100"); return
    await change_balance(data["target_uid"], delta)
    user = await get_user(data["target_uid"])
    await message.answer(
        f"✅ <b>{data['target_name']}</b>: {'+' if delta>=0 else ''}{delta} ⭐\n"
        f"Новый баланс: <b>{user['balance']} ⭐</b>",
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await state.clear()


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text(
        hdr() + "\n📢 Введи текст рассылки (HTML):",
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await state.set_state(AdminStates.broadcast)
    await call.answer()


@router.message(AdminStates.broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    text = message.text or message.caption or ""
    user_ids = await get_all_user_ids()
    sent = failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📢 Рассылка завершена: ✅ {sent} | ❌ {failed}",
        reply_markup=back_to_admin(), parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data == "admin:franchises")
async def admin_franchises(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔", show_alert=True)
        return
    rows = await get_all_franchises()
    if not rows:
        text = "🏢 <b>Франшизы</b>\n\nПока нет ни одной франшизы."
    else:
        status_emoji = {"active": "✅", "pending": "⏳", "suspended": "🚫"}
        lines = [f"🏢 <b>Франшизы ({len(rows)})</b>\n"]
        for f in rows:
            e = status_emoji.get(f["status"], "❓")
            lines.append(
                f"{e} <b>@{f['bot_username'] or '—'}</b> | "
                f"owner: <code>{f['owner_id']}</code> | "
                f"{f['status']} | {f['created_at'][:10]}"
            )
        text = "\n".join(lines)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_admin())
    await call.answer()


@router.callback_query(F.data == "admin:close")
async def admin_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()
