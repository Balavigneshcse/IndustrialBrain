import { Session, DashboardData, DocumentRecord, ChatAnswer, AnswerFormat, AssetData, RcaData, AnalyticsData, StreamHandlers } from './types';

const API_BASE = '/api';

let refreshing: Promise<boolean> | null = null;

// Access tokens live 15 minutes; the httpOnly refresh cookie gets a new one. Concurrent 401s share
// one refresh call, because each refresh rotates the cookie.
function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
    .then(async res => {
      if (!res.ok) return false;
      const session = await res.json();
      localStorage.setItem('token', session.token);
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

async function errorDetail(res: Response): Promise<string> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
  } catch {
    // Error body was not JSON; keep the status text.
  }
  return detail || `HTTP ${res.status}`;
}

type ChatPayload = { question: string, assetTag?: string, desiredFormat: AnswerFormat, history: { role: string; content: string }[] };

// POST /chat/stream answers with Server-Sent Events (status, sources, token..., done | error).
// Aborting `signal` closes the connection, which stops generation on the server.
async function chatStream(payload: ChatPayload, handlers: StreamHandlers, signal: AbortSignal): Promise<ChatAnswer> {
  const send = () => fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('token') ?? ''}` },
    body: JSON.stringify(payload),
  });
  let res = await send();
  if (res.status === 401 && localStorage.getItem('token') && await refreshSession()) res = await send();
  if (!res.ok || !res.body) throw new Error(await errorDetail(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end: number;
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = 'message';
      const data: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7);
        else if (line.startsWith('data: ')) data.push(line.slice(6));
      }
      if (data.length === 0) continue;
      const body = JSON.parse(data.join('\n'));
      if (event === 'status') handlers.onStatus?.(body.stage, body.position);
      else if (event === 'sources') handlers.onSources?.(body.citations);
      else if (event === 'token') handlers.onToken?.(body.text);
      else if (event === 'done') return body as ChatAnswer;
      else if (event === 'error') throw new Error(body.detail || body.title);
    }
  }
  throw new Error('The answer stream ended unexpectedly');
}

async function fetchApi<T>(endpoint: string, options: RequestInit = {}, retried = false): Promise<T> {
  const isFormData = options.body instanceof FormData;

  const headers: Record<string, string> = {};
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!isFormData) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string>) }
  });

  if (res.status === 401 && token && !retried && await refreshSession()) {
    return fetchApi<T>(endpoint, options, true);
  }

  if (!res.ok) {
    // Session could not be refreshed: drop it and go back to the login screen.
    if (res.status === 401 && token) {
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      window.location.reload();
    }
    throw new Error(await errorDetail(res));
  }

  // Handle binary download
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/vnd.openxmlformats-officedocument.wordprocessingml.document')) {
    return res.blob() as Promise<T>;
  }

  return res.json();
}

export const api = {
  login: (credentials: { username: string; password: string }) =>
    fetchApi<Session>('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  getDashboard: () => fetchApi<DashboardData>('/dashboard'),
  uploadDocument: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return fetchApi<DocumentRecord>('/documents/upload', { method: 'POST', body: formData });
  },
  getDocuments: () => fetchApi<DocumentRecord[]>('/documents'),
  deleteDocument: (id: string) => fetchApi<{ ok: boolean }>(`/documents/${id}`, { method: 'DELETE' }),
  chatQuery: (payload: ChatPayload) =>
    fetchApi<ChatAnswer>('/chat/query', { method: 'POST', body: JSON.stringify(payload) }),
  chatStream,
  chatFeedback: (id: number, feedback: 1 | -1 | null) =>
    fetchApi<{ ok: boolean }>(`/chat/${id}/feedback`, { method: 'PATCH', body: JSON.stringify({ feedback }) }),
  getAsset: (tag: string) => fetchApi<AssetData>(`/assets/${encodeURIComponent(tag)}`),
  generateRca: (tag: string) => fetchApi<RcaData>(`/rca/${encodeURIComponent(tag)}`, { method: 'POST' }),
  exportRca: async (tag: string) => {
    const blob = await fetchApi<Blob>(`/rca/export/${encodeURIComponent(tag)}`);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `RCA_${tag}.docx`;
    a.click();
    window.URL.revokeObjectURL(url);
  },
  getAnalytics: () => fetchApi<AnalyticsData>('/analytics')
};
