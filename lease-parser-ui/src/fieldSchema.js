// Mirrors services/lease-abstraction/src/extraction/field_schemas.py — the
// fixed display order for the five in-scope lease terms (FR-002), and a
// formatter for the value shape each field type's schema guarantees, no
// matter which provider (Claude, OpenAI, or the fake seed) produced it.
export const CANONICAL_FIELD_ORDER = [
  'BASE_RENT', 'ESCALATION_SCHEDULE', 'FREE_RENT_PERIOD', 'TI_ALLOWANCE', 'TERM',
]

export const FIELD_TYPES = CANONICAL_FIELD_ORDER

const unit = (u) => (u || '').replaceAll('_', ' ').toLowerCase()

export function formatFieldValue(fieldType, value) {
  if (!value) return ''
  switch (fieldType) {
    case 'BASE_RENT':
    case 'TI_ALLOWANCE':
      return `$${value.amount} / ${unit(value.unit)}`
    case 'ESCALATION_SCHEDULE':
      return `${value.percent}% (${unit(value.frequency)})`
    case 'FREE_RENT_PERIOD':
      return `${value.months} month(s)`
    case 'TERM':
      return `${value.years} yr` +
        (value.commencement_date ? ` — ${value.commencement_date} to ${value.expiration_date || '?'}` : '')
    default:
      return JSON.stringify(value)
  }
}
