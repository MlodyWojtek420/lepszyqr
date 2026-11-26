import { useState } from 'react'
import { send } from './api'

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await send('/auth/login', 'POST', { username, password })
      onLogin(r.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="center">
      <form className="panel login" onSubmit={submit}>
        <h1>Identyfikatory wolontariuszy</h1>
        <p className="muted">Zaloguj się do panelu administratora.</p>
        <label>Nazwa użytkownika
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
        </label>
        <label>Hasło
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        {error && <div className="notice error">{error}</div>}
        <button className="btn primary" disabled={busy || !username || !password}>Zaloguj</button>
      </form>
    </div>
  )
}
