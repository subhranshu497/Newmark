export default function Alert({ children }) {
  return (
    <div className="mt-2 bg-amber-50 text-amber-800 border border-amber-200 rounded-md px-3 py-2 text-sm">
      {children}
    </div>
  )
}
