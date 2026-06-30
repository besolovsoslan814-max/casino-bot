/**
 * Telegram Casino Bot — v2
 * - Slots game
 * - PvP Arena (bet Stars, proportional win chance, 10% house edge)
 * - Promo codes
 * - Admin panel INSIDE the bot (Telegram ID check)
 * - Payments via Telegram Stars
 */

require('dotenv').config();
const express = require('express');
const TelegramBot = require('node-telegram-bot-api');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

// ─── Config ──────────────────────────────────────────────────────────────
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const PORT = process.env.PORT || 3000;
const WEBAPP_URL = process.env.WEBAPP_URL || `http://localhost:${PORT}`;
const ADMIN_IDS = (process.env.ADMIN_IDS || '').split(',').map(Number).filter(Boolean);

if (!BOT_TOKEN) { console.error('❌ TELEGRAM_BOT_TOKEN required!'); process.exit(1); }
if (!ADMIN_IDS.length) console.warn('⚠️  ADMIN_IDS not set — admin panel disabled');

// ─── Express ─────────────────────────────────────────────────────────────
const app = express();
app.use(cors());
app.use(express.json());
// Serve static files if dist exists
const distPath = path.join(__dirname, '../dist');
if (fs.existsSync(distPath)) {
  app.use(express.static(distPath));
}

// ─── Bot ─────────────────────────────────────────────────────────────────
let bot;
try {
  bot = new TelegramBot(BOT_TOKEN, { polling: false });
  console.log('🤖 Bot created (webhook mode)...');
} catch (err) {
  console.error('❌ Failed to create bot:', err.message);
  // Don't exit - let server run for health checks
}

// Set webhook if bot is available
if (bot && WEBAPP_URL && !WEBAPP_URL.includes('localhost')) {
  const webhookUrl = `${WEBAPP_URL}/webhook`;
  bot.setWebHook(webhookUrl)
    .then(() => console.log(`🔗 Webhook set: ${webhookUrl}`))
    .catch(err => console.error('⚠️ Webhook error:', err.message));
} else if (bot) {
  // Fallback to polling for local dev
  try {
    bot.startPolling();
    console.log('🔄 Polling started...');
  } catch (err) {
    console.error('⚠️ Polling error:', err.message);
  }
}

// Webhook endpoint
app.post('/webhook', (req, res) => {
  if (!bot) return res.sendStatus(503);
  bot.processUpdate(req.body);
  res.sendStatus(200);
});

// ─── Data Stores ─────────────────────────────────────────────────────────
const users = new Map();
const promos = new Map();
const arena = { active: false, players: new Map(), startTime: null, duration: 60000 }; // 60s round
let adminStates = new Map(); // adminId -> current menu state

function getUser(id) {
  if (!users.has(id)) {
    users.set(id, { id, firstName: '', username: '', balance: 0, totalBet: 0, totalWon: 0, spins: 0, banned: false, createdAt: new Date() });
  }
  return users.get(id);
}

function isAdmin(id) { return ADMIN_IDS.includes(id); }

// ─── Slots Game Logic ────────────────────────────────────────────────────
const SYMBOLS = ['🍒','🍋','🍊','🍇','💎','7️⃣','⭐','🎰'];
const WEIGHTS = { '🍒':200,'🍋':200,'🍊':180,'🍇':150,'💎':120,'7️⃣':80,'⭐':50,'🎰':20 };
const PAYOUTS = { '🍒':2,'🍋':3,'🍊':4,'🍇':5,'💎':10,'7️⃣':15,'⭐':20,'🎰':50 };
const WIN_CHANCE = { three: 0.03, two: 0.08 };
const HOUSE_EDGE = 0.97;

function randSymbol() {
  const total = Object.values(WEIGHTS).reduce((a,b)=>a+b,0);
  let r = Math.random()*total;
  for (const [s,w] of Object.entries(WEIGHTS)) { r-=w; if(r<=0) return s; }
  return SYMBOLS[0];
}

function spin() { return [randSymbol(), randSymbol(), randSymbol()]; }

