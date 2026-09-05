import Card from './Card.jsx'

function randomId() {
  return crypto.randomUUID()
}

export default function IdentityPanel({ identity, setIdentity }) {
  const { userId, teamId, isAdmin } = identity

  return (
    <Card title="Caller identity">
      <label className="block text-xs text-slate-500 mb-1">User ID (X-User-Id)</label>
      <div className="flex gap-2 mb-3">
        <input
          className="flex-1 border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono"
          value={userId}
          onChange={(e) => setIdentity({ ...identity, userId: e.target.value })}
        />
        <button
          className="px-2 py-1.5 text-xs rounded-md bg-slate-100 hover:bg-slate-200"
          onClick={() => setIdentity({ ...identity, userId: randomId() })}
        >
          random
        </button>
      </div>

      <label className="block text-xs text-slate-500 mb-1">Team ID (X-Team-Id)</label>
      <div className="flex gap-2 mb-3">
        <input
          className="flex-1 border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono"
          value={teamId}
          onChange={(e) => setIdentity({ ...identity, teamId: e.target.value })}
        />
        <button
          className="px-2 py-1.5 text-xs rounded-md bg-slate-100 hover:bg-slate-200"
          onClick={() => setIdentity({ ...identity, teamId: randomId() })}
        >
          random
        </button>
      </div>

      <label className="flex items-start gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={isAdmin}
          onChange={(e) => setIdentity({ ...identity, isAdmin: e.target.checked })}
        />
        X-Is-Admin (crosses the information barrier on reads, audited — FR-018)
      </label>
    </Card>
  )
}
