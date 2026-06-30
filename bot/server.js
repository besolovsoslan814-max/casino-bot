/**
 * Telegram Casino Bot — v2
 * - Slots game
 * - PvP Arena (proportional win chance, 10% house edge)
 * - Promo codes
 * - Admin panel INSIDE the bot (Telegram ID check)
 * - Payments via Telegram Stars
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

// ─── Config ──────────────────────────────────────────────────────────────
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const PORT = process.env.PORT || 3000;
const WEBAPP_URL = process.env.WEBAPP_URL || `http://localhost:${PORT}`;
const ADMIN_IDS = (process.env.ADMIN_IDS || '').split(',').map(Number).filter(Boolean);

console.log('🚀 Starting Casino Bot v2...');
console.log('Token:', BOT_TOKEN ? 'SET' : 'MISSING');
console.log('Admin IDs:', ADMIN_IDS);

// ─── Express ─────────────────────────────────────────────────────────────
const app = express();
app.use(cors());
app.use(express.json());

const distPath = path.join(__dirname, '../dist');
if (fs.existsSync(distPath)) app.use(express.static(distPath));

// Health check
app.get('/', (req, res) => res.json({ status: 'ok', url: WEBAPP_URL }));
app.get('/health', (req, res) => res.json({ status: 'healthy' }));

// ─── Data Stores ─────────────────────────────────────────────────────────
const users = new Map();
const promos = new Map();
const arena = { active: false, players: new Map(), startTime: null, duration: 60000 };
const adminStates = new Map();

function getUser(id) {
  if (!users.has(id)) users.set(id, { id, firstName: '', username: '', balance: 0, totalBet: 0, totalWon: 0, spins: 0, banned: false, createdAt: new Date() });
  return users.get(id);
}
function isAdmin(id) { return ADMIN_IDS.includes(id); }

// ─── Slots Logic ─────────────────────────────────────────────────────────
const SYMBOLS = ['🍒','🍋','🍊','🍇','💎','7️⃣','⭐','🎰'];
const WEIGHTS = { '🍒':200,'🍋':200,'🍊':180,'🍇':150,'💎':120,'7️⃣':80,'⭐':50,'🎰':20 };
const PAYOUTS = { '🍒':2,'🍋':3,'🍊':4,'🍇':5,'💎':10,'7️⃣':15,'⭐':20,'🎰':50 };
const HOUSE_EDGE = 0.97;

function randSymbol() {
  const total = Object.values(WEIGHTS).reduce((a,b)=>a+b,0);
  let r = Math.random()*total;
  for (const [s,w] of Object.entries(WEIGHTS)) { r-=w; if(r<=0) return s; }
  return SYMBOLS[0];
}
function spin() { return [randSymbol(), randSymbol(), randSymbol()]; }
function calcWin(res, bet) {
  const three = res[0]===res[1]&&res[1]===res[2];
  const two = !three&&(res[0]===res[1]||res[1]===res[2]||res[0]===res[2]);
  let win = 0;
  if (three&&Math.random()<0.03) win = Math.floor(bet*(PAYOUTS[res[0]]||1)*(1-HOUSE_EDGE));
  else if (two&&Math.random()<0.08) win = Math.floor(bet*1.5*(1-HOUSE_EDGE));
  return { results:res, winAmount:win, isWin:win>0, allMatch:three, twoMatch:two };
}

// ─── PvP Arena ───────────────────────────────────────────────────────────
function startArena() {
  arena.active = true; arena.players = new Map(); arena.startTime = Date.now();
  const msg = `⚔️ *PvP Арена открыта!*\n💰 Ставьте — чем больше, тем выше шанс!\n🏦 Казино: 10%\n⏱ 60 сек`;
  for (const [userId] of users) {
    bot.sendMessage(userId, msg, { parse_mode:'Markdown', reply_markup:{inline_keyboard:[[{text:'⚔️ Войти',callback_data:'arena_join'}]]} }).catch(()=>{});
  }
  setTimeout(endArena, arena.duration);
}

function endArena() {
  if (!arena.active||arena.players.size===0) { arena.active=false; return; }
  const entries = Array.from(arena.players.entries());
  const totalPot = entries.reduce((s,[,b])=>s+b,0);
  const houseFee = Math.floor(totalPot*0.10);
  const prize = totalPot-houseFee;
  let r = Math.random()*totalPot, winnerId = entries[0][0];
  for (const [uid,bet] of entries) { r-=bet; if(r<=0){winnerId=uid;break;} }
  const w = getUser(winnerId); w.balance+=prize; w.totalWon+=prize;
  const msg = `🏆 *Арена завершена!*\n👥 ${entries.length} | 💰 ${totalPot} | 🏦 ${houseFee}\n🎉 Победитель: *${w.firstName||winnerId}*\n💎 +${prize} монет`;
  for (const [userId] of users) bot.sendMessage(userId, msg, {parse_mode:'Markdown'}).catch(()=>{});
  arena.active = false; arena.players = new Map();
}

// ─── Bot Init ────────────────────────────────────────────────────────────
let bot;

async function initBot() {
  if (!BOT_TOKEN) { console.log('⚠️ No token, API-only mode'); return; }

  const TelegramBot = require('node-telegram-bot-api');
  bot = new TelegramBot(BOT_TOKEN, { polling: false });

  // Webhook
  if (WEBAPP_URL && !WEBAPP_URL.includes('localhost')) {
    try { await bot.setWebHook(`${WEBAPP_URL}/webhook`); console.log('🔗 Webhook set'); }
    catch(e) { console.error('⚠️ Webhook:', e.message); }
  } else {
    try { bot.startPolling(); console.log('🔄 Polling started'); }
    catch(e) { console.error('⚠️ Polling:', e.message); }
  }

  // /start
  bot.onText(/\/start/, (msg) => {
    const user = getUser(msg.from.id);
    user.firstName = msg.from.first_name;
    const kb = [
      [{text:'🎰 Играть',web_app:{url:WEBAPP_URL}}],
      [{text:'⚔️ PvP Арена',callback_data:'arena_info'},{text:'🎫 Промокод',callback_data:'promo'}],
      [{text:'📊 Статистика',callback_data:'stats'},{text:'ℹ️ Помощь',callback_data:'help'}],
    ];
    if (isAdmin(msg.from.id)) kb.push([{text:'🔧 Админ-панель',callback_data:'admin_menu'}]);
    bot.sendMessage(msg.chat.id, `🎰 Добро пожаловать, ${user.firstName}!`, {reply_markup:{inline_keyboard:kb}});
  });

  // Callbacks
  bot.on('callback_query', async (q) => {
    const userId = q.from.id, chatId = q.message.chat.id, data = q.data;
    const user = getUser(userId); user.firstName = q.from.first_name;
    bot.answerCallbackQuery(q.id);

    if (data.startsWith('admin_')) { if(!isAdmin(userId)) return; return handleAdmin(q); }
    if (data==='stats') return bot.sendMessage(chatId, `📊 Баланс:${user.balance} | Игр:${user.spins} | Ставок:${user.totalBet} | Выигрышей:${user.totalWon}`);
    if (data==='help') return bot.sendMessage(chatId, '🎰 Слоты — «Играть» | ⚔️ Арена — PvP | 🎫 Промокоды — бонусы');
    if (data==='promo') return bot.sendMessage(chatId, '🎫 Отправь код промокода:');
    if (data==='arena_info') {
      if (arena.active) {
        const total=Array.from(arena.players.values()).reduce((a,b)=>a+b,0);
        const left=Math.max(0,60-Math.floor((Date.now()-arena.startTime)/1000));
        return bot.sendMessage(chatId, `⚔️ Арена активна!\n👥 ${arena.players.size} | 💰 ${total} | ⏱ ${left}с`, {reply_markup:{inline_keyboard:[[{text:'⚔️ Войти',callback_data:'arena_join'}]]}});
      }
      return bot.sendMessage(chatId, '⚔️ Арена неактивна');
    }
    if (data==='arena_join') {
      if (!arena.active) return bot.sendMessage(chatId, 'Арена не активна');
      if (user.balance<10) return bot.sendMessage(chatId, '❌ Минимум 10 монет');
      const bet = Math.min(100, user.balance);
      user.balance-=bet; arena.players.set(userId, bet);
      return bot.sendMessage(chatId, `✅ Ставка: ${bet} | Банк: ${Array.from(arena.players.values()).reduce((a,b)=>a+b,0)}`);
    }
  });

  // Promo handler
  bot.on('message', (msg) => {
    if (!msg.text||msg.text.startsWith('/')) return;
    if (msg.reply_to_message?.text?.includes('промокод')) {
      const code = msg.text.trim().toUpperCase(), user = getUser(msg.from.id), promo = promos.get(code);
      if (!promo) return bot.sendMessage(msg.chat.id, '❌ Не найден');
      if (!promo.active) return bot.sendMessage(msg.chat.id, '❌ Выкл');
      if (promo.used>=promo.limit) return bot.sendMessage(msg.chat.id, '❌ Лимит');
      promo.used++; user.balance+=promo.bonus;
      bot.sendMessage(msg.chat.id, `✅ +${promo.bonus} монет | Баланс: ${user.balance}`);
    }
    // Admin text input
    if (isAdmin(msg.from.id)) handleAdminText(msg);
  });

  // Auto arena every 10 min
  setInterval(() => { if(!arena.active) startArena(); }, 600000);
  console.log('✅ Bot ready');
}

// ─── Admin Panel ─────────────────────────────────────────────────────────
async function handleAdmin(q) {
  const userId = q.from.id, chatId = q.message.chat.id, data = q.data;

  if (data==='admin_menu') return bot.sendMessage(chatId, '🔧 *Админ-панель*', {parse_mode:'Markdown',reply_markup:{inline_keyboard:[
    [{text:'📊 Статистика',callback_data:'admin_stats'}],
    [{text:'👥 Пользователи',callback_data:'admin_users'}],
    [{text:'🎫 Промокоды',callback_data:'admin_promos'}],
    [{text:'📢 Рассылка',callback_data:'admin_broadcast'}],
    [{text:'⚔️ Арена',callback_data:'admin_arena'}],
  ]}});

  if (data==='admin_stats') {
    let ts=0,tb=0,tw=0,bn=0;
    users.forEach(u=>{ts+=u.spins;tb+=u.totalBet;tw+=u.totalWon;if(u.banned)bn++;});
    return bot.sendMessage(chatId, `📊 Users:${users.size} | Games:${ts} | Bets:${tb} | Won:${tw} | Profit:${tb-tw} | Banned:${bn}`, {reply_markup:{inline_keyboard:[[{text:'◀️',callback_data:'admin_menu'}]]}});
  }

  if (data==='admin_users') {
    const list = Array.from(users.values()).slice(0,8);
    const btns = list.map(u=>[{text:`${u.firstName||u.id} | 💰${u.balance}`,callback_data:`admin_user_${u.id}`}]);
    btns.push([{text:'◀️',callback_data:'admin_menu'}]);
    return bot.sendMessage(chatId, `👥 Пользователи (${users.size}):`, {reply_markup:{inline_keyboard:btns}});
  }

  if (data.startsWith('admin_user_')) {
    const uid=parseInt(data.replace('admin_user_','')), u=getUser(uid);
    return bot.sendMessage(chatId, `👤 ${u.firstName||uid}\n💰 ${u.balance} | 🔄 ${u.spins} | ${u.banned?'🔒ЗАБАНЕН':'✅Активен'}`, {reply_markup:{inline_keyboard:[
      [{text:'🎁 Бонус',callback_data:`admin_bonus_${uid}`}],
      [u.banned?{text:'🔓 Разбан',callback_data:`admin_unban_${uid}`}:{text:'🔒 Бан',callback_data:`admin_ban_${uid}`}],
      [{text:'◀️',callback_data:'admin_users'}]
    ]}});
  }

  if (data.startsWith('admin_ban_')) { getUser(parseInt(data.replace('admin_ban_',''))).banned=true; bot.sendMessage(chatId,'🔒 Забанен'); return handleAdmin({...q,data:'admin_users'}); }
  if (data.startsWith('admin_unban_')) { getUser(parseInt(data.replace('admin_unban_',''))).banned=false; bot.sendMessage(chatId,'🔓 Разбанен'); return handleAdmin({...q,data:'admin_users'}); }
  if (data.startsWith('admin_bonus_')) { adminStates.set(userId,`bonus_${data.replace('admin_bonus_','')}`); return bot.sendMessage(chatId,'🎁 Сколько монет?'); }

  if (data==='admin_promos') {
    const list=Array.from(promos.values());
    const btns=list.map(p=>[{text:`${p.code} | 💰${p.bonus} | ${p.used}/${p.limit}`,callback_data:`admin_promo_${p.code}`}]);
    btns.push([{text:'➕ Новый',callback_data:'admin_newpromo'}]);
    btns.push([{text:'◀️',callback_data:'admin_menu'}]);
    return bot.sendMessage(chatId, `🎫 Промокоды (${list.length}):`, {reply_markup:{inline_keyboard:btns}});
  }

  if (data==='admin_newpromo') { adminStates.set(userId,'newpromo_code'); return bot.sendMessage(chatId,'➕ Код промокода:'); }

  if (data==='admin_broadcast') { adminStates.set(userId,'broadcast'); return bot.sendMessage(chatId,'📢 Текст рассылки:'); }

  if (data==='admin_arena') {
    return bot.sendMessage(chatId, `⚔️ Арена: ${arena.active?'🟢Активна':'🔴Выкл'} | ⏱ ${arena.duration/1000}с`, {reply_markup:{inline_keyboard:[
      [{text:arena.active?'🔴 Стоп':'🟢 Старт',callback_data:'admin_togglearena'}],
      [{text:'◀️',callback_data:'admin_menu'}]
    ]}});
  }

  if (data==='admin_togglearena') { arena.active?endArena():startArena(); bot.sendMessage(chatId, arena.active?'🟢 Запущена':'🔴 Остановлена'); return handleAdmin({...q,data:'admin_arena'}); }
}

function handleAdminText(msg) {
  const userId = msg.from.id, state = adminStates.get(userId);
  if (!state) return;

  if (state==='newpromo_code') { adminStates.set(userId,`newpromo_bonus_${msg.text.trim().toUpperCase()}`); return bot.sendMessage(msg.chat.id,'💰 Бонус (монеты):'); }
  if (state.startsWith('newpromo_bonus_')) { const code=state.replace('newpromo_bonus_',''); adminStates.set(userId,`newpromo_limit_${code}_${msg.text}`); return bot.sendMessage(msg.chat.id,'📊 Лимит:'); }
  if (state.startsWith('newpromo_limit_')) {
    const p=state.replace('newpromo_limit_','').split('_'), code=p[0], bonus=parseInt(p[1]), limit=parseInt(msg.text);
    promos.set(code,{code,bonus,used:0,limit,active:true});
    adminStates.delete(userId);
    return bot.sendMessage(msg.chat.id, `✅ Создан: ${code} | +${bonus} | Лимит ${limit}`);
  }
  if (state==='broadcast') {
    let sent=0;
    for (const [uid] of users) bot.sendMessage(uid, msg.text).then(()=>sent++).catch(()=>{});
    adminStates.delete(userId);
    return bot.sendMessage(msg.chat.id, `📢 Отправлено: ${sent}`);
  }
  if (state.startsWith('bonus_')) {
    const uid=parseInt(state.replace('bonus_','')), amt=parseInt(msg.text);
    const u=getUser(uid); u.balance+=amt;
    bot.sendMessage(uid, `🎁 Бонус: +${amt} монет`).catch(()=>{});
    adminStates.delete(userId);
    return bot.sendMessage(msg.chat.id, `🎁 Выдано ${amt} → ${u.firstName||uid}`);
  }
}

// Webhook endpoint
app.post('/webhook', (req, res) => {
  if (!bot) return res.sendStatus(503);
  bot.processUpdate(req.body);
  res.sendStatus(200);
});

// ─── API (for Mini App) ──────────────────────────────────────────────────
app.get('/api/balance/:userId', (req, res) => res.json({ balance: getUser(parseInt(req.params.userId)).balance }));

app.post('/api/spin', (req, res) => {
  const {userId, betAmount} = req.body;
  if (!userId||!betAmount||betAmount<10) return res.status(400).json({error:'Invalid'});
  const user = getUser(userId);
  if (user.banned) return res.status(403).json({error:'Banned'});
  if (user.balance<betAmount) return res.status(400).json({error:'No balance',balance:user.balance});
  user.balance-=betAmount; user.totalBet+=betAmount; user.spins++;
  const r=spin(), w=calcWin(r,betAmount);
  if(w.isWin){user.balance+=w.winAmount;user.totalWon+=w.winAmount;}
  res.json({results:w.results,winAmount:w.winAmount,isWin:w.isWin,balance:user.balance});
});

app.post('/api/promo', (req, res) => {
  const {userId,code}=req.body;
  const user=getUser(userId), promo=promos.get(code?.toUpperCase());
  if(!promo||!promo.active||promo.used>=promo.limit) return res.status(400).json({error:'Invalid'});
  promo.used++; user.balance+=promo.bonus;
  res.json({success:true,bonus:promo.bonus,balance:user.balance});
});

// Stars
app.post('/api/create-invoice', async (req, res) => {
  const {userId,starsAmount}=req.body;
  try {
    const inv=await bot.sendInvoice(userId,`💰 ${starsAmount} монет`,`Покупка`,JSON.stringify({userId,starsAmount}),'XTR',[{label:'Монеты',amount:starsAmount}],{provider_token:''});
    res.json({success:true,invoiceId:inv.message_id});
  } catch(e) { res.status(500).json({error:'Failed'}); }
});

// Serve Mini App
app.get('*', (req, res) => {
  const idx = path.join(__dirname, '../dist/index.html');
  fs.existsSync(idx) ? res.sendFile(idx) : res.json({status:'ok',webapp:WEBAPP_URL});
});

// ─── Start ───────────────────────────────────────────────────────────────
app.listen(PORT, async () => {
  console.log(`🚀 Server: port ${PORT}`);
  await initBot();
});