function calcWin(res, bet) {
  const three = res[0]===res[1] && res[1]===res[2];
  const two = !three && (res[0]===res[1]||res[1]===res[2]||res[0]===res[2]);
  let win = 0;
  if (three && Math.random()<WIN_CHANCE.three) win = Math.floor(bet*(PAYOUTS[res[0]]||1)*(1-HOUSE_EDGE));
  else if (two && Math.random()<WIN_CHANCE.two) win = Math.floor(bet*1.5*(1-HOUSE_EDGE));
  return { results:res, winAmount:win, isWin:win>0, allMatch:three, twoMatch:two };
}

// ─── PvP Arena Logic ─────────────────────────────────────────────────────
function startArena() {
  arena.active = true;
  arena.players = new Map();
  arena.startTime = Date.now();

  const msg = `⚔️ *PvP Арена открыта!*\n\n` +
    `💰 Ставьте монеты — чем больше ставка, тем выше шанс выиграть!\n` +
    `🏦 Казино берёт 10% от банка\n` +
    `⏱ Раунд длится 60 секунд\n\n` +
    `Жми «⚔️ Войти в арену» чтобы участвовать!`;

  bot.sendMessage(process.env.CHAT_ID || '*',{ // broadcast to all users
    text: msg,
    parse_mode: 'Markdown',
    reply_markup: { inline_keyboard: [[{ text: '⚔️ Войти в арену', callback_data: 'arena_join' }]] }
  }).catch(()=>{});

  // Also send to all known users
  for (const [userId] of users) {
    bot.sendMessage(userId, msg, {
      parse_mode: 'Markdown',
      reply_markup: { inline_keyboard: [[{ text: '⚔️ Войти в арену', callback_data: 'arena_join' }]] }
    }).catch(()=>{});
  }

  // End round after duration
  setTimeout(endArena, arena.duration);
}

function endArena() {
  if (!arena.active || arena.players.size === 0) {
    arena.active = false;
    for (const [userId] of users) {
      bot.sendMessage(userId, '⚔️ Арена завершена. Никто не участвовал.').catch(()=>{});
    }
    return;
  }

  // Calculate winner based on proportional chance
  const entries = Array.from(arena.players.entries()); // [userId, bet]
  const totalPot = entries.reduce((sum, [,bet]) => sum + bet, 0);
  const houseFee = Math.floor(totalPot * 0.10);
  const prizePool = totalPot - houseFee;

  // Each player's chance = their bet / total pot
  let random = Math.random() * totalPot;
  let winnerId = entries[0][0];

  for (const [userId, bet] of entries) {
    random -= bet;
    if (random <= 0) { winnerId = userId; break; }
  }

  const winner = getUser(winnerId);
  winner.balance += prizePool;
  winner.totalWon += prizePool;

  const winnerName = winner.firstName || String(winnerId);
  const resultMsg = `🏆 *Арена завершена!*\n\n` +
    `👥 Участников: ${entries.length}\n` +
    `💰 Банк: ${totalPot} монет\n` +
    `🏦 Комиссия казино (10%): ${houseFee} монет\n` +
    `🎉 Победитель: *${winnerName}*\n` +
    `💎 Выигрыш: *${prizePool} монет*\n\n` +
    `Поздравляем! 🎊`;

  for (const [userId] of users) {
    bot.sendMessage(userId, resultMsg, { parse_mode: 'Markdown' }).catch(()=>{});
  }

  arena.active = false;
  arena.players = new Map();
}

// ─── Bot Commands ────────────────────────────────────────────────────────
bot.onText(/\/start/, (msg) => {
  const user = getUser(msg.from.id);
  user.firstName = msg.from.first_name;
  user.username = msg.from.username || '';

  const keyboard = [
    [{ text: '🎰 Играть', web_app: { url: WEBAPP_URL } }],
    [{ text: '⚔️ PvP Арена', callback_data: 'arena_info' }],
    [{ text: '🎫 Промокод', callback_data: 'promo' }],
    [{ text: '💰 Купить монеты', callback_action: 'buy_coins' }],
    [{ text: '📊 Статистика', callback_data: 'stats' }],
    [{ text: 'ℹ️ Помощь', callback_data: 'help' }],
  ];

  // Admin button only for admin IDs
  if (isAdmin(msg.from.id)) {
    keyboard.push([{ text: '🔧 Админ-панель', callback_data: 'admin_menu' }]);
  }

  bot.sendMessage(msg.chat.id, `🎰 Добро пожаловать в Казино, ${user.firstName}!`, {
    reply_markup: { inline_keyboard: keyboard }
  });
});

