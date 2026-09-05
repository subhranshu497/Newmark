import Card from './Card.jsx'

export default function BackendPanel({ apiBase, setApiBase }) {
  return (
    <Card title="Backend">
      <label className="block text-xs text-slate-500 mb-1">API base URL</label>
      <input
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono"
        value={apiBase}
        onChange={(e) => setApiBase(e.target.value)}
      />
    </Card>
  )
}
