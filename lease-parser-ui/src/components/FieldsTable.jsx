import { useState } from 'react'
import Card from './Card.jsx'
import Badge from './Badge.jsx'
import Modal from './Modal.jsx'
import { CANONICAL_FIELD_ORDER, formatFieldValue } from '../fieldSchema.js'

function VerifyModal({ field, onClose, onSubmit }) {
  const [override, setOverride] = useState('')
  const [error, setError] = useState('')

  const submit = () => {
    if (!override.trim()) {
      onSubmit(null)
      return
    }
    try {
      onSubmit(JSON.parse(override))
    } catch {
      setError('Invalid JSON')
    }
  }

  return (
    <Modal title={`Verify ${field.field_type}`} onClose={onClose}>
      <p className="text-sm text-slate-500 mb-2">
        Confirm the extracted value as-is, or provide an override value as JSON.
      </p>
      <textarea
        className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono mb-1"
        rows={3}
        placeholder={JSON.stringify(field.extracted_value)}
        value={override}
        onChange={(e) => { setOverride(e.target.value); setError('') }}
      />
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      <div className="flex justify-end gap-2 mt-3">
        <button className="px-3 py-1.5 text-sm rounded-md bg-slate-100 hover:bg-slate-200" onClick={onClose}>
          Cancel
        </button>
        <button className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700" onClick={submit}>
          {override.trim() ? 'Override & verify' : 'Confirm as-is'}
        </button>
      </div>
    </Modal>
  )
}

export default function FieldsTable({ fields, documentId, error, onLoad, onVerify }) {
  const [modalField, setModalField] = useState(null)

  const header = (
    <button
      className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700"
      onClick={onLoad}
    >
      Load fields
    </button>
  )

  if (!documentId) {
    return (
      <Card title="Extracted fields" action={header}>
        <div className="text-sm text-slate-500 py-2">Upload or seed a record first.</div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card title="Extracted fields" action={header}>
        <div className="text-sm text-slate-500 py-2">Request failed: {error}</div>
      </Card>
    )
  }

  const byType = Object.fromEntries(fields.map((f) => [f.field_type, f]))

  return (
    <Card title="Extracted fields" action={header}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase text-slate-500">
            <th className="py-1.5 pr-2">Field</th>
            <th className="py-1.5 pr-2">Value</th>
            <th className="py-1.5 pr-2">Confidence</th>
            <th className="py-1.5 pr-2">Status</th>
            <th className="py-1.5"></th>
          </tr>
        </thead>
        <tbody>
          {CANONICAL_FIELD_ORDER.map((fieldType) => {
            const f = byType[fieldType]
            if (!f) {
              return (
                <tr key={fieldType} className="border-t border-slate-100">
                  <td className="py-2 pr-2 text-slate-700">{fieldType}</td>
                  <td className="py-2 text-slate-400" colSpan={4}>
                    not extracted from this document
                  </td>
                </tr>
              )
            }
            return (
              <tr key={fieldType} className="border-t border-slate-100 align-top">
                <td className="py-2 pr-2 text-slate-700">{f.field_type}</td>
                <td
                  className="py-2 pr-2 font-mono text-xs"
                  title={JSON.stringify(f.extracted_value)}
                >
                  {formatFieldValue(f.field_type, f.extracted_value)}
                </td>
                <td className="py-2 pr-2">{f.confidence_score}</td>
                <td className="py-2 pr-2">
                  <Badge status={f.verification_status} />
                </td>
                <td className="py-2">
                  {f.verification_status === 'UNVERIFIED' ? (
                    <button
                      className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white hover:bg-blue-700"
                      onClick={() => setModalField(f)}
                    >
                      Verify
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400 font-mono">{f.verified_by || ''}</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {modalField && (
        <VerifyModal
          field={modalField}
          onClose={() => setModalField(null)}
          onSubmit={(value) => {
            onVerify(modalField.id, value)
            setModalField(null)
          }}
        />
      )}
    </Card>
  )
}