bot.onText(/\/help/, (msg) => {
  bot.sendMessage(msg.chat.id,
    `🎰 *Казино Бот*\n\n` +
    `🔹 *Слоты* — жми «Играть»\n` +
    `🔹 *PvP Арена* — ставь монеты, побеждает тот, кто поставил больше!\n` +
    `🔹 *Промокоды* — вводи коды для бонусов\n` +
    `🔹 *Покупка* —.buy Stars за монеты\n\n` +
    `*Таблица выплат (слоты):*\n` +
    `🍒×2 🍋×3 🍊×4 🍇×5 💎×10 7️⃣×15 ⭐×20 🎰×50`,
    { parse_mode: 'Markdown' }
  );
});

// ─── Callback Handler ────────────────────────────────────────────────────
bot.on('callback_query', async (query) => {
  const chatId = query.message.chat.id;
  const userId = query.from.id;
  const data = query.data;
  const user = getUser(userId);
  user.firstName = query.from.first_name;

  // ── Admin callbacks ──
  if (data.startsWith('admin_')) {
    if (!isAdmin(userId)) return bot.answerCallbackQuery(query.id, { text: 'Нет доступа' });
    return handleAdmin(query);
  }

  // ── Regular callbacks ──
  if (data === 'stats') {
    bot.answerCallbackQuery(query.id);
    bot.sendMessage(chatId,
      `📊 *Твоя статистика:*\n\n` +
      `💰 Баланс: ${user.balance} монет\n` +
      `🔄 Всего игр: ${user.spins}\n` +
      `💸 Ставок: ${user.totalBet}\n` +
      `🏆 Выигрышей: ${user.totalWon}`,
      { parse_mode: 'Markdown' }
    );
  }
  else if (data === 'help') {
    bot.answerCallbackQuery(query.id);
    bot.sendMessage(chatId, `ℹ️ Жми «Играть» для слотов или «PvP Арена» для PvP!`);
  }
  else if (data === 'promo') {
    bot.answerCallbackQuery(query.id);
    bot.sendMessage(chatId, '🎫 Отправь код промокода в чат:');
  }
  // ── PvP Arena ──
  else if (data === 'arena_info') {
    bot.answerCallbackQuery(query.id);
    if (arena.active) {
      const total = Array.from(arena.players.values()).reduce((a,b)=>a+b,0);
      const joined = arena.players.size;
      const myBet = arena.players.get(userId) || 0;
      const left = Math.max(0, 60 - Math.floor((Date.now()-arena.startTime)/1000));
      bot.sendMessage(chatId,
        `⚔️ *Арена активна!*\n\n` +
        `👥 Участников: ${joined}\n` +
        `💰 Банк: ${total} монет\n` +
        `⏳ Осталось: ${left} сек\n` +
        `${myBet > 0 ? `🎫 Твоя ставка: ${myBet} монет` : 'Ты ещё не участвуешь'}`,
        { parse_mode: 'Markdown',
          reply_markup: { inline_keyboard: [[{ text: myBet > 0 ? '⬆️ Увеличить ставку' : '⚔️ Войти', callback_data: 'arena_join' }]] }
        }
      );
    } else {
      bot.sendMessage(chatId, `⚔️ Арена сейчас неактивна.\n\nОжидайте следующего раунда!`);
    }
  }
  else if (data === 'arena_join') {
    bot.answerCallbackQuery(query.id);
    if (!arena.active) return bot.sendMessage(chatId, '⚔️ Арена не активна');
    if (user.balance < 10) return bot.sendMessage(chatId, '❌ Минимум 10 монет для входа');

    const currentBet = arena.players.get(userId) || 0;
    const newBet = Math.min(100, user.balance); // auto bet 100 or all

    if (user.balance < newBet) return bot.sendMessage(chatId, '❌ Недостаточно монет');

    user.balance -= (newBet - currentBet);
    arena.players.set(userId, newBet);

    const total = Array.from(arena.players.values()).reduce((a,b)=>a+b,0);
    const left = Math.max(0, 60 - Math.floor((Date.now()-arena.startTime)/1000));

    bot.sendMessage(chatId,
      `✅ Ставка принята: *${newBet} монет*\n\n` +
      `💰 Банк: ${total} монет\n` +
      `👥 Участников: ${arena.players.size}\n` +
      `⏳ Осталось: ${left} сек`,
      { parse_mode: 'Markdown' }
    );
  }
});

