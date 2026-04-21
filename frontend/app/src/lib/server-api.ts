const API_URL = process.env.KIRA_HQ_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3100'

function getAuthorizationHeader() {
  const username = process.env.KIRA_HQ_USER
  const password = process.env.KIRA_HQ_PASS

  if (!username || !password) return null

  return `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}`
}

function buildHeaders(init?: HeadersInit) {
  const headers = new Headers(init)
  const authorization = getAuthorizationHeader()

  if (authorization) {
    headers.set('authorization', authorization)
  }

  return headers
}

export async function proxyToBackend(path: string, init?: RequestInit) {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: 'no-store',
    headers: buildHeaders(init?.headers),
  })

  const body = await response.text()
  const contentType = response.headers.get('content-type') ?? 'application/json'

  return new Response(body, {
    status: response.status,
    headers: {
      'content-type': contentType,
    },
  })
}
