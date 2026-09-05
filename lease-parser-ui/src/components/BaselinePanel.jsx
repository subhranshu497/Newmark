import { useState, useEffect } from 'react'
import Card from './Card.jsx'

export default function BaselinePanel({ api, documentId }) {
  const [ids, setIds] = useState('')
  const [minutes, setMinutes] = useState('172.5')
  const [method, setMethod] = useState('demo timing')
  const [status, setStatus] = useState(null)

  useEffect(() => {
    if (documentId) setIds(documentId)
  }, [documentId])

  const submit = async () => {
    setStatus('submitting')
    const { ok } = await api('POST', '/v1/baseline-measurements', {
      body: {
        sample_lease_ids: ids.split(',').map((s) => s.trim()).filter(Boolean),
        measured_median_minutes: parseFloat(minutes),
        method,
      },
    })
    setStatus(ok ? 'done' : 'error')
  }

  return (
    <Card title="Baseline measurement">
      <label className="block text-xs text-slate-500 mb-1">Sample lease IDs (comma-separated)</label>
      <textarea
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono mb-3"
        rows={2}
        value={ids}
        onChange={(e) => setIds(e.target.value)}
      />
      <label className="block text-xs text-slate-500 mb-1">Measured median minutes</label>
      <input
        type="number"
        step="0.1"
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mb-3"
        value={minutes}
        onChange={(e) => setMinutes(e.target.value)}
      />
      <label className="block text-xs text-slate-500 mb-1">Method</label>
      <input
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mb-3"
        value={method}
        onChange={(e) => setMethod(e.target.value)}
      />
      <button
        className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
        onClick={submit}
      >
        Submit measurement
      </button>
      {status === 'done' && <p className="text-sm text-green-600 mt-2">Submitted.</p>}
      {status === 'error' && <p className="text-sm text-red-600 mt-2">Failed.</p>}
    </Card>
  )
}
