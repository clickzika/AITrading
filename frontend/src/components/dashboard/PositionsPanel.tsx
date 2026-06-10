import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'

interface Position {
  ticket: number
  symbol: string
  direction: string
  lot_size: number
  open_price: number
  current_price: number
  stop_loss: number | null
  take_profit: number | null
  profit: number
}

interface PositionsData {
  positions: Position[]
  total_profit: number
  count: number
}

export function PositionsPanel() {
  const { data, isLoading, error } = useQuery<PositionsData>({
    queryKey: ['positions'],
    queryFn: () => api.get('/api/trades/positions').then((r) => r.data),
    refetchInterval: 5000,
  })

  if (isLoading) return <PanelSkeleton />
  if (error) return <div style={styles.error}>Failed to load positions</div>

  const positions = data?.positions ?? []
  const totalPnL = data?.total_profit ?? 0

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.title}>Open Positions</span>
        <span style={{ ...styles.badge, color: totalPnL >= 0 ? '#26a69a' : '#ef5350' }}>
          {totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(2)} USD
        </span>
      </div>
      {positions.length === 0 ? (
        <div style={styles.empty}>No open positions</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              {['Symbol', 'Dir', 'Lots', 'Open', 'Current', 'SL', 'TP', 'P&L'].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.ticket}>
                <td style={styles.td}>{p.symbol}</td>
                <td style={{ ...styles.td, color: p.direction === 'buy' ? '#26a69a' : '#ef5350' }}>
                  {p.direction.toUpperCase()}
                </td>
                <td style={styles.td}>{p.lot_size}</td>
                <td style={styles.td}>{p.open_price.toFixed(2)}</td>
                <td style={styles.td}>{p.current_price.toFixed(2)}</td>
                <td style={styles.td}>{p.stop_loss?.toFixed(2) ?? '—'}</td>
                <td style={styles.td}>{p.take_profit?.toFixed(2) ?? '—'}</td>
                <td style={{ ...styles.td, color: p.profit >= 0 ? '#26a69a' : '#ef5350' }}>
                  {p.profit >= 0 ? '+' : ''}{p.profit.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function PanelSkeleton() {
  return <div style={{ ...styles.panel, color: '#8892a4', padding: 24 }}>Loading positions…</div>
}

const styles = {
  panel: { background: '#141820', border: '1px solid #1e2330', borderRadius: 8, overflow: 'hidden' } as React.CSSProperties,
  header: { padding: '12px 16px', borderBottom: '1px solid #1e2330', display: 'flex', justifyContent: 'space-between', alignItems: 'center' } as React.CSSProperties,
  title: { fontWeight: 600, color: '#e2e8f0', fontSize: 14 } as React.CSSProperties,
  badge: { fontSize: 13, fontWeight: 600 } as React.CSSProperties,
  empty: { padding: 24, textAlign: 'center', color: '#8892a4', fontSize: 13 } as React.CSSProperties,
  error: { padding: 24, color: '#ef5350', fontSize: 13 } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse' as const },
  th: { padding: '8px 12px', textAlign: 'left' as const, color: '#8892a4', fontSize: 12, borderBottom: '1px solid #1e2330' },
  td: { padding: '8px 12px', color: '#e2e8f0', fontSize: 13 },
}
