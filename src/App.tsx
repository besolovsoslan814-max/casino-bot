import { useState, useCallback, useRef, useEffect } from 'react'

// ─── Telegram WebApp Integration ─────────────────────────────────────────────
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void
        expand: () => void
        close: () => void
        initDataUnsafe?: {
          user?: {
            id: number
            first_name: string
            last_name?: string
            username?: string
          }
        }
        openInvoice: (url: string, callback: (status: string) => void) => void
        backButton: {
          show: () => void
          hide: () => void
          onClick: (callback: () => void) => void
        }
        MainButton: {
          setText: (text: string) => void
          show: () => void
          hide: () => void
          onClick: (callback: () => void) => void
        }
        themeParams: {
          bg_color?: string
          text_color?: string
          hint_color?: string
          button_color?: string
          button_text_color?: string
        }
      }
    }
  }
}

const tg = window.Telegram?.WebApp

// ─── Constants ────────────────────────────────────────────────────────────────
const SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣', '⭐', '🎰']
const REEL_COUNT = 3
const SPIN_DURATION = 2000
const BASE_SPEED = 50
const API_BASE = '' // Same origin in production

// Payouts multipliers by symbol
const PAYOUTS: Record<string, number> = {
  '🍒': 2,
  '🍋': 3,
  '🍊': 4,
  '🍇': 5,
  '💎': 10,
  '7️⃣': 15,
  '⭐': 20,
  '🎰': 50,
}

// Star packages for purchase
const STAR_PACKAGES = [
  { stars: 10, coins: 500, bonus: 0, popular: false },
  { stars: 50, coins: 3000, bonus: 500, popular: true },
  { stars: 100, coins: 7000, bonus: 2000, popular: false },
  { stars: 500, coins: 40000, bonus: 15000, popular: false },
]

// ─── Types ────────────────────────────────────────────────────────────────────
interface ReelState {
  currentSymbol: string
  spinning: boolean
  finalSymbol: string | null
}

