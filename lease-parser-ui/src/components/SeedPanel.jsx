import { useState } from 'react'
import Card from './Card.jsx'

export default function SeedPanel({ api, teamId, onSeeded }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const seed = async () => {
    setLoading(true)
    try {
      const { ok, data, status } = await api('POST', '/demo/seed', {
        body: { team_id: teamId || null },
      })
      if (!ok) {
        setResult({ error: `Failed (${status})` })
        return
      }
      setResult(data)
      onSeeded(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card title="...or seed a fake demo record">
      <p className="text-sm text-slate-500 mb-3">
        Skips parsing entirely — creates a LeaseDocument with one high-confidence BASE_RENT
        field (ready to verify) and one low-confidence FREE_RENT_PERIOD field already routed to
        the review queue. Useful for exercising the UI without spending API credits.
      </p>
      <button
        className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        onClick={seed}
        disabled={loading}
      >
        {loading ? 'Seeding…' : 'Seed demo record'}
      </button>
      {result?.error && <p className="text-sm text-red-600 mt-2">{result.error}</p>}
      {result && !result.error && (
        <p className="text-sm text-slate-600 mt-2">
          Seeded. Document <span className="font-mono">{result.document_id}</span> — BASE_RENT
          field <span className="font-mono">{result.base_rent_field_id}</span> ready to verify,
          FREE_RENT_PERIOD field routed to review queue item{' '}
          <span className="font-mono">{result.review_queue_item_id}</span>.
        </p>
      )}
    </Card>
  )
}