// ─── Promo Code Handler ──────────────────────────────────────────────────
bot.on('message', (msg) => {
  if (!msg.text || msg.text.startsWith('/')) return;
  if (msg.reply_to_message && msg.reply_to_message.text && msg.reply_to_message.text.includes('промокод')) {
    const code = msg.text.trim().toUpperCase();
    const user = getUser(msg.from.id);
    const promo = promos.get(code);

    if (!promo) return bot.sendMessage(msg.chat.id, '❌ Промокод не найден');
    if (!promo.active) return bot.sendMessage(msg.chat.id, '❌ Промокод деактивирован');
    if (promo.used >= promo.limit) return bot.sendMessage(msg.chat.id, '❌ Лимит исчерпан');

    promo.used++;
    user.balance += promo.bonus;
    bot.sendMessage(msg.chat.id, `✅ Промокод активирован!\n💰 +${promo.bonus} монет\n💎 Баланс: ${user.balance}`);
  }
});

// ─── Admin Panel (inside bot) ────────────────────────────────────────────
async function handleAdmin(query) {
  const userId = query.from.id;
  const chatId = query.message.chat.id;
  const data = query.data;

  bot.answerCallbackQuery(query.id);

  // Main menu
  if (data === 'admin_menu') {
    adminStates.set(userId, 'main');
    return bot.sendMessage(chatId, '🔧 *Админ-панель*\n\nВыберите действие:', {
      parse_mode: 'Markdown',
      reply_markup: { inline_keyboard: [
        [{ text: '📊 Статистика', callback_data: 'admin_stats' }],
        [{ text: '👥 Пользователи', callback_data: 'admin_users' }],
        [{ text: '🎫 Промокоды', callback_data: 'admin_promos' }],
        [{ text: '📢 Рассылка', callback_data: 'admin_broadcast' }],
        [{ text: '⚔️ Арена', callback_data: 'admin_arena' }],
        [{ text: '🎁 Выдать бонус', callback_data: 'admin_givebonus' }],
      ]}
    });
  }

  // Stats
  if (data === 'admin_stats') {
    let totalSpins=0, totalBets=0, totalWon=0, banned=0;
    users.forEach(u => { totalSpins+=u.spins; totalBets+=u.totalBet; totalWon+=u.totalWon; if(u.banned)banned++; });
    return bot.sendMessage(chatId,
      `📊 *Статистика:*\n\n` +
      `👥 Пользователей: ${users.size}\n` +
      `🔄 Всего игр: ${totalSpins}\n` +
      `💸 Всего ставок: ${totalBets}\n` +
      `🏆 Всего выигрышей: ${totalWon}\n` +
      `💰 Профит: ${totalBets-totalWon}\n` +
      `🔒 Забанено: ${banned}`,
      { parse_mode: 'Markdown',
        reply_markup: { inline_keyboard: [[{ text: '◀️ Назад', callback_data: 'admin_menu' }]] }
      }
    );
  }

  // Users list
  if (data === 'admin_users') {
    adminStates.set(userId, 'users');
    const list = Array.from(users.values()).slice(0, 10);
    if (!list.length) return bot.sendMessage(chatId, '👥 Пока нет пользователей', { reply_markup: { inline_keyboard: [[{ text: '◀️ Назад', callback_data: 'admin_menu' }]] } });

    const buttons = list.map(u => [{ text: `${u.firstName||u.id} | 💰${u.balance}`, callback_data: `admin_user_${u.id}` }]);
    buttons.push([{ text: '◀️ Назад', callback_data: 'admin_menu' }]);

    return bot.sendMessage(chatId, `👥 *Пользователи (${users.size}):*`, {
      parse_mode: 'Markdown',
      reply_markup: { inline_keyboard: buttons }
    });
  }

  // User detail
  if (data.startsWith('admin_user_')) {
    const uid = parseInt(data.replace('admin_user_', ''));
    const u = getUser(uid);
    adminStates.set(userId, `user_${uid}`);
    return bot.sendMessage(chatId,
      `👤 *${u.firstName||uid}*\n\n` +
      `🆔 ID: ${uid}\n` +
      `💰 Баланс: ${u.balance}\n` +
      `🔄 Игр: ${u.spins}\n` +
      `💸 Ставок: ${u.totalBet}\n` +
      `🏆 Выигрышей: ${u.totalWon}\n` +
      `🔒 Статус: ${u.banned ? 'ЗАБАНЕН' : 'Активен'}`,
      { parse_mode: 'Markdown',
        reply_markup: { inline_keyboard: [
          [{ text: '🎁 Выдать бонус', callback_data: `admin_bonus_${uid}` }],
          [u.banned
            ? { text: '🔓 Разбанить', callback_data: `admin_unban_${uid}` }
            : { text: '🔒 Забанить', callback_data: `admin_ban_${uid}` }
          ],
          [{ text: '◀️ Назад', callback_data: 'admin_users' }]
        ]}
      }
    );
  }

  // Ban
  if (data.startsWith('admin_ban_')) {
    const uid = parseInt(data.replace('admin_ban_', ''));
    getUser(uid).banned = true;
    bot.sendMessage(chatId, `🔒 Пользователь ${uid} забанен`);
    return handleAdmin({ ...query, data: `admin_user_${uid}` });
  }

  // Unban
  if (data.startsWith('admin_unban_')) {
    const uid = parseInt(data.replace('admin_unban_', ''));
    getUser(uid).banned = false;
    bot.sendMessage(chatId, `🔓 Пользователь ${uid} разбанен`);
    return handleAdmin({ ...query, data: `admin_user_${uid}` });
  }

  // Bonus prompt
  if (data.startsWith('admin_bonus_')) {
    const uid = parseInt(data.replace('admin_bonus_', ''));
    adminStates.set(userId, `bonus_${uid}`);
    return bot.sendMessage(chatId, `🎁 Отправьте количество монет для пользователя ${uid}:`);
  }

  // Give bonus (handled in message handler below)

  // Promos
  if (data === 'admin_promos') {
    const list = Array.from(promos.values());
    const buttons = list.map(p => [{ text: `${p.code} | 💰${p.bonus} | ${p.used}/${p.limit}`, callback_data: `admin_promo_${p.code}` }]);
    buttons.push([{ text: '➕ Новый промокод', callback_data: 'admin_newpromo' }]);
    buttons.push([{ text: '◀️ Назад', callback_data: 'admin_menu' }]);

    return bot.sendMessage(chatId, `🎫 *Промокоды (${list.length}):*`, {
      parse_mode: 'Markdown',
      reply_markup: { inline_keyboard: buttons }
    });
  }

  // Promo detail
  if (data.startsWith('admin_promo_') && data !== 'admin_promos' && data !== 'admin_newpromo') {
    const code = data.replace('admin_promo_', '');
    const p = promos.get(code);
    if (!p) return bot.sendMessage(chatId, '❌ Не найден');

    return bot.sendMessage(chatId,
      `🎫 *${p.code}*\n\n` +
      `💰 Бонус: ${p.bonus}\n` +
      `📊 Использовано: ${p.used}/${p.limit}\n` +
      `🟢 Статус: ${p.active ? 'Активен' : 'Выкл'}`,
      { parse_mode: 'Markdown',
        reply_markup: { inline_keyboard: [
          [{ text: p.active ? '🔴 Выключить' : '🟢 Включить', callback_data: `admin_toggpromo_${p.code}` }],
          [{ text: '🗑 Удалить', callback_data: `admin_delpromo_${p.code}` }],
          [{ text: '◀️ Назад', callback_data: 'admin_promos' }]
        ]}
      }
    );
  }

  // Toggle promo
  if (data.startsWith('admin_toggpromo_')) {
    const code = data.replace('admin_toggpromo_', '');
    const p = promos.get(code);
    if (p) p.active = !p.active;
    bot.sendMessage(chatId, `${p?.active ? '🟢 Включён' : '🔴 Выключен'}: ${code}`);
    return handleAdmin({ ...query, data: `admin_promo_${code}` });
  }

  // Delete promo
  if (data.startsWith('admin_delpromo_')) {
    const code = data.replace('admin_delpromo_', '');
    promos.delete(code);
    bot.sendMessage(chatId, `🗑 Промокод ${code} удалён`);
    return handleAdmin({ ...query, data: 'admin_promos' });
  }

  // New promo prompt
  if (data === 'admin_newpromo') {
    adminStates.set(userId, 'newpromo_code');
    return bot.sendMessage(chatId, `➕ Отправьте код промокода (например: БОНУС100):`);
  }

  // Broadcast prompt
  if (data === 'admin_broadcast') {
    adminStates.set(userId, 'broadcast');
    return bot.sendMessage(chatId, `📢 Отправьте текст рассылки:\n\nМожно использовать HTML разметку:\n<b>жирный</b> <i>курсив</i>`);
  }

  // Arena control
  if (data === 'admin_arena') {
    return bot.sendMessage(chatId, `⚔️ *Управление ареной:*`, {
      parse_mode: 'Markdown',
      reply_markup: { inline_keyboard: [
        [{ text: arena.active ? '🔴 Остановить' : '🟢 Запустить', callback_data: 'admin_togglearena' }],
        [{ text: `⏱ Длительность: ${arena.duration/1000}с`, callback_data: 'admin_arenatime' }],
        [{ text: '◀️ Назад', callback_data: 'admin_menu' }]
      ]}
    });
  }

  // Toggle arena
  if (data === 'admin_togglearena') {
    if (arena.active) {
      arena.active = false;
      endArena();
      bot.sendMessage(chatId, '🔴 Арена остановлена');
    } else {
      startArena();
      bot.sendMessage(chatId, '🟢 Арена запущена!');
    }
    return handleAdmin({ ...query, data: 'admin_arena' });
  }

  // Arena time
  if (data === 'admin_arenatime') {
    arena.duration = arena.duration === 60000 ? 120000 : arena.duration === 120000 ? 300000 : 60000;
    bot.sendMessage(chatId, `⏱ Длительность арены: ${arena.duration/1000}с`);
    return handleAdmin({ ...query, data: 'admin_arena' });
  }

  // Give bonus prompt
  if (data === 'admin_givebonus') {
    adminStates.set(userId, 'bonus_select');
    const list = Array.from(users.values()).slice(0, 10);
    const buttons = list.map(u => [{ text: `${u.firstName||u.id}`, callback_data: `admin_bonus_${u.id}` }]);
    buttons.push([{ text: '◀️ Назад', callback_data: 'admin_menu' }]);
    return bot.sendMessage(chatId, '🎁 Выберите пользователя:', {
      reply_markup: { inline_keyboard: buttons }
    });
  }
}

