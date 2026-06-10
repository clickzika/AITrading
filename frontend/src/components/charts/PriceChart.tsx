import { useEffect, useRef } from 'react'
import { createChart, CandlestickSeries } from 'lightweight-charts'
import type { IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts'

interface OHLCV {
  ts: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface PriceChartProps {
  data: OHLCV[]
  symbol: string
  timeframe: string
  height?: number
}

export function PriceChart({ data, symbol, timeframe, height = 480 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#0f1117' },
        textColor: '#8892a4',
      },
      grid: {
        vertLines: { color: '#1e2330' },
        horzLines: { color: '#1e2330' },
      },
      crosshair: { mode: 1 },
      timeScale: {
        borderColor: '#1e2330',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: { borderColor: '#1e2330' },
    })

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })

    chartRef.current = chart
    seriesRef.current = series

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [height])

  useEffect(() => {
    if (!seriesRef.current || !data.length) return
    const candles: CandlestickData<Time>[] = data.map((d) => ({
      time: (new Date(d.ts).getTime() / 1000) as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))
    seriesRef.current.setData(candles)
    chartRef.current?.timeScale().fitContent()
  }, [data])

  return (
    <div style={{ background: '#0f1117', borderRadius: 8, overflow: 'hidden', border: '1px solid #1e2330' }}>
      <div style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid #1e2330' }}>
        <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 14 }}>{symbol}</span>
        <span style={{ color: '#8892a4', fontSize: 12 }}>{timeframe}</span>
      </div>
      <div ref={containerRef} style={{ width: '100%' }} />
    </div>
  )
}
