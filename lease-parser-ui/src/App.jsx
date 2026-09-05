import { useMemo, useState } from 'react'
import { createApiClient, identityHeaders } from './api.js'
import BackendPanel from './components/BackendPanel.jsx'
import IdentityPanel from './components/IdentityPanel.jsx'
import UploadPanel from './components/UploadPanel.jsx'
import SeedPanel from './components/SeedPanel.jsx'
import DocumentPanel from './components/DocumentPanel.jsx'
import BaselinePanel from './components/BaselinePanel.jsx'
import FieldsTable from './components/FieldsTable.jsx'
import ReviewQueueTable from './components/ReviewQueueTable.jsx'
import RequestLog from './components/RequestLog.jsx'

export default function App() {
  const [apiBase, setApiBase] = useState('http://127.0.0.1:8000')
  const [identity, setIdentity] = useState({
    userId: crypto.randomUUID(),
    teamId: crypto.randomUUID(),
    isAdmin: false,
  })
  const [documentId, setDocumentId] = useState('')
  const [fields, setFields] = useState([])
  const [fieldsError, setFieldsError] = useState(null)
  const [queueItems, setQueueItems] = useState(null)
  const [queueError, setQueueError] = useState(null)
  const [log, setLog] = useState([])

  const api = useMemo(
    () => createApiClient(apiBase, (entry) => setLog((prev) => [entry, ...prev])),
    [apiBase],
  )

  const loadFields = async (docId = documentId) => {
    if (!docId) return
    const { ok, data } = await api('GET', `/v1/lease-documents/${docId}/extracted-fields`, {
      headers: identityHeaders(identity),
    })
    if (ok) {
      setFields(data)
      setFieldsError(null)
    } else {
      setFieldsError(`${data?.detail || 'unknown error'}`)
    }
  }

  const loadQueue = async () => {
    if (!identity.teamId) return
    const { ok, data } = await api('GET', `/v1/review-queue?teamId=${identity.teamId}`, {
      headers: identityHeaders(identity),
    })
    if (ok) {
      setQueueItems(data)
      setQueueError(null)
    } else {
      setQueueError(`${data?.detail || 'unknown error'}`)
    }
  }

  const handleParsed = (result) => {
    setIdentity((prev) => ({ ...prev, teamId: result.team_id }))
    setDocumentId(result.document_id)
    loadFields(result.document_id)
    loadQueue()
  }

  const handleSeeded = (result) => {
    setIdentity((prev) => ({ ...prev, teamId: result.team_id }))
    setDocumentId(result.document_id)
    loadFields(result.document_id)
  }

  const verifyField = async (fieldId, value) => {
    await api('POST', `/v1/lease-documents/${documentId}/extracted-fields/${fieldId}/verify`, {
      headers: identityHeaders(identity),
      body: { value },
    })
    await loadFields()
  }

  const resolveItem = async (itemId, body) => {
    await api('POST', `/v1/review-queue/${itemId}/resolve`, {
      headers: identityHeaders(identity),
      body,
    })
    await loadQueue()
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <h1 className="text-xl font-bold text-slate-900">lease-parser-ui</h1>
      <p className="text-sm text-slate-500 mb-5 max-w-3xl">
        Standalone frontend for the <span className="font-mono">lease-abstraction</span> service's
        local demo — a separate origin from the API, so requests below are cross-origin (CORS).
        Backend must be started with{' '}
        <span className="font-mono">LEASE_ABSTRACTION_ENABLE_DEMO_UI=1</span>.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 items-start">
        <div>
          <BackendPanel apiBase={apiBase} setApiBase={setApiBase} />
          <IdentityPanel identity={identity} setIdentity={setIdentity} />
          <UploadPanel api={api} teamId={identity.teamId} onParsed={handleParsed} />
          <SeedPanel api={api} teamId={identity.teamId} onSeeded={handleSeeded} />
          <DocumentPanel documentId={documentId} setDocumentId={setDocumentId} />
          <BaselinePanel api={api} documentId={documentId} />
        </div>

        <div>
          <FieldsTable
            fields={fields}
            documentId={documentId}
            error={fieldsError}
            onLoad={() => loadFields()}
            onVerify={verifyField}
          />
          <ReviewQueueTable
            items={queueItems}
            error={queueError}
            onLoad={loadQueue}
            onResolve={resolveItem}
          />
          <RequestLog entries={log} onClear={() => setLog([])} />
        </div>
      </div>
    </div>
  )
}
