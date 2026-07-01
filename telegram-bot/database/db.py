import time
import aiosqlite
from config import DB_PATH

# ── Settings cache (60s TTL) ──────────────────────────────────────────────────
_settings_cache: dict[str, str] = {}
_cache_ts: dict[str, float] = {}
_CACHE_TTL = 60.0

SETTING_DEFAULTS: dict[str, tuple[str, str]] = {
    "dice_mult":               ("1.5",  "🎲 Кости — множитель (только 6)"),
    "darts_mult":              ("1.5",  "🎯 Дартс — множитель (только 6)"),
    "bowling_mult":            ("1.5",  "🎳 Боулинг — множитель (только 6)"),
    "basket_mult":             ("1.5",  "🏀 Баскет — множитель (4 или 5)"),
    "coin_win_chance":         ("0.10", "🪙 Монетка — шанс победы (0.0-1.0)"),
    "coin_win_mult":           ("8.0",  "🪙 Монетка — множитель победы"),
    "crash_jackpot_chance":    ("0.01", "🚀 Краш — шанс ×10 (0.0-1.0)"),
    "crash_jackpot_mult":      ("10.0", "🚀 Краш — джекпот множитель"),
    "mines_house_edge":        ("0.10", "💣 Мины — house edge (0.0-1.0)"),
    "case_silver_win_weight":  ("5",    "📦 Серебро — вес ДЖЕКПОТА (из 1000)"),
    "case_silver_win_mult":    ("3.0",  "📦 Серебро — множитель джекпота"),
    "case_silver_partial_w":   ("300",  "📦 Серебро — вес частичного возврата (из 1000)"),
    "case_gold_win_weight":    ("5",    "📦 Золото — вес ДЖЕКПОТА (из 1000)"),
    "case_gold_win_mult":      ("20.0", "📦 Золото — множитель джекпота"),
    "case_gold_partial_w":     ("300",  "📦 Золото — вес частичного возврата (из 1000)"),
    "slots_bar_mult":          ("3.0",  "🎰 Слоты — BAR BAR BAR множитель"),
    "slots_grape_mult":        ("5.0",  "🎰 Слоты — Виноград множитель"),
    "slots_lemon_mult":        ("5.0",  "🎰 Слоты — Лимон множитель"),
    "slots_seven_mult":        ("15.0", "🎰 Слоты — ДЖЕКПОТ 777 множитель"),
}


async def get_setting(key: str) -> str:
    now = time.time()
    if key in _settings_cache and now - _cache_ts.get(key, 0) < _CACHE_TTL:
        return _settings_cache[key]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            val = row[0] if row else SETTING_DEFAULTS.get(key, ("", ""))[0]
    _settings_cache[key] = val
    _cache_ts[key] = now
    return val


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()
    _settings_cache[key] = value
    _cache_ts[key] = time.time()


async def get_all_settings() -> dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM settings") as cur:
            stored = {r[0]: r[1] for r in await cur.fetchall()}
    result = {}
    for key, (default, _) in SETTING_DEFAULTS.items():
        result[key] = stored.get(key, default)
    return result


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                balance     INTEGER DEFAULT 0,
                total_in    INTEGER DEFAULT 0,
                total_out   INTEGER DEFAULT 0,
                games_won   INTEGER DEFAULT 0,
                games_lost  INTEGER DEFAULT 0,
                ref_by      INTEGER DEFAULT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                game        TEXT,
                bet         INTEGER,
                result      TEXT,
                payout      INTEGER,
                played_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER,
                amount       INTEGER,
                method       TEXT DEFAULT 'stars',
                status       TEXT DEFAULT 'pending',
                requested_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS partners (
                user_id    INTEGER PRIMARY KEY,
                ref_code   TEXT UNIQUE,
                earnings   INTEGER DEFAULT 0,
                pending    INTEGER DEFAULT 0,
                referrals  INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crypto_deposits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                currency    TEXT,
                amount_fiat REAL,
                stars       INTEGER,
                status      TEXT DEFAULT 'pending',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER,
                username     TEXT,
                text         TEXT,
                admin_msg_id INTEGER,
                status       TEXT DEFAULT 'open',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS franchise_bots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id     INTEGER UNIQUE,
                bot_token    TEXT UNIQUE,
                bot_username TEXT,
                bot_id       INTEGER,
                status       TEXT DEFAULT 'pending',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # seed default settings (INSERT OR IGNORE keeps existing values)
        for key, (default, _) in SETTING_DEFAULTS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, default)
            )
        # migrations: add columns if missing
        for col_def in [
            ("users", "ref_by INTEGER DEFAULT NULL"),
            ("users", "games_won INTEGER DEFAULT 0"),
            ("users", "games_lost INTEGER DEFAULT 0"),
            ("withdrawals", "method TEXT DEFAULT 'stars'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]}")
            except Exception:
                pass
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def ensure_user(user_id: int, username: str, ref_by: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, ref_by) VALUES (?, ?, ?)",
            (user_id, username, ref_by),
        )
        await db.execute(
            "UPDATE users SET username = ? WHERE user_id = ?", (username, user_id)
        )
        if ref_by:
            await db.execute(
                "UPDATE partners SET referrals = referrals + 1 WHERE user_id = ?", (ref_by,)
            )
        await db.commit()


async def get_balance(user_id: int) -> int:
    user = await get_user(user_id)
    return user["balance"] if user else 0


async def change_balance(user_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id)
        )
        await db.commit()


async def record_deposit(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, total_in = total_in + ? WHERE user_id = ?",
            (amount, amount, user_id),
        )
        await db.commit()


