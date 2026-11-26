function messageOf(detail, fallback) {
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  return detail.message || fallback
}

async function request(path, opts = {}) {
  const res = await fetch('/api' + path, { credentials: 'same-origin', ...opts })
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/login')) {
      window.dispatchEvent(new Event('unauthorized'))
    }
    let detail = null
    try {
      detail = (await res.json()).detail
    } catch {
      /* brak treści JSON */
    }
    const err = new Error(messageOf(detail, `Błąd serwera (${res.status})`))
    err.status = res.status
    err.code = detail && detail.code
    throw err
  }
  return res
}

export const get = (path) => request(path).then((r) => r.json())

export const send = (path, method, body) =>
  request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((r) => r.json())

export const form = (path, method, fd) => request(path, { method, body: fd }).then((r) => r.json())

function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

function filenameFrom(res, fallback) {
  const m = /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') || '')
  return m ? m[1] : fallback
}

export async function download(path, method, body, fallbackName) {
  const res = await request(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  saveBlob(await res.blob(), filenameFrom(res, fallbackName))
}

export async function openPdf(path) {
  const res = await request(path)
  const blob = await res.blob()
  window.open(URL.createObjectURL(blob), '_blank')
}
