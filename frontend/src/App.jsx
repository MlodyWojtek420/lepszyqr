import { useEffect, useState } from 'react'
import { get, send } from './api'
import Login from './Login'
import VolunteersPage from './VolunteersPage'
import ImportPage from './ImportPage'
import SettingsPage from './SettingsPage'

const TABS = [
  ['volunteers', 'Wolontariusze'],
  ['import', 'Import z Excela'],
  ['template', 'Szablon identyfikatora'],
]

export default function App() {
  const [user, setUser] = useState(undefined)
  const [tab, setTab] = useState('volunteers')

  useEffect(() => {
    get('/auth/me').then((r) => setUser(r.user)).catch(() => setUser(null))
    const onUnauthorized = () => setUser(null)
    window.addEventListener('unauthorized', onUnauthorized)
    return () => window.removeEventListener('unauthorized', onUnauthorized)
  }, [])

  const logout = async () => {
    await send('/auth/logout', 'POST', {}).catch(() => {})
    setUser(null)
  }

  if (user === undefined) return <div className="center muted">Ładowanie…</div>
  if (!user) return <Login onLogin={setUser} />

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Identyfikatory wolontariuszy</div>
        <nav>
          {TABS.map(([key, label]) => (
            <button key={key} className={'tab' + (tab === key ? ' active' : '')} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </nav>
        <button className="btn ghost" onClick={logout}>Wyloguj</button>
      </header>
      <main className="content">
        {tab === 'volunteers' && <VolunteersPage />}
        {tab === 'import' && <ImportPage />}
        {tab === 'template' && <SettingsPage />}
      </main>
    </div>
  )
}
