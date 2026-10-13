import { Session, DashboardData, DocumentRecord, ChatAnswer, AnswerFormat, AssetData, RcaData, AnalyticsData } from './types';

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
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      // Error body was not JSON; keep the status text.
    }
    throw new Error(detail || `HTTP ${res.status}`);
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
  chatQuery: (payload: { question: string, assetTag?: string, desiredFormat: AnswerFormat, history: { role: string; content: string }[] }) =>
    fetchApi<ChatAnswer>('/chat/query', { method: 'POST', body: JSON.stringify(payload) }),
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
