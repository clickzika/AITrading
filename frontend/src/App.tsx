import { isAuthenticated } from '@/services/auth'

function App() {
  if (!isAuthenticated()) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0f1117', color: '#e2e8f0', fontFamily: 'sans-serif' }}>
        <div style={{ textAlign: 'center' }}>
          <h1 style={{ color: '#6c63ff', marginBottom: 8 }}>AITrading</h1>
          <p style={{ color: '#8892a4', marginBottom: 24 }}>Dashboard loading — backend not yet connected</p>
          <p style={{ color: '#8892a4', fontSize: 13 }}>Phase 3 (T36–T42) will replace this placeholder</p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ background: '#0f1117', minHeight: '100vh', color: '#e2e8f0', fontFamily: 'sans-serif', padding: 40 }}>
      <h1 style={{ color: '#6c63ff' }}>AITrading Dashboard</h1>
      <p style={{ color: '#8892a4' }}>Scaffold complete — feature development begins in Gate 4</p>
    </div>
  )
}

export default App
