import { useEffect, useState } from 'react'
import { form, get, openPdf, send } from './api'
import Notice from './Notice'

export default function SettingsPage() {
  const [c, setC] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)
  const [logoKey, setLogoKey] = useState(0)

  useEffect(() => {
    get('/template').then(setC).catch((e) => setNotice({ type: 'error', text: e.message }))
  }, [])
  if (!c) return <Notice notice={notice} />

  const set = (k, num) => (e) => setC({ ...c, [k]: num ? Number(e.target.value) : e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const wrap = async (fn, ok) => {
    setBusy(true); setNotice(null)
    try { await fn(); if (ok) setNotice({ type: 'ok', text: ok }) } catch (e) { setNotice({ type: 'error', text: e.message }) } finally { setBusy(false) }
  }
  const { has_logo, ...payload } = c

  const save = () => wrap(() => send('/template', 'PUT', payload), 'Szablon zapisany.')
  const preview = () => wrap(async () => { await send('/template', 'PUT', payload); await openPdf('/template/preview.pdf') })
  const upload = (e) => {
    const f = e.target.files[0]
    if (!f) return
    const fd = new FormData()
    fd.append('logo', f)
    wrap(async () => { await form('/template/logo', 'POST', fd); setC({ ...c, has_logo: true }); setLogoKey((k) => k + 1) }, 'Logo zapisane.')
  }
  const removeLogo = () => wrap(async () => { await send('/template/logo', 'DELETE'); setC({ ...c, has_logo: false }) }, 'Logo usunięte.')

  return (
    <section className="panel">
      <h2>Szablon identyfikatora</h2>
      <p className="muted">Jeden szablon dla wszystkich identyfikatorów. Podgląd generuje przykładowy PDF z aktualnymi ustawieniami.</p>
      <div className="grid2">
        <label>Nazwa organizacji<input value={c.org_name} onChange={set('org_name')} /></label>
        <label>Podpis roli<input value={c.role_label} onChange={set('role_label')} /></label>
      </div>
      <label>Tekst na dole identyfikatora<input value={c.footer_text} onChange={set('footer_text')} /></label>
      <div className="grid3">
        <label>Kolor nagłówka<input type="color" value={c.primary_color} onChange={set('primary_color')} /></label>
        <label>Kolor tła<input type="color" value={c.background_color} onChange={set('background_color')} /></label>
        <label>Kolor tekstu<input type="color" value={c.text_color} onChange={set('text_color')} /></label>
      </div>
      <div className="grid3">
        <label>Szerokość (mm)<input type="number" min="40" max="120" value={c.card_width_mm} onChange={set('card_width_mm', true)} /></label>
        <label>Wysokość (mm)<input type="number" min="50" max="200" value={c.card_height_mm} onChange={set('card_height_mm', true)} /></label>
        <label>Układ PDF
          <select value={c.layout} onChange={set('layout')}>
            <option value="a4">Arkusze A4 (kilka na stronie)</option>
            <option value="card">Jedna karta na stronę (drukarka kart)</option>
          </select>
        </label>
      </div>
      {c.layout === 'a4' && (
        <div className="grid3">
          <label>Margines arkusza (mm)<input type="number" min="0" max="30" value={c.sheet_margin_mm} onChange={set('sheet_margin_mm', true)} /></label>
          <label className="inline"><input type="checkbox" checked={c.crop_lines} onChange={set('crop_lines')} /> Linie cięcia wokół kart</label>
        </div>
      )}
      <div className="logo-row">
        {has_logo && <img key={logoKey} className="logo-prev" src={`/api/template/logo?v=${logoKey}`} alt="Logo" />}
        <label className="btn">{has_logo ? 'Zmień logo' : 'Dodaj logo'}<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={upload} /></label>
        {has_logo && <button className="btn" onClick={removeLogo} disabled={busy}>Usuń logo</button>}
      </div>
      <Notice notice={notice} onClose={() => setNotice(null)} />
      <div className="actions left">
        <button className="btn primary" disabled={busy} onClick={save}>Zapisz szablon</button>
        <button className="btn" disabled={busy} onClick={preview}>Zapisz i pokaż podgląd PDF</button>
      </div>
    </section>
  )
}
