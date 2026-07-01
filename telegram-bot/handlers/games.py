import random
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import ensure_user, get_balance, record_game, change_balance, get_setting
from keyboards.kb import (
    bet_keyboard, coin_choice, crash_targets, cases_keyboard,
    mines_count_keyboard, mines_field,
)

router = Router()


class MinesState(StatesGroup):
    playing = State()


# ── helpers ───────────────────────────────────────────────────────────────────

async def deduct(uid: int, bet: int, call: CallbackQuery) -> bool:
    bal = await get_balance(uid)
    if bal < bet:
        await call.answer(f"❌ Недостаточно средств. Баланс: {bal} ⭐", show_alert=True)
        return False
    await change_balance(uid, -bet)
    return True


def win_msg(bet: int, payout: int, new_bal: int, extra: str = "") -> str:
    net = payout - bet
    return (
        f"🏆 <b>ВЫИГРЫШ!</b> {extra}\n\n"
        f"Ставка: {bet} ⭐ → Выплата: <b>+{payout} ⭐</b> (прибыль +{net} ⭐)\n"
        f"💰 Баланс: <b>{new_bal} ⭐</b>"
    )


def loss_msg(bet: int, new_bal: int, extra: str = "") -> str:
    return (
        f"❌ <b>Проигрыш.</b> {extra}\n\n"
        f"Ставка: {bet} ⭐ сгорела\n"
        f"💰 Баланс: <b>{new_bal} ⭐</b>"
    )


# ── СЛОТЫ 🎰 ──────────────────────────────────────────────────────────────────

SLOTS_MAP = {
    1:  ("🍫", "BAR BAR BAR",    "slots_bar_mult",   3.0),
    22: ("🍇", "Виноград 🍇🍇🍇", "slots_grape_mult", 5.0),
    43: ("🍋", "Лимон 🍋🍋🍋",   "slots_lemon_mult", 5.0),
    64: ("7️⃣", "ДЖЕКПОТ 7️⃣7️⃣7️⃣","slots_seven_mult", 15.0),
}


