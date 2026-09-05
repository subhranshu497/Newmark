export default function Card({ title, action, children }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4 shadow-sm">
      {(title || action) && (
        <div className="flex items-center justify-between mb-3">
          {title && (
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