interface SpinResult {
  results: string[]
  winAmount: number
  isWin: boolean
  balance: number
  allMatch: boolean
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatCoins(n: number): string {
  return n.toLocaleString('ru-RU')
}

function getUserId(): number {
  return tg?.initDataUnsafe?.user?.id || 0
}

// ─── Reel Component ───────────────────────────────────────────────────────────
function Reel({ state, index }: { state: ReelState; index: number }) {
  const [displaySymbol, setDisplaySymbol] = useState(state.currentSymbol)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const symbolIndexRef = useRef(0)

  useEffect(() => {
    if (state.spinning) {
      symbolIndexRef.current = SYMBOLS.indexOf(state.currentSymbol)
      intervalRef.current = setInterval(() => {
        symbolIndexRef.current = (symbolIndexRef.current + 1) % SYMBOLS.length
        setDisplaySymbol(SYMBOLS[symbolIndexRef.current])
      }, BASE_SPEED)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (state.finalSymbol) setDisplaySymbol(state.finalSymbol)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [state.spinning, state.finalSymbol, state.currentSymbol])

  return (
    <div
      className="reel-window"
      style={{ animationDelay: `${index * 0.1}s` }}
    >
      <div className={`reel-symbol ${state.spinning ? 'blur-sm' : ''}`}>
        {displaySymbol}
      </div>
    </div>
  )
}

// ─── Stars Purchase Modal ────────────────────────────────────────────────────
function StarsModal({ onClose, onPurchase }: { onClose: () => void; onPurchase: (stars: number) => void }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>⭐ Купить монеты</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <p className="modal-subtitle">Оплати Telegram Stars</p>
          <div className="star-packages">
            {STAR_PACKAGES.map((pkg) => (
              <div
                key={pkg.stars}
                className={`star-package ${pkg.popular ? 'popular' : ''}`}
                onClick={() => onPurchase(pkg.stars)}
              >
                {pkg.popular && <div className="popular-badge">ХИТ</div>}
                <div className="package-coins">
                  💰 {formatCoins(pkg.coins)}
                  {pkg.bonus > 0 && (
                    <span className="package-bonus">+{formatCoins(pkg.bonus)}</span>
                  )}
                </div>
                <div className="package-price">
                  <span className="star-icon">⭐</span>
                  <span>{pkg.stars}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="modal-footer">
            <p>💳 Оплата через Telegram Stars</p>
            <p>🔒 Безопасная транзакция</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [balance, setBalance] = useState(0)
  const [bet, setBet] = useState(100)
  const [spinning, setSpinning] = useState(false)
  const [reels, setReels] = useState<ReelState[]>(
    Array.from({ length: REEL_COUNT }, () => ({
      currentSymbol: '🍒',
      spinning: false,
      finalSymbol: null,
    }))
  )
  const [lastWin, setLastWin] = useState(0)
  const [totalWon, setTotalWon] = useState(0)
  const [totalSpins, setTotalSpins] = useState(0)
  const [message, setMessage] = useState<string | null>(null)
  const [jackpot, setJackpot] = useState(50000)
  const [showStarsModal, setShowStarsModal] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<
    { bet: number; result: string[]; win: number; time: string }[]
  >([])
  const [loading, setLoading] = useState(true)

  // Initialize Telegram WebApp
  useEffect(() => {
    if (tg) {
      tg.ready()
      tg.expand()
      tg.MainButton.hide()
    }
    loadBalance()
  }, [])

  const loadBalance = async () => {
    try {
      const userId = getUserId()
      const response = await fetch(`${API_BASE}/api/balance/${userId}`)
      const data = await response.json()
      setBalance(data.balance)
      setLoading(false)
    } catch (error) {
      console.error('Failed to load balance:', error)
      setLoading(false)
    }
  }

  const spin = useCallback(async () => {
    if (spinning || balance < bet) {
      if (balance < bet) {
        setMessage('💸 Недостаточно монет! Купи Stars.')
        setShowStarsModal(true)
      }
      return
    }

    setSpinning(true)
    setLastWin(0)
    setMessage(null)

    // Start spinning animation
    setReels((prev) =>
      prev.map((r) => ({
        ...r,
        spinning: true,
        finalSymbol: null,
        currentSymbol: '🍒',
      }))
    )

    try {
      const response = await fetch(`${API_BASE}/api/spin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: getUserId(), betAmount: bet }),
      })

      const data: SpinResult = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Spin failed')
      }

      // Animate reels stopping one by one
      data.results.forEach((symbol, i) => {
        setTimeout(() => {
          setReels((prev) =>
            prev.map((r, ri) =>
              ri === i ? { ...r, spinning: false, finalSymbol: symbol, currentSymbol: symbol } : r
            )
          )
        }, SPIN_DURATION + i * 500)
      })

      // Show result after all reels stop
      setTimeout(() => {
        setBalance(data.balance)
        setLastWin(data.winAmount)
        setTotalSpins((p) => p + 1)

        if (data.isWin) {
          setTotalWon((p) => p + data.winAmount)
          if (data.allMatch) {
            setMessage(`🎉 ${data.results[0]}${data.results[0]}${data.results[0]} — Выигрыш!`)
          } else {
            setMessage('✨ Два совпали — выигрыш!')
          }
        } else {
          setMessage('😔 Не повезло...')
          setJackpot((p) => p + Math.floor(bet * 0.1))
        }

        setHistory((p) => [
          { bet, result: data.results, win: data.winAmount, time: new Date().toLocaleTimeString('ru-RU') },
          ...p.slice(0, 19),
        ])

        setSpinning(false)
      }, SPIN_DURATION + data.results.length * 500 + 200)
    } catch (error) {
      console.error('Spin error:', error)
      setMessage('❌ Ошибка при вращении')
      setSpinning(false)
    }
  }, [spinning, balance, bet])

  const handlePurchase = async (stars: number) => {
    try {
      const response = await fetch(`${API_BASE}/api/create-invoice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: getUserId(), amount: stars, starsAmount: stars }),
      })

      const data = await response.json()

      if (data.success && tg?.openInvoice) {
        // Open Telegram payment
        tg.openInvoice(data.invoiceUrl, (status) => {
          if (status === 'paid') {
            setShowStarsModal(false)
            loadBalance()
            setMessage('✅ Оплата прошла! Монеты зачислены.')
          }
        })
      }
    } catch (error) {
      console.error('Purchase error:', error)
      setMessage('❌ Ошибка при покупке')
    }
  }

  const changeBet = (delta: number) => {
    setBet((prev) => Math.max(10, Math.min(balance, prev + delta)))
  }

  if (loading) {
    return (
      <div className="app-container">
        <div className="loading-screen">
          <div className="loading-spinner">🎰</div>
          <p>Загрузка...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="app-logo">🎰</div>
          <div>
            <h1 className="app-title">Казино</h1>
            <p className="app-subtitle">Telegram Stars</p>
          </div>
        </div>
        <div className="balance-chip" onClick={() => setShowStarsModal(true)}>
          <span className="balance-icon">💰</span>
          <span className="balance-value">{formatCoins(balance)}</span>
          <span className="balance-add">+</span>
        </div>
      </header>

      {/* Jackpot Banner */}
      <div className="jackpot-banner">
        <div className="jackpot-label">🎰 ДЖЕКПОТ</div>
        <div className="jackpot-value">{formatCoins(jackpot)}</div>
      </div>

      {/* Slot Machine */}
      <div className="slot-machine">
        <div className="machine-frame">
          <div className="reels-container">
            {reels.map((reel, i) => (
              <Reel key={i} state={reel} index={i} />
            ))}
          </div>
          <div className="reel-lines">
            <div className="payline payline-top" />
            <div className="payline payline-mid" />
            <div className="payline payline-bottom" />
          </div>
        </div>
      </div>

      {/* Win Display */}
      <div className="win-display">
        {lastWin > 0 ? (
          <div className="win-amount pulse">+{formatCoins(lastWin)} 🪙</div>
        ) : (
          <div className="win-placeholder">Сделай ставку!</div>
        )}
      </div>

      {/* Message */}
      {message && (
        <div className={`game-message ${lastWin > 0 ? 'win' : 'lose'}`}>
          {message}
        </div>
      )}

      {/* Bet Controls */}
      <div className="bet-section">
        <div className="bet-label">СТАВКА</div>
        <div className="bet-controls">
          <button className="bet-btn minus" onClick={() => changeBet(-50)} disabled={spinning || balance < 50}>
            −
          </button>
          <div className="bet-amount">{formatCoins(bet)}</div>
          <button className="bet-btn plus" onClick={() => changeBet(50)} disabled={spinning}>
            +
          </button>
        </div>
        <div className="quick-bets">
          {[50, 100, 500, 1000].map((b) => (
            <button
              key={b}
              className={`quick-bet ${bet === b ? 'active' : ''}`}
              onClick={() => setBet(Math.min(b, balance))}
              disabled={spinning || balance < b}
            >
              {formatCoins(b)}
            </button>
          ))}
        </div>
      </div>

      {/* Spin Button */}
      <button
        className={`spin-btn ${spinning ? 'spinning' : ''}`}
        onClick={spin}
        disabled={spinning || balance < bet}
      >
        {spinning ? (
          <span className="spin-text">🎰 Крутится...</span>
        ) : balance < bet ? (
          <span className="spin-text" onClick={() => setShowStarsModal(true)}>
            ⭐ Купить монеты
          </span>
        ) : (
          <span className="spin-text">🎰 КРУТИТЬ</span>
        )}
      </button>

      {/* Buy Stars Button */}
      <button
        className="buy-stars-btn"
        onClick={() => setShowStarsModal(true)}
      >
        ⭐ Купить Stars
      </button>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-icon">🔄</div>
          <div className="stat-value">{totalSpins}</div>
          <div className="stat-label">Крутилок</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🏆</div>
          <div className="stat-value">{formatCoins(totalWon)}</div>
          <div className="stat-label">Выиграно</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📊</div>
          <div className="stat-value">{totalSpins > 0 ? Math.round((totalWon / (totalSpins * bet)) * 100) : 0}%</div>
          <div className="stat-label">RTP</div>
        </div>
      </div>

      {/* Paytable */}
      <div className="paytable">
        <h3 className="paytable-title">📊 Таблица выплат</h3>
        <div className="paytable-grid">
          {Object.entries(PAYOUTS)
            .sort((a, b) => b[1] - a[1])
            .map(([symbol, mult]) => (
              <div key={symbol} className="paytable-row">
                <span className="paytable-symbols">
                  {symbol}{symbol}{symbol}
                </span>
                <span className="paytable-mult">×{mult}</span>
              </div>
            ))}
          <div className="paytable-row special">
            <span className="paytable-symbols">任意2个</span>
            <span className="paytable-mult">×1.5</span>
          </div>
        </div>
      </div>

      {/* History */}
      <div className="history-section">
        <button className="history-toggle" onClick={() => setShowHistory(!showHistory)}>
          📜 История {showHistory ? '▲' : '▼'}
        </button>
        {showHistory && (
          <div className="history-list">
            {history.length === 0 && (
              <div className="history-empty">Пока нет игр</div>
            )}
            {history.map((h, i) => (
              <div key={i} className={`history-item ${h.win > 0 ? 'win' : 'lose'}`}>
                <span className="history-time">{h.time}</span>
                <span className="history-symbols">{h.result.join(' ')}</span>
                <span className="history-bet">-{formatCoins(h.bet)}</span>
                <span className="history-result">
                  {h.win > 0 ? `+${formatCoins(h.win)}` : '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="app-footer">
        <p>🤖 Telegram Mini App • Казино</p>
        <p className="footer-disclaimer">Играйте ответственно! 18+</p>
      </footer>

      {/* Stars Modal */}
      {showStarsModal && (
        <StarsModal
          onClose={() => setShowStarsModal(false)}
          onPurchase={handlePurchase}
        />
      )}
    </div>
  )
}