async def record_game(user_id: int, game: str, bet: int, result: str, payout: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO games (user_id, game, bet, result, payout) VALUES (?, ?, ?, ?, ?)",
            (user_id, game, bet, result, payout),
        )
        # Bet already removed by deduct() — only add payout back (0 if full loss)
        if payout > 0:
            await db.execute(
                "UPDATE users SET balance = balance + ?, total_out = total_out + ? "
                "WHERE user_id = ?",
                (payout, payout, user_id),
            )
        if payout >= bet:
            await db.execute(
                "UPDATE users SET games_won = games_won + 1 WHERE user_id = ?", (user_id,)
            )
        else:
            await db.execute(
                "UPDATE users SET games_lost = games_lost + 1 WHERE user_id = ?", (user_id,)
            )
        casino_profit = bet - payout
        if casino_profit > 0:
            async with db.execute(
                "SELECT ref_by FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                if row and row[0]:
                    share = casino_profit // 2
                    await db.execute(
                        "UPDATE partners SET earnings = earnings + ?, pending = pending + ? "
                        "WHERE user_id = ?",
                        (share, share, row[0]),
                    )
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) as players, SUM(total_in) as total_in, SUM(total_out) as total_out, "
            "SUM(games_won) as games_won, SUM(games_lost) as games_lost FROM users"
        ) as cur:
            row = dict(await cur.fetchone())
        async with db.execute("SELECT COUNT(*) FROM games") as cur:
            row["total_games"] = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM games WHERE played_at >= datetime('now', '-1 day')"
        ) as cur:
            row["games_today"] = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM partners") as cur:
            row["partners"] = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE status = 'open'"
        ) as cur:
            row["open_tickets"] = (await cur.fetchone())[0]
        row["total_in"]   = row["total_in"]  or 0
        row["total_out"]  = row["total_out"] or 0
        row["profit"]     = row["total_in"]  - row["total_out"]
        row["games_won"]  = row["games_won"] or 0
        row["games_lost"] = row["games_lost"] or 0
        return row


async def get_top_players(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, balance, games_won, games_lost FROM users "
            "ORDER BY balance DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_recent_games(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT g.game, g.bet, g.payout, g.result, g.played_at, u.username "
            "FROM games g JOIN users u ON g.user_id = u.user_id "
            "ORDER BY g.id DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            return [r[0] for r in await cur.fetchall()]


async def add_withdrawal(user_id: int, amount: int, method: str = "stars") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO withdrawals (user_id, amount, method) VALUES (?, ?, ?)",
            (user_id, amount, method),
        )
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id)
        )
        await db.commit()
        return cur.lastrowid


async def get_pending_withdrawals() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT w.*, u.username FROM withdrawals w JOIN users u ON w.user_id = u.user_id "
            "WHERE w.status = 'pending' ORDER BY w.requested_at DESC LIMIT 10"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Partner ───────────────────────────────────────────────────────────────────

async def get_or_create_partner(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM partners WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
        import hashlib
        code = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:8].upper()
        await db.execute(
            "INSERT INTO partners (user_id, ref_code) VALUES (?, ?)", (user_id, code)
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM partners WHERE user_id = ?", (user_id,)
        ) as cur:
            return dict(await cur.fetchone())


async def get_partner_by_code(code: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM partners WHERE ref_code = ?", (code.upper(),)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def withdraw_partner_earnings(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE partners SET pending = pending - ? WHERE user_id = ?", (amount, user_id)
        )
        await db.commit()


async def add_crypto_deposit(user_id: int, currency: str, amount_fiat: float, stars: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO crypto_deposits (user_id, currency, amount_fiat, stars) VALUES (?, ?, ?, ?)",
            (user_id, currency, amount_fiat, stars),
        )
        await db.commit()
        return cur.lastrowid


# ── Support ───────────────────────────────────────────────────────────────────

async def create_support_ticket(user_id: int, username: str, text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO support_tickets (user_id, username, text) VALUES (?, ?, ?)",
            (user_id, username, text),
        )
        await db.commit()
        return cur.lastrowid


async def set_ticket_admin_msg(ticket_id: int, admin_msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE support_tickets SET admin_msg_id = ? WHERE id = ?",
            (admin_msg_id, ticket_id),
        )
        await db.commit()


async def get_ticket(ticket_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def close_ticket(ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE support_tickets SET status = 'closed' WHERE id = ?", (ticket_id,)
        )
        await db.commit()


async def get_open_tickets(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_tickets WHERE status = 'open' "
            "ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Franchise ─────────────────────────────────────────────────────────────────

async def create_franchise(owner_id: int, bot_token: str,
                           bot_username: str, bot_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO franchise_bots "
            "(owner_id, bot_token, bot_username, bot_id) VALUES (?, ?, ?, ?)",
            (owner_id, bot_token, bot_username, bot_id),
        )
        await db.commit()
        return cur.lastrowid or 0


async def activate_franchise(franchise_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE franchise_bots SET status = 'active' WHERE id = ?",
            (franchise_id,),
        )
        await db.commit()


async def get_franchise_by_owner(owner_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM franchise_bots WHERE owner_id = ?", (owner_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_active_franchises() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM franchise_bots WHERE status = 'active'"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_franchises() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM franchise_bots ORDER BY created_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_or_create_partner(user_id: int) -> dict:
    """Ensure a partner record exists; return it."""
    import random, string
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM partners WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
        ref_code = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        await db.execute(
            "INSERT OR IGNORE INTO partners (user_id, ref_code) VALUES (?, ?)",
            (user_id, ref_code),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM partners WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}
