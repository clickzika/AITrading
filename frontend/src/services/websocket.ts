type WsEventHandler = (event: WsEvent) => void

export interface WsEvent {
  type: 'tick' | 'candle_close' | 'signal' | 'position' | 'risk'
  [key: string]: unknown
}

export class TradingWebSocket {
  private ws: WebSocket | null = null
  private handlers: WsEventHandler[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null

  connect(symbols?: string[]): void {
    const token = localStorage.getItem('access_token')
    if (!token) return

    const params = new URLSearchParams({ token })
    if (symbols?.length) params.set('symbols', symbols.join(','))

    this.ws = new WebSocket(`ws://${location.host}/ws?${params}`)
    this.ws.onmessage = (e) => {
      try {
        const event: WsEvent = JSON.parse(e.data)
        this.handlers.forEach((h) => h(event))
      } catch {
        // ignore parse errors
      }
    }
    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(symbols), 3000)
    }
  }

  on(handler: WsEventHandler): void {
    this.handlers.push(handler)
  }

  off(handler: WsEventHandler): void {
    this.handlers = this.handlers.filter((h) => h !== handler)
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
    this.ws = null
  }
}

export const tradingWs = new TradingWebSocket()
