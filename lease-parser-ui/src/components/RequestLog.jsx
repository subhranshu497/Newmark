import Card from './Card.jsx'

function statusColor(status) {
  const bucket = status === 0 ? 0 : Math.floor(status / 100)
  if (bucket === 2) return 'text-green-600'
  if (bucket === 4) return 'text-amber-600'
  return 'text-red-600'
}

export default function RequestLog({ entries, onClear }) {
  return (
    <Card
      title="Request log"
      action={
        <button
          className="px-2 py-1 text-xs rounded-md bg-slate-100 hover:bg-slate-200"
          onClick={onClear}
        >
          clear
        </button>
      }
    >
      <div className="max-h-80 overflow-y-auto font-mono text-xs">
        {entries.map((e, i) => (
          <div key={i} className={`py-1.5 border-b border-dashed border-slate-200 ${statusColor(e.status)}`}>
            <div>
              <strong>{e.method} {e.url}</strong> → {e.status}
            </div>
            <pre className="whitespace-pre-wrap text-slate-700 mt-0.5">
              {JSON.stringify(e.data, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </Card>
  )
}
