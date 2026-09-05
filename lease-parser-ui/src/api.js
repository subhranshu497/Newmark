// Thin fetch wrapper shared by every panel. Cross-origin by design — this
// frontend is a separate project from the lease-abstraction backend, so
// every call here needs the backend's CORS (enabled only when it's started
// with LEASE_ABSTRACTION_ENABLE_DEMO_UI=1 — see services/lease-abstraction/test.md).
export function createApiClient(apiBase, onLog) {
  return async function api(method, path, { headers = {}, body } = {}) {
    const url = apiBase.replace(/\/+$/, '') + path
    const opts = { method, headers: { ...headers } }
    if (body instanceof FormData) {
      opts.body = body // browser sets Content-Type (with multipart boundary) itself
    } else if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }

    let res
    let data = null
    try {
      res = await fetch(url, opts)
      try {
        data = await res.json()
      } catch {
        data = null
      }
    } catch (e) {
      onLog?.({ method, url, status: 0, data: { error: String(e) } })
      throw e
    }
    onLog?.({ method, url, status: res.status, data })
    return { status: res.status, ok: res.ok, data }
  }
}

export function identityHeaders({ userId, teamId, isAdmin }) {
  const headers = { 'X-User-Id': userId, 'X-Team-Id': teamId }
  if (isAdmin) headers['X-Is-Admin'] = 'true'
  return headers
}
