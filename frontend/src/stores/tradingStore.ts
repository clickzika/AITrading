import { create } from 'zustand'

export type Timeframe = 'M1' | 'M5' | 'M15' | 'H1' | 'H4' | 'D1'

interface TradingState {
  symbol: string
  timeframe: Timeframe
  autoTrading: boolean
  setSymbol: (symbol: string) => void
  setTimeframe: (tf: Timeframe) => void
  setAutoTrading: (v: boolean) => void
}

export const useTradingStore = create<TradingState>((set) => ({
  symbol: 'XAUUSD',
  timeframe: 'H1',
  autoTrading: false,
  setSymbol: (symbol) => set({ symbol }),
  setTimeframe: (timeframe) => set({ timeframe }),
  setAutoTrading: (autoTrading) => set({ autoTrading }),
}))
