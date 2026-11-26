import { useState } from 'react'
import { form } from './api'

export default function VolunteerForm({ volunteer, onClose, onSaved }) {
  const isNew = !volunteer
  const [f, setF] = useState({
    first_name: volunteer?.first_name || '',
    last_name: volunteer?.last_name || '',
    url: volunteer?.url || '',
    status: volunteer?.status || 'active',
  })
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(volunteer?.photo_url || null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const pick = (e) => {
    const fl = e.target.files[0]
    if (!fl) return
    setFile(fl)
    setPreview(URL.createObjectURL(fl))
  }

  const submit = async (force = false) => {
    setError('')
    if (isNew && !file) return setError('Dodaj zdjęcie wolontariusza.')
    const fd = new FormData()
    Object.entries(f).forEach(([k, v]) => fd.append(k, v))
    if (file) fd.append('photo', file)
    if (force) fd.append('force', 'true')
    setSaving(true)
    try {
      await form(isNew ? '/volunteers' : `/volunteers/${volunteer.id}`, isNew ? 'POST' : 'PUT', fd)
      onSaved({ urlChanged: !isNew && f.url.trim() !== volunteer.url })
    } catch (e) {
      if (e.status === 409 && e.code === 'duplicate') {
        if (window.confirm(e.message + ' Dodać mimo to?')) return await submit(true)
      } else {
        setError(e.message)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true">
        <h2>{isNew ? 'Dodaj wolontariusza' : 'Edytuj wolontariusza'}</h2>
        <div className="grid2">
          <label>Imię<input value={f.first_name} onChange={set('first_name')} autoFocus /></label>
          <label>Nazwisko<input value={f.last_name} onChange={set('last_name')} /></label>
        </div>
        <label>Adres URL strony weryfikacyjnej (trafi do kodu QR)
          <input value={f.url} onChange={set('url')} placeholder="https://organizacja.pl/wolontariusze/jan-kowalski" />
        </label>
        {!isNew && (
          <label>Status
            <select value={f.status} onChange={set('status')}>
              <option value="active">Aktywny</option>
              <option value="inactive">Nieaktywny</option>
            </select>
          </label>
        )}
        <div className="photo-pick">
          {preview ? <img src={preview} alt="" className="photo-prev" /> : <div className="photo-prev empty">brak zdjęcia</div>}
          <label className="btn">
            {isNew ? 'Wybierz zdjęcie' : 'Zmień zdjęcie'}
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={pick} hidden />
          </label>
        </div>
        {error && <div className="notice error">{error}</div>}
        <div className="actions">
          <button className="btn" onClick={onClose}>Anuluj</button>
          <button className="btn primary" disabled={saving} onClick={() => submit(false)}>
            {saving ? 'Zapisywanie…' : 'Zapisz'}
          </button>
        </div>
      </div>
    </div>
  )
}
