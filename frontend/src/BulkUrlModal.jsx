import { useState } from 'react'
import { send } from './api'

export default function BulkUrlModal({ ids, onClose, onApplied }) {
  const [mode, setMode] = useState('replace')
  const [find, setFind] = useState('')
  const [replace, setReplace] = useState('')
  const [pattern, setPattern] = useState('https://organizacja.pl/wolontariusze/{slug}')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const call = async (apply) => {
    setBusy(true)
    setError('')
    try {
      const r = await send('/volunteers/bulk-urls/transform', 'POST', { ids, mode, find, replace, pattern, apply })
      if (apply) onApplied(r.changed)
      else setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const reset = (fn) => (e) => {
    fn(e.target.value)
    setResult(null)
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal wide" role="dialog" aria-modal="true">
        <h2>Zmień adresy URL ({ids.length} osób)</h2>
        <div className="segmented">
          <button className={mode === 'replace' ? 'on' : ''} onClick={() => { setMode('replace'); setResult(null) }}>Zamień fragment</button>
          <button className={mode === 'pattern' ? 'on' : ''} onClick={() => { setMode('pattern'); setResult(null) }}>Wzorzec adresu</button>
        </div>
        {mode === 'replace' ? (
          <div className="grid2">
            <label>Znajdź<input value={find} onChange={reset(setFind)} placeholder="https://stara-domena.pl" /></label>
            <label>Zamień na<input value={replace} onChange={reset(setReplace)} placeholder="https://nowa-domena.pl" /></label>
          </div>
        ) : (
          <>
            <label>Wzorzec
              <input value={pattern} onChange={reset(setPattern)} />
            </label>
            <p className="muted small">
              Dostępne znaczniki: <code>{'{slug}'}</code> (jan-kowalski), <code>{'{first_name}'}</code>, <code>{'{last_name}'}</code>, <code>{'{id}'}</code>.
              Polskie znaki są zamieniane na łacińskie.
            </p>
          </>
        )}
        <div className="actions left">
          <button className="btn" disabled={busy} onClick={() => call(false)}>Pokaż podgląd</button>
        </div>
        {error && <div className="notice error">{error}</div>}
        {result && (
          <>
            <p><strong>{result.changed}</strong> adresów zostanie zmienionych.</p>
            <div className="table-wrap short">
              <table>
                <thead><tr><th>Osoba</th><th>Obecny adres</th><th>Nowy adres</th></tr></thead>
                <tbody>
                  {result.rows.map((r) => (
                    <tr key={r.id} className={r.error ? 'row-error' : ''}>
                      <td>{r.name}</td>
                      <td className="url">{r.old_url}</td>
                      <td className="url">
                        {r.error ? <span className="err">{r.error}</span> : r.changed ? r.new_url : <span className="muted">bez zmian</span>}
                        {r.warning && <div className="warn">{r.warning}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="notice warn">
              Zmiana adresu aktualizuje kod QR w systemie, ale nie zmienia już wydrukowanych identyfikatorów.
              Dla zmienionych osób wydrukuj nowe identyfikatory.
            </p>
          </>
        )}
        <div className="actions">
          <button className="btn" onClick={onClose}>Zamknij</button>
          <button className="btn primary" disabled={busy || !result || result.changed === 0} onClick={() => call(true)}>
            Zastosuj zmiany
          </button>
        </div>
      </div>
    </div>
  )
}
