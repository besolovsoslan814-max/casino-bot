# 🎰 Telegram Casino Bot

Полноценный Telegram бот с казино мини-игрой и оплатой Telegram Stars.

## 🚀 Быстрый старт

### 1. Получи токены

**Бот токен:**
1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Следуй инструкциям, получи токен

**Payment Provider Token:**
~~Telegram Stars НЕ требует отдельного токена!~~
Stars встроены в Telegram, провайдер не нужен.

### 2. Настрой .env

```bash
cd bot
cp .env.example .env
# Заполни токены в .env файле
```

### 3. Запусти

```bash
# Установи зависимости
npm install

# Запусти бота
npm start
```

### 4. Настрой WebApp в Telegram

1. Открой [@BotFather](https://t.me/BotFather)
2. `/mybots → Bot Settings → Menu Button`
3. Введи URL твоего сервера (например `https://your-domain.com`)
4. Назови кнопку «🎰 Играть»

### 5. Настрой Mini App

1. `/mybots → Bot Settings → Apps`
2. Добавь URL твоего сервера
3. Включи «Данные пользователя»

## 📁 Структура проекта

```
bot/
├── server.js          # Бэкенд: Express + Telegram Bot
├── package.json       # Зависимости
├── .env.example       # Шаблон переменных окружения
└── README.md          # Эта документация

src/
├── App.tsx            # Фронтенд: Telegram Mini App
├── index.css          # Стили
└── main.tsx           # Точка входа
```

## 🎮 Игровая механика

### Шансы на выигрыш (МАКСИМАЛЬНО НИЗКИЕ)

| Символ | Вероятность | Множитель | RTP |
|--------|-------------|-----------|-----|
| 🍒🍒🍒 | 20% (символ) × 3% (шанс) = **0.6%** | ×2 | 1.2% |
| 🍋🍋🍋 | 20% × 3% = **0.6%** | ×3 | 1.8% |
| 🍊🍊🍊 | 18% × 3% = **0.54%** | ×4 | 2.16% |
| 🍇🍇🍇 | 15% × 3% = **0.45%** | ×5 | 2.25% |
| 💎💎💎 | 12% × 3% = **0.36%** | ×10 | 3.6% |
| 7️⃣7️⃣7️⃣ | 8% × 3% = **0.24%** | ×15 | 3.6% |
| ⭐⭐⭐ | 5% × 3% = **0.15%** | ×20 | 3.0% |
| 🎰🎰🎰 | 2% × 3% = **0.06%** | ×50 | 3.0% |
| 2 совпадения | 8% | ×1.5 | ~3% |

**Общий RTP: ~23%** → **House Edge: ~77%**

### Что это значит:
- На каждые 100 Stars поставленных → казино зарабатывает ~77 Stars
- Игроки возвращают только ~23% от своих ставок

## 💰 Монетизация

### Telegram Stars

| Stars | Монеты | Бонус |
|-------|--------|-------|
| 10 | 500 | — |
| 50 | 3,000 | +500 |
| 100 | 7,000 | +2,000 |
| 500 | 40,000 | +15,000 |

### Профит казино:
- **House Edge: 77%** (вместо обычных 2-10%)
- На 1000 Stars ставок → ~770 Stars чистой прибыли

## 🔧 API Endpoints

```
GET  /api/balance/:userId    - Получить баланс
POST /api/spin               - Крутить барабаны
POST /api/create-invoice     - Создать инвойс Stars
```

## 🚀 Деплой на продакшен

### Вариант 1: Railway
```bash
# Установи Railway CLI
npm i -g @railway/cli

# Войди и создай проект
railway login
railway init

# Добавь переменные
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set PAYMENT_PROVIDER_TOKEN=your_payment_token

# Деплой
railway up
```

### Вариант 2: Render
1. Создай Web Service на [render.com](https://render.com)
2. Подключи GitHub репозиторий
3. Build Command: `npm install && cd .. && npm run build`
4. Start Command: `cd bot && node server.js`
5. Добавь Environment Variables

### Вариант 3: VPS (DigitalOcean, etc.)
```bash
# На сервере
git clone your-repo
cd project
npm install
cd bot && npm install

# Запусти с PM2
npm i -g pm2
pm2 start bot/server.js --name casino-bot
pm2 save
pm2 startup
```

## ⚠️ Важно

1. **В продакшене используй базу данных** (вместо in-memory) для хранения балансов
2. **Добавь rate limiting** для защиты от спама
3. **Проверь законы** о азартных играх в твоей юрисдикции
4. **Настрой HTTPS** для работы Telegram Mini App

## 📝 Команды бота

- `/start` - Приветствие и главное меню
- `/help` - Помощь и таблица выплат
- Статистика через callback кнопки
