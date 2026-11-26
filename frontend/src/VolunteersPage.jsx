import { useCallback, useEffect, useMemo, useState } from 'react'
import { download, get, send } from './api'
import Notice from './Notice'
import VolunteerForm from './VolunteerForm'
import BulkUrlModal from './BulkUrlModal'

const URL_WARNING =
  'Adres zmieniony, kod QR zaktualizowany. Jeśli identyfikator był już wydrukowany, stary kod nadal prowadzi pod poprzedni adres – wydrukuj nowy identyfikator.'

function UrlCell({ v, onSave }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(v.url)

  if (!editing) {
    return (
      <div className="urlcell">
        <a href={v.url} target="_blank" rel="noreferrer" className="url">{v.url}</a>
        <button className="link" onClick={() => { setVal(v.url); setEditing(true) }}>zmień</button>
      </div>
    )
  }
  const save = async () => {
    if (await onSave(v, val)) setEditing(false)
  }
  return (
    <div className="urlcell">
      <input value={val} onChange={(e) => setVal(e.target.value)} autoFocus
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }} />
      <button className="btn small primary" onClick={save}>Zapisz</button>
      <button className="btn small" onClick={() => setEditing(false)}>Anuluj</button>
    </div>
  )
}

export default function VolunteersPage() {
  const [items, setItems] = useState([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState(new Set())
  const [editing, setEditing] = useState(null) // null | 'new' | volunteer
  const [bulk, setBulk] = useState(false)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setItems(await get('/volunteers?' + new URLSearchParams({ q, status })))
  }, [q, status])

  useEffect(() => {
    const t = setTimeout(() => load().catch((e) => setNotice({ type: 'error', text: e.message })), 200)
    return () => clearTimeout(t)
  }, [load])

  const selIds = useMemo(() => items.filter((v) => selected.has(v.id)).map((v) => v.id), [items, selected])
  const allSelected = items.length > 0 && selIds.length === items.length

  const toggle = (id) => {
    const s = new Set(selected)
    s.has(id) ? s.delete(id) : s.add(id)
    setSelected(s)
  }
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(items.map((v) => v.id)))

  const run = async (fn, okText) => {
    setBusy(true)
    setNotice(null)
    try {
      const r = await fn()
      if (okText) setNotice({ type: 'ok', text: typeof okText === 'function' ? okText(r) : okText })
      await load()
    } catch (e) {
      setNotice({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const saveUrl = async (v, url) => {
    try {
      await send(`/volunteers/${v.id}/url`, 'PATCH', { url })
      setNotice({ type: 'warn', text: URL_WARNING })
      await load()
      return true
    } catch (e) {
      setNotice({ type: 'error', text: e.message })
      return false
    }
  }

  const setOne = (v, st) => run(() => send(`/volunteers/${v.id}/status`, 'PATCH', { status: st }))
  const removeOne = (v) => {
    if (window.confirm(`Usunąć wolontariusza: ${v.first_name} ${v.last_name}? Tej operacji nie można cofnąć.`))
      run(() => send('/volunteers/bulk-delete', 'POST', { ids: [v.id] }), 'Wolontariusz usunięty.')
  }
  const removeSelected = () => {
    if (window.confirm(`Usunąć zaznaczonych wolontariuszy (${selIds.length})? Tej operacji nie można cofnąć.`))
      run(async () => { await send('/volunteers/bulk-delete', 'POST', { ids: selIds }); setSelected(new Set()) }, 'Wolontariusze usunięci.')
  }
  const pdf = (ids) => run(() => download('/badges/pdf', 'POST', { ids }, 'identyfikatory.pdf'))

  return (
    <div>
      <div className="toolbar">
        <input className="search" type="search" placeholder="Szukaj: nazwisko, imię lub adres URL" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Wszystkie statusy</option>
          <option value="active">Aktywni</option>
          <option value="inactive">Nieaktywni</option>
        </select>
        <div className="spacer" />
        <button className="btn primary" onClick={() => setEditing('new')}>Dodaj wolontariusza</button>
      </div>

      <Notice notice={notice} onClose={() => setNotice(null)} />

      <div className="bulkbar">
        <span>{items.length} osób{selIds.length > 0 && <>, zaznaczono <strong>{selIds.length}</strong></>}</span>
        <div className="spacer" />
        {selIds.length === 0 ? (
          <>
            <button className="btn" disabled={busy || !items.length} onClick={() => pdf(items.map((v) => v.id))}>
              PDF dla wszystkich widocznych ({items.length})
            </button>
          </>
        ) : (
          <>
            <button className="btn" disabled={busy} onClick={() => pdf(selIds)}>Identyfikatory PDF</button>
            <button className="btn" disabled={busy} onClick={() => run(() => download('/volunteers/qr-zip', 'POST', { ids: selIds }, 'kody-qr.zip'))}>Pobierz kody QR (ZIP)</button>
            <button className="btn" disabled={busy} onClick={() => run(() => send('/volunteers/regenerate-qr', 'POST', { ids: selIds }), (r) => `Wygenerowano ponownie kody QR: ${r.count}.`)}>Wygeneruj kody QR ponownie</button>
            <button className="btn" disabled={busy} onClick={() => setBulk(true)}>Zmień adresy URL</button>
            <button className="btn" disabled={busy} onClick={() => run(() => send('/volunteers/bulk-status', 'POST', { ids: selIds, status: 'active' }), 'Ustawiono status: aktywny.')}>Ustaw: aktywny</button>
            <button className="btn" disabled={busy} onClick={() => run(() => send('/volunteers/bulk-status', 'POST', { ids: selIds, status: 'inactive' }), 'Ustawiono status: nieaktywny.')}>Ustaw: nieaktywny</button>
            <button className="btn danger" disabled={busy} onClick={removeSelected}>Usuń</button>
          </>
        )}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="chk"><input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Zaznacz wszystkich" /></th>
              <th>Zdjęcie</th>
              <th>Nazwisko i imię</th>
              <th>Adres URL w kodzie QR</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((v) => (
              <tr key={v.id} className={selected.has(v.id) ? 'sel' : ''}>
                <td className="chk"><input type="checkbox" checked={selected.has(v.id)} onChange={() => toggle(v.id)} /></td>
                <td><img className="thumb" src={v.photo_url} alt="" loading="lazy" /></td>
                <td className="name"><strong>{v.last_name}</strong> {v.first_name}</td>
                <td><UrlCell key={v.url} v={v} onSave={saveUrl} /></td>
                <td>
                  <select className={'status ' + v.status} value={v.status} onChange={(e) => setOne(v, e.target.value)}>
                    <option value="active">Aktywny</option>
                    <option value="inactive">Nieaktywny</option>
                  </select>
                </td>
                <td className="rowactions">
                  <button className="btn small" onClick={() => setEditing(v)}>Edytuj</button>
                  <button className="btn small" disabled={busy} onClick={() => pdf([v.id])}>PDF</button>
                  <button className="btn small danger" onClick={() => removeOne(v)}>Usuń</button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan="6" className="empty">
                {q || status ? 'Brak wyników dla tych filtrów.' : 'Nie ma jeszcze wolontariuszy. Dodaj pierwszego lub zaimportuj listę z Excela.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <VolunteerForm
          volunteer={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={({ urlChanged }) => {
            setEditing(null)
            setNotice(urlChanged ? { type: 'warn', text: URL_WARNING } : { type: 'ok', text: 'Zapisano.' })
            load()
          }}
        />
      )}
      {bulk && (
        <BulkUrlModal
          ids={selIds}
          onClose={() => setBulk(false)}
          onApplied={(n) => {
            setBulk(false)
            setNotice({ type: 'warn', text: `Zmieniono adresy: ${n}. Kody QR zaktualizowane – wydrukuj nowe identyfikatory dla tych osób.` })
            load()
          }}
        />
      )}
    </div>
  )
}