@router.callback_query(F.data == "game:slots")
async def slots_menu(call: CallbackQuery):
    lines = "\n".join(f"  {e} {name}" for _, (e, name, _, _) in SLOTS_MAP.items())
    await call.message.edit_text(
        f"🎰 <b>Слоты</b>\n\nПобеда при трёх одинаковых:\n{lines}\n\n"
        f"Выбери ставку ⭐:",
        reply_markup=bet_keyboard("slots"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:slots:"))
async def slots_play(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    dice_msg = await call.message.answer_dice(emoji="🎰")
    val = dice_msg.dice.value
    combo = SLOTS_MAP.get(val)
    if combo:
        emoji, name, setting_key, default_mult = combo
        mult = float(await get_setting(setting_key) or default_mult)
        payout = int(bet * mult)
        await record_game(uid, "slots", bet, f"win:{val}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            win_msg(bet, payout, new_bal, f"{emoji} <b>{name}</b> × {mult}"),
            reply_markup=bet_keyboard("slots"), parse_mode="HTML",
        )
    else:
        await record_game(uid, "slots", bet, f"loss:{val}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            loss_msg(bet, new_bal, "Нет совпадений"),
            reply_markup=bet_keyboard("slots"), parse_mode="HTML",
        )
    await call.answer()


# ── КОСТИ 🎲 ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:dice")
async def dice_menu(call: CallbackQuery):
    mult = await get_setting("dice_mult")
    await call.message.edit_text(
        f"🎲 <b>Кости</b>\n\nВыигрыш только при <b>6</b>.\n"
        f"Выплата: <b>× {mult}</b> | Шанс: ~16.7%\n\nВыбери ставку ⭐:",
        reply_markup=bet_keyboard("dice"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:dice:"))
async def dice_play(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    dice_msg = await call.message.answer_dice(emoji="🎲")
    roll = dice_msg.dice.value
    if roll == 6:
        mult = float(await get_setting("dice_mult"))
        payout = int(bet * mult)
        await record_game(uid, "dice", bet, "win:6", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            win_msg(bet, payout, new_bal, f"Выпала <b>6</b>! 🎲 × {mult}"),
            reply_markup=bet_keyboard("dice"), parse_mode="HTML",
        )
    else:
        await record_game(uid, "dice", bet, f"loss:{roll}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            loss_msg(bet, new_bal, f"Выпало <b>{roll}</b>, нужна 6"),
            reply_markup=bet_keyboard("dice"), parse_mode="HTML",
        )
    await call.answer()


# ── МОНЕТКА 🪙 ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:coin")
async def coin_menu(call: CallbackQuery):
    chance = float(await get_setting("coin_win_chance"))
    mult = await get_setting("coin_win_mult")
    pct = int(chance * 100)
    await call.message.edit_text(
        f"🪙 <b>Орёл / Решка</b>\n\nВыплата при победе: <b>× {mult}</b>\n"
        f"Шанс: {pct}% — удача улыбается редко!\n\nВыбери ставку ⭐:",
        reply_markup=bet_keyboard("coin"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:coin:"))
async def coin_bet(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    await call.message.edit_text(
        f"🪙 <b>Ставка: {bet} ⭐</b>\n\nВыбери сторону:",
        reply_markup=coin_choice(bet), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("coin:"))
async def coin_play(call: CallbackQuery):
    _, side, bet_s = call.data.split(":")
    bet = int(bet_s)
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    label = {"heads": "🦅 Орёл", "tails": "🔵 Решка"}
    chance = float(await get_setting("coin_win_chance"))
    mult = float(await get_setting("coin_win_mult"))
    won = random.random() < chance
    result = side if won else ("tails" if side == "heads" else "heads")
    if won:
        payout = int(bet * mult)
        await record_game(uid, "coin", bet, f"win:{result}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            win_msg(bet, payout, new_bal, f"Выпало {label[result]} 🍀 × {mult}"),
            reply_markup=coin_choice(bet), parse_mode="HTML",
        )
    else:
        await record_game(uid, "coin", bet, f"loss:{result}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            loss_msg(bet, new_bal, f"Ты: {label[side]} | Выпало: {label[result]}"),
            reply_markup=coin_choice(bet), parse_mode="HTML",
        )
    await call.answer()


# ── КРАШ 🚀 ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:crash")
async def crash_menu(call: CallbackQuery):
    jchance = float(await get_setting("crash_jackpot_chance"))
    jmult = await get_setting("crash_jackpot_mult")
    pct = int(jchance * 100)
    await call.message.edit_text(
        f"🚀 <b>Краш</b>\n\n99% ракет падает до ×1.5\n"
        f"<b>{pct}%</b> ракет достигает <b>×{jmult}</b>!\n\n"
        f"Выбери ставку ⭐:",
        reply_markup=bet_keyboard("crash"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:crash:"))
async def crash_bet(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    await call.message.edit_text(
        f"🚀 <b>Краш — ставка: {bet} ⭐</b>\n\nВыбери целевой множитель:",
        reply_markup=crash_targets(bet), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("crash:"))
async def crash_play(call: CallbackQuery):
    _, target_s, bet_s = call.data.split(":")
    target = float(target_s)
    bet = int(bet_s)
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    jchance = float(await get_setting("crash_jackpot_chance"))
    jmult = float(await get_setting("crash_jackpot_mult"))
    if random.random() < jchance:
        crash_point = jmult
    else:
        crash_point = round(random.uniform(1.0, 1.49), 2)
    if crash_point >= target:
        payout = int(bet * target)
        await record_game(uid, "crash", bet, f"win:{target}:{crash_point}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            f"🚀 Ракета поднялась до <b>×{crash_point}</b>!\n\n"
            + win_msg(bet, payout, new_bal, f"Твой выход: ×{target}"),
            reply_markup=crash_targets(bet), parse_mode="HTML",
        )
    else:
        await record_game(uid, "crash", bet, f"loss:{target}:{crash_point}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            f"💥 <b>КРАШ</b> на <b>×{crash_point}</b> — до ×{target} не дотянула!\n"
            f"Ставка сгорела полностью.\n\n" + loss_msg(bet, new_bal),
            reply_markup=crash_targets(bet), parse_mode="HTML",
        )
    await call.answer()


# ── КЕЙСЫ 📦 ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:cases")
async def cases_menu(call: CallbackQuery):
    s_win_w = int(await get_setting("case_silver_win_weight"))
    s_win_m = float(await get_setting("case_silver_win_mult"))
    s_par_w = int(await get_setting("case_silver_partial_w"))
    s_none_w = 1000 - s_win_w - s_par_w
    g_win_w = int(await get_setting("case_gold_win_weight"))
    g_win_m = float(await get_setting("case_gold_win_mult"))
    g_par_w = int(await get_setting("case_gold_partial_w"))
    g_none_w = 1000 - g_win_w - g_par_w
    text = (
        f"📦 <b>Кейсы</b>\n\n"
        f"<b>🥈 Серебряный — 50 ⭐</b>\n"
        f"  💀 Ничего: {max(0,s_none_w)/10:.1f}%\n"
        f"  🔴 Частичный (×0.1-0.9): {s_par_w/10:.1f}%\n"
        f"  ✨ Джекпот ×{s_win_m}: {s_win_w/10:.2f}%\n\n"
        f"<b>🥇 Золотой — 200 ⭐</b>\n"
        f"  💀 Ничего: {max(0,g_none_w)/10:.1f}%\n"
        f"  🔴 Частичный (×0.3-0.9): {g_par_w/10:.1f}%\n"
        f"  🌟 Джекпот ×{g_win_m}: {g_win_w/10:.2f}%\n\n"
        f"Выбери кейс:"
    )
    await call.message.edit_text(text, reply_markup=cases_keyboard(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("case:"))
async def case_open(call: CallbackQuery):
    key = call.data.split(":")[1]
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)

    if key == "silver":
        price, case_name = 50, "🥈 Серебряный"
        win_w = int(await get_setting("case_silver_win_weight"))
        win_m = float(await get_setting("case_silver_win_mult"))
        par_w = int(await get_setting("case_silver_partial_w"))
        par_min, par_max = 0.1, 0.9
    elif key == "gold":
        price, case_name = 200, "🥇 Золотой"
        win_w = int(await get_setting("case_gold_win_weight"))
        win_m = float(await get_setting("case_gold_win_mult"))
        par_w = int(await get_setting("case_gold_partial_w"))
        par_min, par_max = 0.3, 0.9
    else:
        await call.answer("Не найдено", show_alert=True)
        return

    none_w = max(0, 1000 - win_w - par_w)
    items = [
        ("💀 Ничего",           0.0,   False, none_w),
        ("🔴 Частичный возврат", None,  True,  par_w),
        ("✨ Джекпот!",          win_m, False, win_w),
    ]
    weights = [i[3] for i in items]
    chosen = random.choices(items, weights=weights, k=1)[0]
    name_item, mult_val, is_var, _ = chosen

    if is_var:
        mult_val = round(random.uniform(par_min, par_max), 2)

    if not await deduct(uid, price, call):
        return

    payout = int(price * (mult_val or 0))
    if payout > 0:
        await record_game(uid, "case", price, f"win:{name_item}:{mult_val}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            f"📦 <b>{case_name} открыт!</b>\n\n"
            f"Выпало: <b>{name_item}</b> × {mult_val}\n\n"
            + win_msg(price, payout, new_bal),
            reply_markup=cases_keyboard(), parse_mode="HTML",
        )
    else:
        await record_game(uid, "case", price, f"loss:{name_item}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            f"📦 <b>{case_name} открыт!</b>\n\nВыпало: <b>{name_item}</b> 😔\n\n"
            + loss_msg(price, new_bal),
            reply_markup=cases_keyboard(), parse_mode="HTML",
        )
    await call.answer()


# ── ДАРТС 🎯 ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:darts")
async def darts_menu(call: CallbackQuery):
    mult = await get_setting("darts_mult")
    await call.message.edit_text(
        f"🎯 <b>Дартс</b>\n\nЯблочко (<b>6</b>) = выигрыш.\n"
        f"Выплата: <b>× {mult}</b> | Шанс: ~16.7%\n\nВыбери ставку ⭐:",
        reply_markup=bet_keyboard("darts"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:darts:"))
async def darts_play(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    dice_msg = await call.message.answer_dice(emoji="🎯")
    val = dice_msg.dice.value
    if val == 6:
        mult = float(await get_setting("darts_mult"))
        payout = int(bet * mult)
        await record_game(uid, "darts", bet, f"win:{val}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            win_msg(bet, payout, new_bal, "🎯 Яблочко!"),
            reply_markup=bet_keyboard("darts"), parse_mode="HTML",
        )
    else:
        await record_game(uid, "darts", bet, f"loss:{val}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            loss_msg(bet, new_bal, f"Попал в {val}, нужно яблочко"),
            reply_markup=bet_keyboard("darts"), parse_mode="HTML",
        )
    await call.answer()


# ── БОУЛИНГ 🎳 ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:bowling")
async def bowling_menu(call: CallbackQuery):
    mult = await get_setting("bowling_mult")
    await call.message.edit_text(
        f"🎳 <b>Боулинг</b>\n\nСтрайк (<b>6</b>) = выигрыш.\n"
        f"Выплата: <b>× {mult}</b> | Шанс: ~16.7%\n\nВыбери ставку ⭐:",
        reply_markup=bet_keyboard("bowling"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:bowling:"))
async def bowling_play(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    dice_msg = await call.message.answer_dice(emoji="🎳")
    val = dice_msg.dice.value
    if val == 6:
        mult = float(await get_setting("bowling_mult"))
        payout = int(bet * mult)
        await record_game(uid, "bowling", bet, f"win:{val}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            win_msg(bet, payout, new_bal, "🎳 СТРАЙК!"),
            reply_markup=bet_keyboard("bowling"), parse_mode="HTML",
        )
    else:
        await record_game(uid, "bowling", bet, f"loss:{val}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            loss_msg(bet, new_bal, f"Сбил {val} — нужен страйк"),
            reply_markup=bet_keyboard("bowling"), parse_mode="HTML",
        )
    await call.answer()


# ── БАСКЕТ 🏀 ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "game:basket")
async def basket_menu(call: CallbackQuery):
    mult = await get_setting("basket_mult")
    await call.message.edit_text(
        f"🏀 <b>Баскетбол</b>\n\nПопадание (<b>4 или 5</b>) = выигрыш.\n"
        f"Выплата: <b>× {mult}</b> | Шанс: ~40%\n\nВыбери ставку ⭐:",
        reply_markup=bet_keyboard("basket"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:basket:"))
async def basket_play(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    dice_msg = await call.message.answer_dice(emoji="🏀")
    val = dice_msg.dice.value
    if val in {4, 5}:
        mult = float(await get_setting("basket_mult"))
        payout = int(bet * mult)
        await record_game(uid, "basket", bet, f"win:{val}", payout)
        new_bal = await get_balance(uid)
        await call.message.answer(
            win_msg(bet, payout, new_bal, "🏀 Попал!"),
            reply_markup=bet_keyboard("basket"), parse_mode="HTML",
        )
    else:
        await record_game(uid, "basket", bet, f"loss:{val}", 0)
        new_bal = await get_balance(uid)
        await call.message.answer(
            loss_msg(bet, new_bal, f"Мимо (результат {val})"),
            reply_markup=bet_keyboard("basket"), parse_mode="HTML",
        )
    await call.answer()


# ── МИНЫ 💣 ───────────────────────────────────────────────────────────────────

async def mines_multiplier(revealed: int, mines: int, total: int = 25) -> float:
    if revealed == 0:
        return 1.0
    house = float(await get_setting("mines_house_edge"))
    prob = 1.0
    safe = total - mines
    for i in range(revealed):
        prob *= (safe - i) / (total - i)
    return round((1.0 / prob) * (1 - house), 2)


@router.callback_query(F.data == "game:mines")
async def mines_menu(call: CallbackQuery):
    he = float(await get_setting("mines_house_edge"))
    await call.message.edit_text(
        f"💣 <b>Мины</b>\n\nПоле 5×5. Открывай клетки — избегай мин.\n"
        f"Больше мин = выше множитель. Забирай когда угодно!\n"
        f"House edge: {int(he*100)}%\n\nВыбери ставку ⭐:",
        reply_markup=bet_keyboard("mines"), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("bet:mines:"))
async def mines_bet(call: CallbackQuery):
    bet = int(call.data.split(":")[2])
    bal = await get_balance(call.from_user.id)
    if bal < bet:
        await call.answer("❌ Недостаточно средств.", show_alert=True)
        return
    await call.message.edit_text(
        f"💣 <b>Мины — ставка: {bet} ⭐</b>\n\nВыбери кол-во мин:",
        reply_markup=mines_count_keyboard(bet), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("mines:start:"))
async def mines_start(call: CallbackQuery, state: FSMContext):
    _, _, bet_s, count_s = call.data.split(":")
    bet, mine_count = int(bet_s), int(count_s)
    uid = call.from_user.id
    await ensure_user(uid, call.from_user.username or call.from_user.first_name)
    if not await deduct(uid, bet, call):
        return
    mines_pos = random.sample(range(25), mine_count)
    await state.set_state(MinesState.playing)
    await state.update_data(bet=bet, mines=mine_count, mines_pos=mines_pos, revealed=[])
    mult = await mines_multiplier(0, mine_count)
    await call.message.edit_text(
        f"💣 <b>Мины</b> — {bet} ⭐ | {mine_count} мин | ×{mult}",
        reply_markup=mines_field([], None, mines_pos, mult, False), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("mines:open:"))
async def mines_open(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await call.answer("Игра не найдена. Начни новую.", show_alert=True)
        return
    idx = int(call.data.split(":")[2])
    mines_pos, revealed = data["mines_pos"], data["revealed"]
    bet, mine_count, uid = data["bet"], data["mines"], call.from_user.id
    if idx in mines_pos:
        await state.clear()
        await record_game(uid, "mines", bet, f"loss:hit:{idx}", 0)
        new_bal = await get_balance(uid)
        await call.message.edit_text(
            f"💥 <b>БУМ!</b> Мина!\n\nПотеря: -{bet} ⭐\n💰 Баланс: <b>{new_bal} ⭐</b>",
            reply_markup=mines_field(revealed, idx, mines_pos, 0, True), parse_mode="HTML",
        )
    else:
        revealed.append(idx)
        await state.update_data(revealed=revealed)
        mult = await mines_multiplier(len(revealed), mine_count)
        payout = int(bet * mult)
        await call.message.edit_text(
            f"💣 <b>Мины</b> — {bet} ⭐ | {mine_count} мин\n"
            f"Открыто: {len(revealed)} | ×{mult} | <b>{payout} ⭐</b>",
            reply_markup=mines_field(revealed, None, mines_pos, mult, False), parse_mode="HTML",
        )
    await call.answer()


@router.callback_query(F.data == "mines:cashout")
async def mines_cashout(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await call.answer("Игра не найдена.", show_alert=True)
        return
    revealed, bet = data["revealed"], data["bet"]
    mine_count, mines_pos = data["mines"], data["mines_pos"]
    uid = call.from_user.id
    mult = await mines_multiplier(len(revealed), mine_count)
    payout = int(bet * mult)
    await state.clear()
    await record_game(uid, "mines", bet, f"win:cashout:{len(revealed)}", payout)
    new_bal = await get_balance(uid)
    await call.message.edit_text(
        f"💰 <b>Забрал!</b> Открыто: {len(revealed)} | ×{mult}\n\n"
        + win_msg(bet, payout, new_bal),
        reply_markup=mines_field(revealed, None, mines_pos, mult, True), parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "mines:noop")
async def mines_noop(call: CallbackQuery):
    await call.answer()
