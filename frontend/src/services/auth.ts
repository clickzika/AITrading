export async function login(password: string): Promise<void> {
  const body = new URLSearchParams({ username: 'trader', password })
  const res = await fetch('/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!res.ok) throw new Error('Invalid password')
  const data = await res.json()
  localStorage.setItem('access_token', data.access_token)
}

export function logout(): void {
  localStorage.removeItem('access_token')
  window.location.href = '/login'
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('access_token')
}
