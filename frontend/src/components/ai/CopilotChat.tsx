import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '@/services/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export function CopilotChat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Hello! I\'m your AI trading co-pilot. Ask me about market analysis, SMC concepts, or strategy advice.' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  async function sendMessage(e: FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    const userMsg: Message = { role: 'user', content: text }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setLoading(true)

    try {
      const response = await api.post<{ role: string; content: string }>('/api/ai/chat', {
        messages: newMessages.slice(-10), // last 10 messages as context
        stream: false,
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: response.data.content }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '⚠️ AI co-pilot unavailable. Check ANTHROPIC_API_KEY configuration.' },
      ])
    } finally {
      setLoading(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.title}>AI Co-Pilot</span>
        <span style={{ fontSize: 11, color: '#6c63ff' }}>Claude</span>
      </div>
      <div style={styles.messages}>
        {messages.map((m, i) => (
          <div key={i} style={{ ...styles.bubble, ...(m.role === 'user' ? styles.userBubble : styles.aiBubble) }}>
            <span style={styles.roleTag}>{m.role === 'user' ? 'You' : 'Claude'}</span>
            <p style={styles.messageText}>{m.content}</p>
          </div>
        ))}
        {loading && (
          <div style={{ ...styles.bubble, ...styles.aiBubble }}>
            <span style={styles.roleTag}>Claude</span>
            <p style={{ ...styles.messageText, color: '#8892a4' }}>Thinking…</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={sendMessage} style={styles.form}>
        <input
          style={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about market structure, SMC, trade setup…"
          disabled={loading}
        />
        <button type="submit" style={styles.sendBtn} disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}

const styles = {
  panel: { background: '#141820', border: '1px solid #1e2330', borderRadius: 8, display: 'flex', flexDirection: 'column' as const, height: '100%' },
  header: { padding: '12px 16px', borderBottom: '1px solid #1e2330', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontWeight: 600, color: '#e2e8f0', fontSize: 14 },
  messages: { flex: 1, overflowY: 'auto' as const, padding: 16, display: 'flex', flexDirection: 'column' as const, gap: 12, maxHeight: 360 },
  bubble: { padding: '10px 14px', borderRadius: 8, maxWidth: '85%' },
  userBubble: { background: '#1e2d5a', alignSelf: 'flex-end' as const },
  aiBubble: { background: '#1a2030', alignSelf: 'flex-start' as const },
  roleTag: { fontSize: 11, color: '#8892a4', display: 'block' as const, marginBottom: 4 },
  messageText: { margin: 0, color: '#e2e8f0', fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' as const },
  form: { display: 'flex', gap: 8, padding: '12px 16px', borderTop: '1px solid #1e2330' },
  input: { flex: 1, background: '#0f1117', border: '1px solid #1e2330', borderRadius: 4, color: '#e2e8f0', padding: '8px 12px', fontSize: 13, outline: 'none' },
  sendBtn: { background: '#6c63ff', border: 'none', color: '#fff', padding: '8px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600 } as React.CSSProperties,
}
