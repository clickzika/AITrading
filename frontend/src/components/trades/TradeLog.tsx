import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'

interface Trade {
  id: string
  symbol: string
  direction: string
  lot_size: number
  open_price: number
  close_price: number | null
  stop_loss: number | null
  take_profit: number | null
  profit: number | null
  status: string
  strategy: string | null
  opened_at: string
  closed_at: string | null
}

export function TradeLog() {
  const [symbol, setSymbol] = useState('')
  const [page, setPage] = useState(0)
  const limit = 20

  const { data = [], isLoading } = useQuery<Trade[]>({
    queryKey: ['trades', symbol, page],
    queryFn: () =>
      api
        .get('/api/trades', { params: { symbol: symbol || undefined, limit, offset: page * limit } })
        .then((r) => r.data),
  })

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.title}>Trade History</span>
        <input
          style={styles.input}
          placeholder="Filter by symbol…"
          value={symbol}
          onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setPage(0) }}
        />
      </div>
      {isLoading ? (
        <div style={styles.empty}>Loading…</div>
      ) : data.length === 0 ? (
        <div style={styles.empty}>No trades found</div>
      ) : (
        <>
          <table style={styles.table}>
            <thead>
              <tr>
                {['Symbol', 'Dir', 'Lots', 'Open', 'Close', 'P&L', 'Strategy', 'Status', 'Opened'].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((t) => (
                <tr key={t.id} style={{ borderBottom: '1px solid #1e2330' }}>
                  <td style={styles.td}>{t.symbol}</td>
                  <td style={{ ...styles.td, color: t.direction === 'buy' ? '#26a69a' : '#ef5350' }}>
                    {t.direction.toUpperCase()}
                  </td>
                  <td style={styles.td}>{t.lot_size}</td>
                  <td style={styles.td}>{t.open_price.toFixed(2)}</td>
                  <td style={styles.td}>{t.close_price?.toFixed(2) ?? '—'}</td>
                  <td style={{ ...styles.td, color: (t.profit ?? 0) >= 0 ? '#26a69a' : '#ef5350' }}>
                    {t.profit != null ? `${t.profit >= 0 ? '+' : ''}${t.profit.toFixed(2)}` : '—'}
                  </td>
                  <td style={styles.td}>{t.strategy ?? '—'}</td>
                  <td style={{ ...styles.td, color: t.status === 'open' ? '#f59e0b' : '#8892a4' }}>
                    {t.status}
                  </td>
                  <td style={styles.td}>{new Date(t.opened_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={styles.pagination}>
            <button style={styles.btn} onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
              ← Prev
            </button>
            <span style={{ color: '#8892a4', fontSize: 12 }}>Page {page + 1}</span>
            <button style={styles.btn} onClick={() => setPage((p) => p + 1)} disabled={data.length < limit}>
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}

const styles = {
  panel: { background: '#141820', border: '1px solid #1e2330', borderRadius: 8, overflow: 'hidden' } as React.CSSProperties,
  header: { padding: '12px 16px', borderBottom: '1px solid #1e2330', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 } as React.CSSProperties,
  title: { fontWeight: 600, color: '#e2e8f0', fontSize: 14 } as React.CSSProperties,
  input: { background: '#0f1117', border: '1px solid #1e2330', borderRadius: 4, color: '#e2e8f0', padding: '4px 10px', fontSize: 13 } as React.CSSProperties,
  empty: { padding: 24, textAlign: 'center' as const, color: '#8892a4', fontSize: 13 },
  table: { width: '100%', borderCollapse: 'collapse' as const },
  th: { padding: '8px 12px', textAlign: 'left' as const, color: '#8892a4', fontSize: 12, borderBottom: '1px solid #1e2330' },
  td: { padding: '8px 12px', color: '#e2e8f0', fontSize: 13 } as React.CSSProperties,
  pagination: { padding: '8px 16px', display: 'flex', gap: 12, alignItems: 'center', borderTop: '1px solid #1e2330' } as React.CSSProperties,
  btn: { background: '#1e2330', border: '1px solid #2d3650', color: '#e2e8f0', padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12 } as React.CSSProperties,
}
