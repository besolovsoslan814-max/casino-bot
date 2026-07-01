from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db import SETTING_DEFAULTS


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎰 Слоты",     callback_data="game:slots"),
            InlineKeyboardButton(text="🎲 Кости",     callback_data="game:dice"),
            InlineKeyboardButton(text="💣 Мины",      callback_data="game:mines"),
        ],
        [
            InlineKeyboardButton(text="🪙 Монетка",  callback_data="game:coin"),
            InlineKeyboardButton(text="🚀 Краш",     callback_data="game:crash"),
            InlineKeyboardButton(text="📦 Кейсы",    callback_data="game:cases"),
        ],
        [
            InlineKeyboardButton(text="🎯 Дартс",    callback_data="game:darts"),
            InlineKeyboardButton(text="🎳 Боулинг",  callback_data="game:bowling"),
            InlineKeyboardButton(text="🏀 Баскет",   callback_data="game:basket"),
        ],
        [
            InlineKeyboardButton(text="💳 Stars",    callback_data="deposit"),
            InlineKeyboardButton(text="₿ Крипто",    callback_data="deposit:crypto"),
            InlineKeyboardButton(text="💸 Вывести",  callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton(text="📊 Стат",     callback_data="mystats"),
            InlineKeyboardButton(text="🏆 Топ",      callback_data="leaderboard"),
            InlineKeyboardButton(text="🤝 Партнёрка",callback_data="partner"),
        ],
        [
            InlineKeyboardButton(text="💬 Поддержка",callback_data="support"),
            InlineKeyboardButton(text="❓ Правила",   callback_data="rules"),
        ],
        [
            InlineKeyboardButton(text="🏢 Франшиза", callback_data="franchise"),
        ],
    ])


def bet_keyboard(game: str, bets: list[int] | None = None) -> InlineKeyboardMarkup:
    if bets is None:
        bets = [1, 5, 10, 25, 50, 100]
    rows, row = [], []
    for b in bets:
        row.append(InlineKeyboardButton(text=f"⭐ {b}", callback_data=f"bet:{game}:{b}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def coin_choice(bet: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🦅 Орёл",  callback_data=f"coin:heads:{bet}"),
            InlineKeyboardButton(text="🔵 Решка", callback_data=f"coin:tails:{bet}"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="game:coin")],
    ])


def crash_targets(bet: int) -> InlineKeyboardMarkup:
    targets = [("1.1×","1.1"),("1.3×","1.3"),("1.5×","1.5"),
               ("2×","2.0"),("5×","5.0"),("10×","10.0")]
    rows, row = [], []
    for label, val in targets:
        row.append(InlineKeyboardButton(text=label, callback_data=f"crash:{val}:{bet}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="game:crash")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cases_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥈 Серебряный — 50 ⭐",  callback_data="case:silver")],
        [InlineKeyboardButton(text="🥇 Золотой    — 200 ⭐", callback_data="case:gold")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu")],
    ])


def mines_count_keyboard(bet: int) -> InlineKeyboardMarkup:
    counts = [3, 5, 7, 10, 15]
    rows = [[InlineKeyboardButton(text=f"💣 {c}", callback_data=f"mines:start:{bet}:{c}")
             for c in counts]]
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="game:mines")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mines_field(revealed: list[int], mine_hit: int | None, mines_pos: list[int],
                cashout_mult: float, game_over: bool) -> InlineKeyboardMarkup:
    rows = []
    for row_i in range(5):
        row = []
        for col_i in range(5):
            idx = row_i * 5 + col_i
            if game_over and idx in mines_pos:
                text = "💣"
            elif idx in revealed:
                text = "✅"
            elif mine_hit == idx:
                text = "💥"
            else:
                text = "⬜"
            cb = ("mines:noop" if (game_over or idx in revealed or mine_hit is not None)
                  else f"mines:open:{idx}")
            row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(row)
    if not game_over and mine_hit is None and revealed:
        rows.append([InlineKeyboardButton(
            text=f"💰 Забрать × {cashout_mult:.2f}", callback_data="mines:cashout"
        )])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def deposit_keyboard() -> InlineKeyboardMarkup:
    amounts = [100, 200, 500, 1000, 2500, 5000]
    rows, row = [], []
    for a in amounts:
        row.append(InlineKeyboardButton(text=f"⭐ {a}", callback_data=f"pay:{a}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crypto_currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USDT (TRC20)", callback_data="crypto:USDT (TRC20)")],
        [InlineKeyboardButton(text="₿ BTC",           callback_data="crypto:BTC")],
        [InlineKeyboardButton(text="💎 ETH",           callback_data="crypto:ETH")],
        [InlineKeyboardButton(text="🔙 Назад",         callback_data="menu")],
    ])


def crypto_amount_keyboard(currency: str) -> InlineKeyboardMarkup:
    amounts = [("10$", 10), ("25$", 25), ("50$", 50), ("100$", 100)]
    rows = []
    for label, val in amounts:
        rows.append([InlineKeyboardButton(
            text=label, callback_data=f"crypto_amount:{currency}:{val}"
        )])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="deposit:crypto")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика",     callback_data="admin:stats"),
            InlineKeyboardButton(text="🏆 Топ игроков",    callback_data="admin:top"),
        ],
        [
            InlineKeyboardButton(text="🔍 Найти игрока",   callback_data="admin:find"),
            InlineKeyboardButton(text="💰 Баланс",         callback_data="admin:balance"),
        ],
        [
            InlineKeyboardButton(text="🎮 Последние игры", callback_data="admin:games"),
            InlineKeyboardButton(text="📤 Выводы",         callback_data="admin:withdrawals"),
        ],
        [
            InlineKeyboardButton(text="🤝 Партнёры",       callback_data="admin:partners"),
            InlineKeyboardButton(text="₿ Крипто",          callback_data="admin:crypto"),
        ],
        [
            InlineKeyboardButton(text="💬 Тикеты",         callback_data="admin:tickets"),
            InlineKeyboardButton(text="⚙️ Настройки игр",  callback_data="admin:settings"),
        ],
        [
            InlineKeyboardButton(text="🏢 Франшизы",       callback_data="admin:franchises"),
            InlineKeyboardButton(text="📢 Рассылка",        callback_data="admin:broadcast"),
        ],
        [InlineKeyboardButton(text="✖️ Закрыть",           callback_data="admin:close")],
    ])


def settings_keyboard(current: dict[str, str]) -> InlineKeyboardMarkup:
    """One button per setting showing key + current value."""
    rows = []
    for key, (default, label) in SETTING_DEFAULTS.items():
        val = current.get(key, default)
        rows.append([InlineKeyboardButton(
            text=f"{label}: {val}",
            callback_data=f"setting:{key}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_admin_keyboard(ticket_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✏️ Ответить",
            callback_data=f"support_reply:{ticket_id}:{user_id}",
        )],
        [InlineKeyboardButton(
            text="✅ Закрыть без ответа",
            callback_data=f"support_close:{ticket_id}",
        )],
    ])


def back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin:panel")]
    ])


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")]
    ])
