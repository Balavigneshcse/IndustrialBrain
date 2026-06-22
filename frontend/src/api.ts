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
  if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`)
  return data as T
}

export function login(username: string, password: string) {
  return request<Session>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

