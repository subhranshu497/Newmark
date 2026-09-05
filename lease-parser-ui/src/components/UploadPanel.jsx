import { useState } from 'react'
import Card from './Card.jsx'
import Alert from './Alert.jsx'

export default function UploadPanel({ api, teamId, onParsed }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)

    const form = new FormData()
    form.append('file', file)
    if (teamId) form.append('team_id', teamId)

    try {
      const { ok, data, status } = await api('POST', '/demo/parse-upload', { body: form })
      if (!ok) {
        setError(`Failed (${status}): ${data?.detail || 'unknown error'}`)
        return
      }
      setResult(data)
      onParsed(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card title="1. Upload a lease PDF to parse">
      <p className="text-sm text-slate-500 mb-3">
        Extracts the PDF's text locally, then runs the real pipeline: Claude extraction (OpenAI
        failover, FR-012), confidence-threshold routing to auto-populate or the review queue
        (FR-004/FR-013). Uses the API keys in the backend's <span className="font-mono">.env</span> —
        this is a real, billed model call, not a fake seed.
      </p>
      <input
        type="file"
        accept="application/pdf"
        className="block text-sm mb-2"
        onChange={(e) => setFile(e.target.files[0] || null)}
      />
      <button
        className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        onClick={submit}
        disabled={!file || loading}
      >
        {loading ? 'Parsing…' : 'Upload & parse'}
      </button>

      {loading && (
        <p className="text-sm text-slate-500 mt-2">
          Parsing… (real Claude/OpenAI call, may take a few seconds)
        </p>
      )}
      {error && <Alert>{error}</Alert>}
      {result && result.ocr_status === 'EXCLUDED_LOW_QUALITY' && (
        <Alert>
          Couldn't read this PDF — it has no usable text layer (likely a scanned image with no
          OCR available in this demo). Routed to the review queue.
        </Alert>
      )}
      {result && result.ocr_status !== 'EXCLUDED_LOW_QUALITY' && !result.is_valid_lease_document && (
        <Alert>
          <strong>This document is not a valid lease document</strong> — none of the five lease
          fields (Base Rent, Escalation Schedule, Free Rent Period, TI Allowance, Term) were
          found in it.
          {result.document_summary && (
            <div className="mt-1.5 text-amber-700">{result.document_summary}</div>
          )}
        </Alert>
      )}
      {result && result.is_valid_lease_document && (
        <p className="text-sm text-slate-600 mt-2">
          Parsed. Document <span className="font-mono">{result.document_id}</span> —{' '}
          {result.fields.length} field(s) extracted,{' '}
          {result.fields.filter((f) => f.auto_populated).length} auto-populated,{' '}
          {result.review_queue_item_ids.length} routed to the review queue.
        </p>
      )}
    </Card>
  )
}
