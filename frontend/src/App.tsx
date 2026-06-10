import { useState } from 'react'
import { isAuthenticated, login, logout } from '@/services/auth'
import { PriceChart } from '@/components/charts/PriceChart'
import { PositionsPanel } from '@/components/dashboard/PositionsPanel'
import { TradeLog } from '@/components/trades/TradeLog'
import { CopilotChat } from '@/components/ai/CopilotChat'
import { useTradingStore } from '@/stores/tradingStore'

function LoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(password)
      window.location.reload()
    } catch {
      setError('Invalid password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0f1117' }}>
      <div style={{ background: '#141820', border: '1px solid #1e2330', borderRadius: 12, padding: '40px 48px', width: 320 }}>
        <h1 style={{ color: '#6c63ff', marginBottom: 8, fontSize: 24, textAlign: 'center' }}>AITrading</h1>
        <p style={{ color: '#8892a4', fontSize: 13, marginBottom: 24, textAlign: 'center' }}>Enter your trader password</p>
        <form onSubmit={handleLogin}>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            style={{ width: '100%', background: '#0f1117', border: '1px solid #1e2330', borderRadius: 6, color: '#e2e8f0', padding: '10px 14px', fontSize: 14, boxSizing: 'border-box', marginBottom: 12 }}
          />
          {error && <p style={{ color: '#ef5350', fontSize: 12, marginBottom: 8 }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ width: '100%', background: '#6c63ff', border: 'none', color: '#fff', padding: '10px', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
            {loading ? 'Logging in…' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}

type TabId = 'dashboard' | 'trades' | 'ai'

export default function App() {
  const [tab, setTab] = useState<TabId>('dashboard')
  const { symbol, timeframe, setSymbol, setTimeframe } = useTradingStore()

  if (!isAuthenticated()) return <LoginPage />

  return (
    <div style={{ background: '#0f1117', minHeight: '100vh', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif' }}>
      {/* Top Nav */}
      <nav style={{ background: '#141820', borderBottom: '1px solid #1e2330', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 24, height: 52 }}>
        <span style={{ fontWeight: 700, color: '#6c63ff', fontSize: 16, marginRight: 16 }}>AITrading</span>
        {(['dashboard', 'trades', 'ai'] as TabId[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{ background: 'none', border: 'none', color: tab === t ? '#e2e8f0' : '#8892a4', fontWeight: tab === t ? 600 : 400, fontSize: 14, cursor: 'pointer', padding: '0 4px', borderBottom: tab === t ? '2px solid #6c63ff' : '2px solid transparent', height: 52 }}
          >
            {t === 'ai' ? 'AI Co-Pilot' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            style={{ background: '#0f1117', border: '1px solid #1e2330', color: '#e2e8f0', padding: '4px 8px', borderRadius: 4, fontSize: 13 }}
          >
            {['XAUUSD', 'EURUSD', 'BTCUSD', 'GBPUSD'].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value as import('@/stores/tradingStore').Timeframe)}
            style={{ background: '#0f1117', border: '1px solid #1e2330', color: '#e2e8f0', padding: '4px 8px', borderRadius: 4, fontSize: 13 }}
          >
            {['M1', 'M5', 'M15', 'H1', 'H4', 'D1'].map((tf) => (
              <option key={tf}>{tf}</option>
            ))}
          </select>
          <button onClick={logout} style={{ background: 'none', border: '1px solid #1e2330', color: '#8892a4', padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
            Logout
          </button>
        </div>
      </nav>

      {/* Tab content */}
      <main style={{ padding: 24 }}>
        {tab === 'dashboard' && (
          <div style={{ display: 'grid', gridTemplateRows: 'auto auto', gap: 16 }}>
            <PriceChart data={[]} symbol={symbol} timeframe={timeframe} height={420} />
            <PositionsPanel />
          </div>
        )}
        {tab === 'trades' && <TradeLog />}
        {tab === 'ai' && (
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            <CopilotChat />
          </div>
        )}
      </main>
    </div>
  )
}
