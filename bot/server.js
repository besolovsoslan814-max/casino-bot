/**
 * Telegram Casino Bot — v2
 * Simplified for Render deployment
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');

// ─── Config ──────────────────────────────────────────────────────────────
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const PORT = process.env.PORT || 3000;
const WEBAPP_URL = process.env.WEBAPP_URL || `http://localhost:${PORT}`;
const ADMIN_IDS = (process.env.ADMIN_IDS || '').split(',').map(Number).filter(Boolean);

console.log('🚀 Starting bot...');
console.log('Token:', BOT_TOKEN ? 'SET' : 'MISSING');
console.log('Port:', PORT);
console.log('Admin IDs:', ADMIN_IDS);

// ─── Express ─────────────────────────────────────────────────────────────
const app = express();
app.use(cors());
app.use(express.json());

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'Casino Bot is running', url: WEBAPP_URL });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

// ─── Bot (lazy init) ────────────────────────────────────────────────────
let bot = null;

async function initBot() {
  if (!BOT_TOKEN) {
    console.log('⚠️ No bot token, skipping bot init');
    return;
  }

  try {
    const TelegramBot = require('node-telegram-bot-api');
    bot = new TelegramBot(BOT_TOKEN, { polling: false });
    console.log('🤖 Bot created');

    // Set webhook
    if (WEBAPP_URL && !WEBAPP_URL.includes('localhost')) {
      try {
        await bot.setWebHook(`${WEBAPP_URL}/webhook`);
        console.log('🔗 Webhook set');
      } catch (err) {
        console.error('⚠️ Webhook error:', err.message);
      }
    }

    // Message handlers
    bot.onText(/\/start/, (msg) => {
      const name = msg.from.first_name;
      bot.sendMessage(msg.chat.id, `🎰 Добро пожаловать, ${name}!`, {
        reply_markup: {
          inline_keyboard: [
            [{ text: '🎰 Играть', web_app: { url: WEBAPP_URL } }],
            [{ text: '⚔️ PvP Арена', callback_data: 'arena' }],
            [{ text: '📊 Статистика', callback_data: 'stats' }],
          ]
        }
      });
    });

    console.log('✅ Bot handlers registered');
  } catch (err) {
    console.error('❌ Bot init error:', err.message);
  }
}

// Webhook endpoint
app.post('/webhook', (req, res) => {
  if (!bot) return res.sendStatus(503);
  bot.processUpdate(req.body);
  res.sendStatus(200);
});

// ─── Start ───────────────────────────────────────────────────────────────
app.listen(PORT, async () => {
  console.log(`🚀 Server running on port ${PORT}`);
  await initBot();
  console.log('🎰 Casino Bot ready!');
});
