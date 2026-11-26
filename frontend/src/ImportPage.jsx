import { useState } from 'react'
import { form, send } from './api'
import Notice from './Notice'

const LABEL = { ok: 'Nowy', duplicate: 'Już istnieje', error: 'Błąd' }

function VolunteerImport() {
  const [xlsx, setXlsx] = useState(null)
  const [zip, setZip] = useState(null)
  const [prev, setPrev] = useState(null)
  const [onDup, setOnDup] = useState('skip')
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  const check = async () => {
    setBusy(true); setNotice(null); setPrev(null)
    try {
      const fd = new FormData()
      fd.append('xlsx', xlsx)
      fd.append('photos', zip)
      setPrev(await form('/import/preview', 'POST', fd))
    } catch (e) {
      setNotice({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const commit = async () => {
    setBusy(true); setNotice(null)
    try {
      const r = await send('/import/commit', 'POST', { token: prev.token, on_duplicate: onDup })
      setPrev(null); setXlsx(null); setZip(null)
      setNotice({ type: 'ok', text: `Import zakończony. Dodano: ${r.created}, zaktualizowano: ${r.updated}, pominięto: ${r.skipped}.` })
    } catch (e) {
      setNotice({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const s = prev?.summary
  const canCommit = s && (s.ok > 0 || (onDup === 'update' && s.duplicate > 0))

  return (
    <section className="panel">
      <h2>Import wolontariuszy</h2>
      <p className="muted">
        Wgraj plik Excel (kolumny: <code>first_name</code>, <code>last_name</code>, <code>photo</code>, <code>url</code>)
        oraz archiwum ZIP ze zdjęciami o nazwach zgodnych z kolumną <code>photo</code>.{' '}
        <a href="/api/import/template.xlsx">Pobierz wzór pliku</a>
      </p>
      <div className="grid2">
        <label>Plik Excel (.xlsx)<input type="file" accept=".xlsx" onChange={(e) => { setXlsx(e.target.files[0] || null); setPrev(null) }} /></label>
        <label>Archiwum ZIP ze zdjęciami<input type="file" accept=".zip" onChange={(e) => { setZip(e.target.files[0] || null); setPrev(null) }} /></label>
      </div>
      <div className="actions left">
        <button className="btn primary" disabled={busy || !xlsx || !zip} onClick={check}>
          {busy && !prev ? 'Sprawdzanie…' : 'Sprawdź pliki'}
        </button>
      </div>
      <Notice notice={notice} onClose={() => setNotice(null)} />

      {prev && (
        <>
          <div className="chips">
            <span className="chip ok">Nowi: {s.ok}</span>
            <span className="chip warn">Już istnieją: {s.duplicate}</span>
            <span className="chip err">Błędy: {s.error}</span>
            <span className="chip">Razem wierszy: {s.total}</span>
          </div>
          <div className="table-wrap short">
            <table>
              <thead><tr><th>Wiersz</th><th>Zdjęcie</th><th>Osoba</th><th>Adres URL</th><th>Wynik</th></tr></thead>
              <tbody>
                {prev.rows.map((r) => (
                  <tr key={r.row} className={r.status === 'error' ? 'row-error' : ''}>
                    <td>{r.row}</td>
                    <td>{r.photo_file ? <img className="thumb" src={`/api/import/${prev.token}/photo/${r.row}`} alt="" /> : '—'}</td>
                    <td>{r.last_name} {r.first_name}</td>
                    <td className="url">{r.url}</td>
                    <td>
                      <span className={'tag ' + r.status}>{LABEL[r.status]}</span>
                      {r.messages.map((m, i) => <div key={i} className="small">{m}</div>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {s.duplicate > 0 && (
            <label className="inline">Osoby, które już są w bazie:
              <select value={onDup} onChange={(e) => setOnDup(e.target.value)}>
                <option value="skip">pomiń (bez zmian)</option>
                <option value="update">zaktualizuj adres URL i zdjęcie</option>
              </select>
            </label>
          )}
          <div className="actions left">
            <button className="btn primary" disabled={busy || !canCommit} onClick={commit}>Zatwierdź import</button>
            <span className="muted small">Wiersze z błędami zostaną pominięte.</span>
          </div>
        </>
      )}
    </section>
  )
}

function UrlImport() {
  const [xlsx, setXlsx] = useState(null)
  const [res, setRes] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  const call = async (apply) => {
    setBusy(true); setNotice(null)
    try {
      const fd = new FormData()
      fd.append('xlsx', xlsx)
      const r = await form(`/import/urls?apply=${apply}`, 'POST', fd)
      if (apply) {
        setRes(null); setXlsx(null)
        setNotice({ type: 'warn', text: `Zmieniono adresy: ${r.summary.change}. Kody QR zaktualizowane – wydrukuj nowe identyfikatory dla tych osób.` })
      } else setRes(r)
    } catch (e) {
      setNotice({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <h2>Import nowych adresów URL</h2>
      <p className="muted">
        Plik Excel z kolumną <code>url</code> oraz kolumną <code>id</code> albo kolumnami <code>first_name</code> i <code>last_name</code>.
        Najpierw zobaczysz podgląd zmian.
      </p>
      <label>Plik Excel (.xlsx)<input type="file" accept=".xlsx" onChange={(e) => { setXlsx(e.target.files[0] || null); setRes(null) }} /></label>
      <div className="actions left">
        <button className="btn" disabled={busy || !xlsx} onClick={() => call(false)}>Pokaż podgląd zmian</button>
      </div>
      <Notice notice={notice} onClose={() => setNotice(null)} />
      {res && (
        <>
          <div className="chips">
            <span className="chip ok">Do zmiany: {res.summary.change}</span>
            <span className="chip">Bez zmian: {res.summary.same}</span>
            <span className="chip err">Błędy: {res.summary.error}</span>
          </div>
          <div className="table-wrap short">
            <table>
              <thead><tr><th>Wiersz</th><th>Osoba</th><th>Obecny adres</th><th>Nowy adres</th><th>Wynik</th></tr></thead>
              <tbody>
                {res.rows.map((r) => (
                  <tr key={r.row} className={r.status === 'error' ? 'row-error' : ''}>
                    <td>{r.row}</td><td>{r.name || '—'}</td>
                    <td className="url">{r.old_url}</td><td className="url">{r.new_url}</td>
                    <td><span className={'tag ' + r.status}>{{ change: 'Zmiana', same: 'Bez zmian', error: 'Błąd' }[r.status]}</span>
                      {r.message && r.status !== 'same' && <div className="small">{r.message}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="actions left">
            <button className="btn primary" disabled={busy || res.summary.change === 0} onClick={() => call(true)}>Zastosuj zmiany</button>
          </div>
        </>
      )}
    </section>
  )
}

export default function ImportPage() {
  return (
    <div className="stack">
      <VolunteerImport />
      <UrlImport />
    </div>
  )
}
