const COLORS = {
  UNVERIFIED: 'bg-slate-100 text-slate-700',
  VERIFIED: 'bg-green-100 text-green-700',
  RESOLVED: 'bg-green-100 text-green-700',
  OVERRIDDEN: 'bg-amber-100 text-amber-700',
  PENDING: 'bg-blue-100 text-blue-700',
  IN_PROGRESS: 'bg-blue-100 text-blue-700',
}

export default function Badge({ status }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${COLORS[status] || 'bg-slate-100 text-slate-700'}`}>
      {status}
    </span>
  )
}
