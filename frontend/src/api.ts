const API = '/api'

export type Session = {
  token: string
  username: string
  displayName: string
  role: 'ADMIN' | 'ENGINEER'
}

export async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if ((response.status === 401 || response.status === 403) && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event('indusmind-unauthorized'))
    }
    throw new Error(data.message || `Request failed (${response.status})`)
  }
  return data as T
}

export function login(username: string, password: string) {
  return request<Session>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function exportRca(tag: string, format: 'docx' | 'pdf' | 'csv', token: string): Promise<void> {
  const response = await fetch(`${API}/assets/${encodeURIComponent(tag)}/rca/export?format=${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const message = await response.text().catch(() => '')
    throw new Error(message || `Export failed (${response.status})`)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `RCA-${tag.toUpperCase()}.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

