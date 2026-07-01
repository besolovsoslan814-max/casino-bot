import os

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
ADMIN_ID: int = int(os.environ["ADMIN_ID"])

# ── Слоты (реальные комбинации Telegram 🎰) ────────────────────────────────
SLOTS_COMBOS = {
    1:  {"name": "BAR BAR BAR",     "mult": 3.0,  "emoji": "🍫"},
    22: {"name": "Виноград 🍇🍇🍇",  "mult": 5.0,  "emoji": "🍇"},
    43: {"name": "Лимон 🍋🍋🍋",     "mult": 5.0,  "emoji": "🍋"},
    64: {"name": "ДЖЕКПОТ 7️⃣7️⃣7️⃣", "mult": 15.0, "emoji": "7️⃣"},
}

# ── Кости (🎲) — только 6, коэф 1.5 ──────────────────────────────────────
DICE_SIX_MULT = 1.5

# ── Баскет / Дартс / Боулинг → × 1.5 ─────────────────────────────────────
BASKET_WIN_VALUES = {4, 5}
BASKET_MULT = 1.5

DARTS_WIN_VALUE = 6
DARTS_MULT = 1.5

BOWLING_WIN_VALUE = 6
BOWLING_MULT = 1.5

# ── Орёл/Решка: 10% шанс на выигрыш (≈5 из 50) ───────────────────────────
COIN_WIN_CHANCE = 0.10   # 10% победа
COIN_WIN_MULT   = 8.0    # × 8 при победе

# ── Краш 🚀: 99% крашится на 1.0-1.5, 1% — достигает × 10 ───────────────
# Реализация через «выбор целевого множителя» до броска

# ── Кейсы 📦: 0.5% шанс выиграть; остальное — 0 или 0.1-0.9 ──────────────
CASES = {
    "silver": {
        "name": "🥈 Серебряный кейс",
        "price": 50,
        "items": [
            # (name, min_mult, max_mult, weight)
            {"name": "💀 Ничего",          "mult": 0.0,            "var": False, "weight": 695},
            {"name": "🔴 Частичный возврат","mult": None,           "var": True,  "weight": 300,
             "mult_min": 0.1, "mult_max": 0.9},
            {"name": "✨ Выигрыш",         "mult": 3.0,            "var": False, "weight": 5},
        ],
    },
    "gold": {
        "name": "🥇 Золотой кейс",
        "price": 200,
        "items": [
            {"name": "💀 Ничего",          "mult": 0.0,            "var": False, "weight": 695},
            {"name": "🔴 Частичный возврат","mult": None,           "var": True,  "weight": 300,
             "mult_min": 0.3, "mult_max": 0.9},
            {"name": "🌟 ДЖЕКПОТ",         "mult": 20.0,           "var": False, "weight": 5},
        ],
    },
}

# ── Мины ──────────────────────────────────────────────────────────────────
MINES_HOUSE_EDGE = 0.10

# ── Партнёрка ──────────────────────────────────────────────────────────────
PARTNER_SHARE = 0.50        # 50% от профита казино идёт партнёру

# ── Крипто (задай адреса через Replit Secrets) ────────────────────────────
CRYPTO_WALLETS = {
    "USDT (TRC20)": os.environ.get("WALLET_USDT_TRC20", ""),
    "BTC":          os.environ.get("WALLET_BTC", ""),
    "ETH":          os.environ.get("WALLET_ETH", ""),
}
STARS_PER_USDT = int(os.environ.get("STARS_PER_USDT", "50"))  # курс обмена

# ── Общее ─────────────────────────────────────────────────────────────────
MIN_BET      = 1
MAX_BET      = 500
MIN_DEPOSIT  = 100
MIN_WITHDRAW = 50
DB_PATH      = os.environ.get("DB_PATH", "casino.db")
