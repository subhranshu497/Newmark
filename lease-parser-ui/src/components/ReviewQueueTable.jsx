import { useState } from 'react'
import Card from './Card.jsx'
import Badge from './Badge.jsx'
import Modal from './Modal.jsx'
import { FIELD_TYPES } from '../fieldSchema.js'

function ResolveModal({ item, onClose, onSubmit }) {
  const [value, setValue] = useState('{}')
  const [fieldType, setFieldType] = useState('')
  const [error, setError] = useState('')

  const submit = () => {
    let parsed
    try {
      parsed = JSON.parse(value)
    } catch {
      setError('Invalid JSON')
      return
    }
    onSubmit({ value: parsed, field_type: fieldType || undefined })
  }

  return (
    <Modal title="Resolve review queue item" onClose={onClose}>
      <label className="block text-xs text-slate-500 mb-1">Resolution value (JSON)</label>
      <textarea
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono mb-2"
        rows={3}
        value={value}
        onChange={(e) => { setValue(e.target.value); setError('') }}
      />
      {item.extracted_field_id == null && (
        <>
          <label className="block text-xs text-slate-500 mb-1">
            Field type (required — this item has no linked field)
          </label>
          <select
            className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mb-2"
            value={fieldType}
            onChange={(e) => setFieldType(e.target.value)}
          >
            <option value="">Select…</option>
            {FIELD_TYPES.map((ft) => (
              <option key={ft} value={ft}>{ft}</option>
            ))}
          </select>
        </>
      )}
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      <div className="flex justify-end gap-2 mt-3">
        <button className="px-3 py-1.5 text-sm rounded-md bg-slate-100 hover:bg-slate-200" onClick={onClose}>
          Cancel
        </button>
        <button className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700" onClick={submit}>
          Resolve
        </button>
      </div>
    </Modal>
  )
}

export default function ReviewQueueTable({ items, error, onLoad, onResolve }) {
  const [modalItem, setModalItem] = useState(null)

  return (
    <Card
      title="Review queue (caller's team)"
      action={
        <button
          className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700"
          onClick={onLoad}
        >
          Load queue
        </button>
      }
    >
      {error ? (
        <div className="text-sm text-slate-500 py-2">Request failed: {error}</div>
      ) : items === null ? (
        <div className="text-sm text-slate-500 py-2">Nothing loaded yet.</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-slate-500 py-2">No queue items.</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-slate-500">
              <th className="py-1.5 pr-2">Item</th>
              <th className="py-1.5 pr-2">Document</th>
              <th className="py-1.5 pr-2">Status</th>
              <th className="py-1.5"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t border-slate-100">
                <td className="py-2 pr-2 font-mono text-xs">{item.id.slice(0, 8)}…</td>
                <td className="py-2 pr-2 font-mono text-xs">{item.lease_document_id.slice(0, 8)}…</td>
                <td className="py-2 pr-2">
                  <Badge status={item.status} />
                </td>
                <td className="py-2">
                  {item.status === 'PENDING' && (
                    <button
                      className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700"
                      onClick={() => setModalItem(item)}
                    >
                      Resolve
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modalItem && (
        <ResolveModal
          item={modalItem}
          onClose={() => setModalItem(null)}
          onSubmit={(body) => {
            onResolve(modalItem.id, body)
            setModalItem(null)
          }}
        />
      )}
    </Card>
  )
}
