export default function Notice({ notice, onClose }) {
  if (!notice) return null
  return (
    <div className={'notice ' + notice.type}>
      <span>{notice.text}</span>
      {onClose && <button className="x" onClick={onClose} aria-label="Zamknij">×</button>}
    </div>
  )
}