// ─── Admin Message Handler (text input for admin actions) ─────────────────
bot.on('message', (msg) => {
  if (!isAdmin(msg.from.id)) return;
  const state = adminStates.get(msg.from.id);
  if (!state || !msg.text || msg.text.startsWith('/')) return;

  // New promo code
  if (state === 'newpromo_code') {
    const code = msg.text.trim().toUpperCase();
    if (promos.has(code)) return bot.sendMessage(msg.chat.id, '❌ Уже существует');
    adminStates.set(msg.from.id, `newpromo_bonus_${code}`);
    return bot.sendMessage(msg.chat.id, `💰 Сколько монет бонуса для "${code}"?`);
  }

  if (state.startsWith('newpromo_bonus_')) {
    const code = state.replace('newpromo_bonus_', '');
    const bonus = parseInt(msg.text);
    if (isNaN(bonus) || bonus < 1) return bot.sendMessage(msg.chat.id, '❌ Введите число');
    adminStates.set(msg.from.id, `newpromo_limit_${code}_${bonus}`);
    return bot.sendMessage(msg.chat.id, `📊 Лимит активаций? (сколько раз можно использовать)`);
  }

  if (state.startsWith('newpromo_limit_')) {
    const parts = state.replace('newpromo_limit_', '').split('_');
    const code = parts[0];
    const bonus = parseInt(parts[1]);
    const limit = parseInt(msg.text);
    if (isNaN(limit) || limit < 1) return bot.sendMessage(msg.chat.id, '❌ Введите число');

    promos.set(code, { code, bonus, used: 0, limit, active: true });
    adminStates.delete(msg.from.id);
    return bot.sendMessage(msg.chat.id, `✅ Промокод создан!\n\n🎫 Код: ${code}\n💰 Бонус: ${bonus}\n📊 Лимит: ${limit}`);
  }

  // Broadcast
  if (state === 'broadcast') {
    const text = msg.text;
    let sent = 0;
    for (const [userId] of users) {
      bot.sendMessage(userId, text, { parse_mode: 'HTML' }).then(()=>sent++).catch(()=>{});
    }
    adminStates.delete(msg.from.id);
    return bot.sendMessage(msg.chat.id, `📢 Рассылка отправлена ${sent} пользователям`);
  }

  // Bonus amount
  if (state.startsWith('bonus_') && !state.startsWith('bonus_select')) {
    const uid = parseInt(state.replace('bonus_', ''));
    const amount = parseInt(msg.text);
    if (isNaN(amount) || amount < 1) return bot.sendMessage(msg.chat.id, '❌ Введите число');

    const user = getUser(uid);
    user.balance += amount;
    bot.sendMessage(msg.chat.id, `🎁 Выдано ${amount} монет пользователю ${user.firstName||uid}`);

    // Notify user
    bot.sendMessage(uid, `🎁 Вам начислен бонус: ${amount} монет от админа!`).catch(()=>{});
    adminStates.delete(msg.from.id);
  }
});

