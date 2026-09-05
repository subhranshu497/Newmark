import Card from './Card.jsx'

export default function DocumentPanel({ documentId, setDocumentId }) {
  return (
    <Card title="Document">
      <label className="block text-xs text-slate-500 mb-1">Document ID</label>
      <input
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono"
        value={documentId}
        onChange={(e) => setDocumentId(e.target.value)}
      />
    </Card>
  )
}