// ─── API Endpoints (for Mini App) ────────────────────────────────────────
app.get('/api/balance/:userId', (req, res) => {
  const user = getUser(parseInt(req.params.userId));
  res.json({ balance: user.balance });
});

app.post('/api/spin', (req, res) => {
  const { userId, betAmount } = req.body;
  if (!userId || !betAmount || betAmount < 10) return res.status(400).json({ error: 'Invalid' });
  const user = getUser(userId);
  if (user.banned) return res.status(403).json({ error: 'Banned' });
  if (user.balance < betAmount) return res.status(400).json({ error: 'No balance', balance: user.balance });

  user.balance -= betAmount;
  user.totalBet += betAmount;
  user.spins++;

  const result = spin();
  const win = calcWin(result, betAmount);
  if (win.isWin) { user.balance += win.winAmount; user.totalWon += win.winAmount; }

  res.json({ results: win.results, winAmount: win.winAmount, isWin: win.isWin, balance: user.balance });
});

app.post('/api/promo', (req, res) => {
  const { userId, code } = req.body;
  if (!userId || !code) return res.status(400).json({ error: 'Invalid' });
  const user = getUser(userId);
  const promo = promos.get(code.toUpperCase());
  if (!promo || !promo.active || promo.used >= promo.limit) return res.status(400).json({ error: 'Invalid promo' });
  promo.used++;
  user.balance += promo.bonus;
  res.json({ success: true, bonus: promo.bonus, balance: user.balance });
});

// Stars payment
app.post('/api/create-invoice', async (req, res) => {
  const { userId, amount, starsAmount } = req.body;
  try {
    const invoice = await bot.sendInvoice(userId, `💰 ${starsAmount} монет`, `Покупка ${starsAmount} монет`, JSON.stringify({ userId, amount, starsAmount }), 'XTR', [{ label: 'Монеты', amount: starsAmount }], { provider_token: '' });
    res.json({ success: true, invoiceId: invoice.message_id });
  } catch (e) { res.status(500).json({ error: 'Failed' }); }
});

bot.on('pre_checkout_query', async (q) => {
  try { await bot.answerPreCheckoutQuery(q.id, true); }
  catch (e) { await bot.answerPreCheckoutQuery(q.id, false, 'Failed'); }
});

bot.on('successful_payment', async (msg) => {
  const p = msg.successful_payment;
  try {
    const payload = JSON.parse(p.invoice_payload);
    const user = getUser(msg.from.id);
    user.balance += payload.starsAmount;
    bot.sendMessage(msg.from.id, `✅ Оплата! +${payload.starsAmount} монет | Баланс: ${user.balance}`, {
      reply_markup: { inline_keyboard: [[{ text: '🎰 Играть', web_app: { url: WEBAPP_URL } }]] }
    });
  } catch (e) {}
});

// ─── Serve Mini App (if dist exists) ────────────────────────────────────
app.get('*', (req, res) => {
  const indexPath = path.join(__dirname, '../dist/index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.json({ status: 'ok', message: 'Casino Bot API is running', webapp: WEBAPP_URL });
  }
});

// ─── Auto-start arena every 10 minutes ──────────────────────────────────
setInterval(() => {
  if (!arena.active) startArena();
}, 600000);

// ─── Start ───────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`🚀 Server: port ${PORT}`);
  console.log(`🌐 WebApp: ${WEBAPP_URL}`);
  console.log(`🎰 Casino Bot v2 ready!`);
  console.log(`🔧 Admin IDs: ${ADMIN_IDS.join(', ') || 'NOT SET'}`);
});
