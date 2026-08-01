import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { exportRca, login, request, Session } from './api'
import type { AnalyticsData, AnswerFormat, AssetData, AssetRegistryEntry, AuditLogEntry, ChatAnswer, ConversationTurn, DashboardData, DocumentRecord, ExportFormat, HealthData, RcaData } from './types'

type View = 'dashboard' | 'documents' | 'assistant' | 'asset' | 'rca' | 'analytics' | 'registry' | 'audit'

const nav: { id: View; label: string; icon: string; adminOnly?: boolean }[] = [
  { id: 'dashboard', label: 'Command center', icon: '⌂' },
  { id: 'documents', label: 'Knowledge library', icon: '▤' },
  { id: 'assistant', label: 'AI copilot', icon: '✦' },
  { id: 'asset', label: 'Asset 360°', icon: '◎' },
  { id: 'rca', label: 'RCA intelligence', icon: '⌁' },
  { id: 'analytics', label: 'Trend analytics', icon: '▲' },
  { id: 'registry', label: 'Asset registry', icon: '▦' },
  { id: 'audit', label: 'Audit trail', icon: '⏱', adminOnly: true },
]

export default function App() {
  const [session, setSession] = useState<Session | null>(() => {
    const raw = localStorage.getItem('indusmind-session')
    return raw ? JSON.parse(raw) : null
  })
  const [view, setView] = useState<View>('dashboard')

  const logout = () => {
    localStorage.removeItem('indusmind-session')
    setSession(null)
  }

  useEffect(() => {
    const handleUnauthorized = () => logout()
    window.addEventListener('indusmind-unauthorized', handleUnauthorized)
    return () => window.removeEventListener('indusmind-unauthorized', handleUnauthorized)
  }, [])

  if (!session) return <Login onLogin={(value) => {
    localStorage.setItem('indusmind-session', JSON.stringify(value))
    setSession(value)
  }} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><span /></div>
          <div><strong>IndusMind</strong><small>Industrial intelligence</small></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {nav.filter(item => !item.adminOnly || session.role === 'ADMIN').map(item => (
            <button key={item.id} className={view === item.id ? 'active' : ''} onClick={() => setView(item.id)}>
              <span>{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="pulse" />
          <div><strong>Evidence-first AI</strong><small>Answers stay grounded in your documents.</small></div>
        </div>
        <div className="user-card">
          <div className="avatar">{session.displayName.charAt(0)}</div>
          <div><strong>{session.displayName}</strong><small>{session.role.toLowerCase()}</small></div>
          <button aria-label="Logout" onClick={logout}>↗</button>
        </div>
      </aside>
      <main>
        <TopBar session={session} view={view} />
        <div className="page">
          {view === 'dashboard' && <Dashboard token={session.token} navigate={setView} />}
          {view === 'documents' && <Documents token={session.token} isAdmin={session.role === 'ADMIN'} />}
          {view === 'assistant' && <Assistant token={session.token} />}
          {view === 'asset' && <AssetView token={session.token} />}
          {view === 'rca' && <RcaView token={session.token} />}
          {view === 'analytics' && <AnalyticsView token={session.token} />}
          {view === 'registry' && <RegistryView token={session.token} isAdmin={session.role === 'ADMIN'} />}
          {view === 'audit' && <AuditView token={session.token} />}
        </div>
      </main>
    </div>
  )
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('Admin@123')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try { onLogin(await login(username, password)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Login failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="login-page">
      <section className="login-story">
        <div className="story-brand"><div className="brand-mark"><span /></div>INDUSMIND AI</div>
        <div className="story-copy">
          <div className="eyebrow light">INDUSTRIAL KNOWLEDGE, CONNECTED</div>
          <h1>Every document.<br />One operational brain.</h1>
          <p>Turn maintenance records, inspections, manuals and safety procedures into evidence-backed decisions.</p>
          <div className="story-proof">
            <div><b>01</b><span>Ingest & extract</span></div>
            <div><b>02</b><span>Connect asset history</span></div>
            <div><b>03</b><span>Answer with evidence</span></div>
          </div>
        </div>
        <small>Synthetic demo environment · Engineering verification required</small>
      </section>
      <section className="login-panel">
        <form onSubmit={submit}>
          <div className="eyebrow">SECURE WORKSPACE</div>
          <h2>Welcome back</h2>
          <p>Sign in to your industrial knowledge command center.</p>
          <label>Username<input value={username} onChange={e => setUsername(e.target.value)} /></label>
          <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>
          {error && <div className="error">{error}</div>}
          <button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to workspace'} <span>→</span></button>
          <div className="demo-access">
            <b>Demo access</b>
            <button type="button" onClick={() => { setUsername('admin'); setPassword('Admin@123') }}>Admin</button>
            <button type="button" onClick={() => { setUsername('engineer'); setPassword('Engineer@123') }}>Engineer</button>
          </div>
        </form>
      </section>
    </div>
  )
}

function TopBar({ session, view }: { session: Session; view: View }) {
  const label = nav.find(item => item.id === view)?.label
  return (
    <header className="topbar">
      <div><span>IndusMind AI</span><i>/</i><strong>{label}</strong></div>
      <div className="top-actions"><span className="status-chip"><i /> System ready</span><span>{new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span><b>{session.username}</b></div>
    </header>
  )
}

function Dashboard({ token, navigate }: { token: string; navigate: (view: View) => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => request<DashboardData>('/dashboard', {}, token).then(setData).catch(e => setError(e.message)), [token])
  useEffect(() => { load() }, [load])
  const cards = [
    ['Indexed documents', data?.documents ?? '—', `${data?.readyDocuments ?? 0} ready`, '▤'],
    ['Connected assets', data?.assets ?? '—', 'Across the corpus', '◎'],
    ['Knowledge queries', data?.queries ?? '—', 'Evidence-backed', '✦'],
    ['AI service', data?.aiOnline ? 'Online' : 'Offline', data?.aiOnline ? 'Ready to answer' : 'Start FastAPI', '◉'],
  ]
  return (
    <>
      <Hero eyebrow="OPERATIONAL OVERVIEW" title="Your knowledge, in command." subtitle="A live view of industrial evidence, connected assets and decision intelligence." actions={<>
        <button className="secondary" onClick={() => navigate('documents')}>Upload evidence</button>
        <button className="primary" onClick={() => navigate('assistant')}>Ask IndusMind <span>→</span></button>
      </>} />
      {error && <Notice text={error} />}
      <div className="metric-grid">{cards.map(card => <div className="metric" key={card[0]}><div className="metric-icon">{card[3]}</div><span>{card[0]}</span><strong>{card[1]}</strong><small>{card[2]}</small></div>)}</div>
      <div className="content-grid">
        <section className="panel wide">
          <PanelHead title="Asset intelligence" subtitle="Equipment discovered across indexed documents" />
          <div className="asset-strip">
            {data?.assetTags?.length ? data.assetTags.map((tag, index) => (
              <button key={tag} onClick={() => navigate('asset')}>
                <span className={`asset-orb orb-${index % 3}`}>{tag.charAt(0)}</span>
                <span><b>{tag}</b><small>Indexed asset</small></span>
                <i>→</i>
              </button>
            )) : <div className="empty"><span>◎</span><b>No assets yet</b><small>Upload documents to discover asset tags.</small></div>}
          </div>
          {!!data?.assetTags?.length && <div className="pattern-callout">
            <div className="signal">⌁</div><div><b>Investigate any asset</b><p>Open a tag in Asset 360° for its full evidence trail, or ask the copilot a question and IndusMind will connect the records for you.</p></div>
            <button onClick={() => navigate('rca')}>Investigate →</button>
          </div>}
        </section>
        <section className="panel">
          <PanelHead title="Recent questions" subtitle="Latest knowledge activity" />
          <div className="recent-list">
            {data?.recentQueries?.length ? data.recentQueries.map(q => <div key={q.id}><span>?</span><div><b>{q.question}</b><small>{q.mode} · {Math.round(q.confidence * 100)}% confidence</small></div></div>) :
              <div className="empty"><span>✦</span><b>No questions yet</b><small>Ask the copilot about your indexed equipment.</small></div>}
          </div>
        </section>
      </div>
    </>
  )
}

function Documents({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [formats, setFormats] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const pollRef = useRef<number | null>(null)
  const load = useCallback(() => request<DocumentRecord[]>('/documents', {}, token).then(setDocuments).catch(e => setMessage(e.message)), [token])
  useEffect(() => { load() }, [load])
  useEffect(() => { request<HealthData>('/health', {}, token).then(h => setFormats(h.supportedFormats ?? [])).catch(() => {}) }, [token])
  // Uploads are processed asynchronously in the background (OCR/transcription
  // can take a while), so poll while anything is still queued/processing and
  // stop once everything has settled into READY or FAILED.
  useEffect(() => {
    const active = documents.some(d => d.status === 'QUEUED' || d.status === 'PROCESSING')
    if (active && pollRef.current === null) {
      pollRef.current = window.setInterval(load, 3000)
    } else if (!active && pollRef.current !== null) {
      window.clearInterval(pollRef.current); pollRef.current = null
    }
    return () => { if (pollRef.current !== null) { window.clearInterval(pollRef.current); pollRef.current = null } }
  }, [documents, load])
  const upload = async (file?: File) => {
    if (!file) return
    setBusy(true); setMessage('Uploading…')
    const body = new FormData(); body.append('file', file)
    try {
      await request('/documents', { method: 'POST', body }, token)
      setMessage(`${file.name} was queued for processing.`); load()
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Upload failed') }
    finally { setBusy(false) }
  }
  const remove = async (doc: DocumentRecord) => {
    if (!window.confirm(`Remove "${doc.originalName}" and its indexed evidence? This can't be undone.`)) return
    try { await request(`/documents/${doc.id}`, { method: 'DELETE' }, token); load() }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Delete failed') }
  }
  const formatSummary = formats.length ? formats.join(', ') : 'PDF, DOCX, XLSX, PPTX, CSV, TXT, JSON, XML, HTML, RTF, EML, images (OCR)…'
  const visible = documents.filter(doc => {
    const needle = query.trim().toLowerCase()
    if (!needle) return true
    return [doc.originalName, doc.documentType, doc.assetTags, doc.status].some(field => field?.toLowerCase().includes(needle))
  })
  return (
    <>
      <Hero eyebrow="KNOWLEDGE INGESTION" title="Build the evidence layer." subtitle="Upload maintenance records, inspections, manuals, SOPs, spreadsheets, scans, photos and more - any format the AI service can read." />
      <section className={`upload-zone ${!isAdmin ? 'disabled' : ''}`}>
        <div className="upload-symbol">⇧</div><div><h3>{busy ? 'Uploading…' : 'Drop industrial documents here'}</h3><p>Supported: {formatSummary}</p></div>
        <label className="primary">{isAdmin ? 'Choose files' : 'Admin access required'}<input type="file" accept={formats.length ? formats.join(',') : undefined} disabled={!isAdmin || busy} onChange={e => upload(e.target.files?.[0])} /></label>
      </section>
      {message && <Notice text={message} />}
      <section className="panel">
        <PanelHead title="Document library" subtitle={`${documents.length} records in the workspace`} />
        <input className="filter-input" placeholder="Search by name, type, asset tag or status…" value={query} onChange={e => setQuery(e.target.value)} />
        <div className="document-table">
          <div className="table-row table-head"><span>Document</span><span>Type</span><span>Assets</span><span>Status</span><span>Uploaded</span><span></span></div>
          {visible.map(doc => <div className="table-row" key={doc.id}>
            <span className="doc-name"><i>▤</i><span><b>{doc.originalName}</b><small>{formatBytes(doc.sizeBytes)} · {doc.summary || doc.errorMessage || 'Waiting to be processed'}{doc.uploadedBy ? ` · ${doc.uploadedBy}` : ''}</small></span></span>
            <span>{doc.documentType || '—'}</span><span><b>{doc.assetTags || '—'}</b></span>
            <span><em className={`state ${doc.status.toLowerCase()}`}>{doc.status}</em></span><span>{new Date(doc.uploadedAt).toLocaleDateString()}</span>
            <span>{isAdmin && <button className="row-action danger" onClick={() => remove(doc)} title="Delete">✕</button>}</span>
          </div>)}
          {!visible.length && <div className="empty table-empty"><span>▤</span><b>{documents.length ? 'No documents match your search' : 'The library is empty'}</b><small>{documents.length ? 'Try a different search term.' : 'Upload the provided synthetic files to begin.'}</small></div>}
        </div>
      </section>
    </>
  )
}

const FORMAT_OPTIONS: { value: AnswerFormat; label: string }[] = [
  { value: 'quick_answer', label: 'Quick answer' },
  { value: 'work_order', label: 'Work order' },
  { value: 'checklist', label: 'Checklist' },
  { value: 'table', label: 'Table' },
  { value: 'report', label: 'Report' },
]

type Exchange = { question: string; answer: ChatAnswer }

function Assistant({ token }: { token: string }) {
  const [question, setQuestion] = useState('Why did Pump P-101 fail repeatedly in 2025?')
  const [assetTag, setAssetTag] = useState('')
  const [format, setFormat] = useState<AnswerFormat>('quick_answer')
  const [assetTags, setAssetTags] = useState<string[]>([])
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { request<DashboardData>('/dashboard', {}, token).then(d => setAssetTags(d.assetTags ?? [])).catch(() => {}) }, [token])
  const ask = async (text = question) => {
    setBusy(true); setError(''); setQuestion(text)
    try {
      // Only the last few turns are sent - enough for "what about last month?"
      // style follow-ups without letting the prompt grow unbounded.
      const history: ConversationTurn[] = exchanges.slice(-3).map(e => ({ question: e.question, answer: e.answer.answer }))
      const answer = await request<ChatAnswer>('/chat/query', {
        method: 'POST',
        body: JSON.stringify({ question: text, assetTag, desiredFormat: format, history }),
      }, token)
      setExchanges(prev => [...prev, { question: text, answer }])
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Question failed') }
    finally { setBusy(false) }
  }
  const giveFeedback = async (exchange: Exchange, value: 1 | -1) => {
    if (!exchange.answer.queryId) return
    const next = value === exchange.answer.feedback ? undefined : value
    setExchanges(prev => prev.map(e => e === exchange ? { ...e, answer: { ...e.answer, feedback: next } } : e))
    try { await request(`/chat/${exchange.answer.queryId}/feedback`, { method: 'PATCH', body: JSON.stringify({ feedback: next ?? null }) }, token) }
    catch { /* feedback is a nice-to-have signal, not worth blocking the UI over */ }
  }
  const latest = exchanges[exchanges.length - 1]
  return (
    <>
      <Hero eyebrow="EVIDENCE-BACKED COPILOT" title="Ask the operation." subtitle="Natural-language answers grounded in your industrial document corpus." actions={exchanges.length ? <button className="secondary" onClick={() => setExchanges([])}>New conversation</button> : undefined} />
      <div className="assistant-layout">
        <section className="chat-panel">
          <div className="suggestions">
            {['What maintenance was performed on P-101?', 'What safety steps apply before pump maintenance?', 'Which readings exceeded OEM limits?'].map(text =>
              <button key={text} onClick={() => ask(text)}>{text}</button>)}
          </div>
          <div className="conversation">
            {!exchanges.length && !busy && <div className="chat-welcome"><div className="ai-orb">✦</div><h3>What do you need to know?</h3><p>I’ll search the indexed records, connect evidence across files and show exactly where the answer came from.</p></div>}
            {exchanges.map((exchange, index) => <div key={index}>
              <div className="user-message">{exchange.question}</div>
              <div className="ai-answer">
                <div className="answer-head"><span className="ai-orb small">✦</span><b>IndusMind answer</b><em>{Math.round(exchange.answer.confidence * 100)}% confidence</em></div>
                <p className={exchange.answer.format === 'quick_answer' ? '' : 'answer-structured'}>{exchange.answer.answer}</p>
                <div className="answer-foot">
                  <small>Mode: {exchange.answer.mode} · Format: {FORMAT_OPTIONS.find(f => f.value === exchange.answer.format)?.label ?? exchange.answer.format}</small>
                  <div className="feedback">
                    <button className={exchange.answer.feedback === 1 ? 'active' : ''} onClick={() => giveFeedback(exchange, 1)} aria-label="Helpful">👍</button>
                    <button className={exchange.answer.feedback === -1 ? 'active' : ''} onClick={() => giveFeedback(exchange, -1)} aria-label="Not helpful">👎</button>
                  </div>
                </div>
              </div>
            </div>)}
            {busy && <div className="thinking"><span /><span /><span /> Retrieving relevant evidence…</div>}
            {error && <Notice text={error} />}
          </div>
          <form className="ask-box" onSubmit={e => { e.preventDefault(); ask() }}>
            <textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about an asset, procedure, incident or operating condition…" />
            <div className="ask-controls">
              <label>Asset scope
                <select value={assetTag} onChange={e => setAssetTag(e.target.value)}>
                  <option value="">All assets</option>
                  {assetTags.map(tag => <option key={tag} value={tag}>{tag}</option>)}
                </select>
              </label>
              <label>Answer as
                <select value={format} onChange={e => setFormat(e.target.value as AnswerFormat)}>
                  {FORMAT_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </label>
              <button className="primary" disabled={busy}>Ask <i>→</i></button>
            </div>
          </form>
        </section>
        <aside className="evidence-panel">
          <PanelHead title="Source evidence" subtitle={latest ? `${latest.answer.citations.length} passages retrieved` : 'Citations appear with every answer'} />
          {latest?.answer.citations.map((citation, index) => <article className="citation" key={`${citation.source}-${index}`}>
            <div><span>{index + 1}</span><b>{citation.source}</b></div>
            <small>Page {citation.page} · {citation.documentType || 'Industrial record'} · {Math.round((citation.relevance || 0) * 100)}% match</small>
            <p>{citation.excerpt}</p>
          </article>)}
          {!latest && <div className="empty"><span>⌕</span><b>Waiting for a question</b><small>Every answer includes traceable source passages.</small></div>}
        </aside>
      </div>
    </>
  )
}

function AssetView({ token }: { token: string }) {
  const [tag, setTag] = useState('P-101')
  const [asset, setAsset] = useState<AssetData | null>(null)
  const [error, setError] = useState('')
  const load = async () => {
    setError('')
    try { setAsset(await request<AssetData>(`/assets/${encodeURIComponent(tag)}`, {}, token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Asset not found') }
  }
  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <Hero eyebrow="CONNECTED ASSET HISTORY" title="Asset 360°" subtitle="One evidence-backed view of maintenance, inspection, operating data and failure context." actions={<div className="asset-search"><input value={tag} onChange={e => setTag(e.target.value.toUpperCase())} /><button className="primary" onClick={load}>Load asset</button></div>} />
      {error && <Notice text={error} />}
      {asset && <>
        <div className="asset-hero">
          <div className="big-orb">{asset.tag.charAt(0)}</div><div><span>INDEXED ASSET</span><h2>{asset.tag}</h2><p>Indexed from {asset.sources.length} source document{asset.sources.length === 1 ? '' : 's'}.</p></div>
          <div className="asset-stat"><b>{asset.evidenceChunks}</b><span>Evidence chunks</span></div><div className="asset-stat"><b>{asset.sources.length}</b><span>Source documents</span></div>
        </div>
        <div className="asset-columns">
          <section className="panel">
            <PanelHead title="Failure signals" subtitle="Patterns extracted from source records" />
            <div className="tag-list">{asset.failures.map(x => <span className="risk-tag" key={x}>{x}</span>)}</div>
            <h4>Observed measurements</h4><div className="measurement-grid">{asset.measurements.slice(0, 8).map(x => <span key={x}>{x}</span>)}</div>
          </section>
          <section className="panel">
            <PanelHead title="Maintenance timeline" subtitle="Cross-document event trail" />
            <div className="timeline">{asset.timeline.length ? asset.timeline.map((event, i) => <div key={i}><i /><span><b>{event.date}</b><small>{event.source}</small><p>{event.summary}</p></span></div>) : <div className="empty"><small>No dated events extracted.</small></div>}</div>
          </section>
        </div>
      </>}
    </>
  )
}

function RcaView({ token }: { token: string }) {
  const [tag, setTag] = useState('P-101')
  const [data, setData] = useState<RcaData | null>(null)
  const [busy, setBusy] = useState(false)
  const [exporting, setExporting] = useState<ExportFormat | ''>('')
  const [error, setError] = useState('')
  const generate = async () => {
    setBusy(true); setError('')
    try { setData(await request<RcaData>(`/assets/${encodeURIComponent(tag)}/rca`, { method: 'POST' }, token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'RCA failed') }
    finally { setBusy(false) }
  }
  const download = async (format: ExportFormat) => {
    setExporting(format); setError('')
    try { await exportRca(data?.assetTag ?? tag, format, token) }
    catch (e) { setError(e instanceof Error ? e.message : 'Export failed') }
    finally { setExporting('') }
  }
  return (
    <>
      <Hero eyebrow="ROOT CAUSE SUPPORT" title="Turn history into action." subtitle="Connect recurring failures, interventions and operating conditions into a traceable investigation brief."
        actions={<div className="asset-search">
          <input value={tag} onChange={e => setTag(e.target.value.toUpperCase())} placeholder="Asset tag, e.g. P-101" />
          <button className="primary" onClick={generate} disabled={busy}>{busy ? 'Analysing evidence…' : `Generate ${tag || 'asset'} RCA`} <span>→</span></button>
        </div>} />
      {error && <Notice text={error} />}
      {!data && <section className="rca-intro"><div className="rca-graphic"><span>{tag || 'ASSET'}</span><i /><b>Evidence</b><i /><b>Patterns</b><i /><strong>RCA</strong></div><h3>Evidence before inference.</h3><p>IndusMind builds a decision-support brief from uploaded records. It separates observed evidence from probable causes and always preserves the source trail.</p></section>}
      {data && <div className="rca-report">
        <div className="rca-header">
          <div><span>RCA BRIEF</span><h2>{data.assetTag}</h2><p>{data.observedProblem}</p></div>
          <div className="confidence-ring"><b>{Math.round(data.confidence * 100)}%</b><span>evidence confidence</span></div>
        </div>
        <div className="rca-grid">
          <RcaBlock number="01" title="Probable contributors" items={data.probableCauses} tone="risk" />
          <RcaBlock number="02" title="Recommended investigation" items={data.recommendedInvestigation} tone="warn" />
          <RcaBlock number="03" title="Preventive actions" items={data.preventiveActions} tone="good" />
        </div>
        <div className="rca-evidence"><b>Source trail</b>{data.citations.map((x, i) => <span key={i}>{x.source} · p.{x.page}</span>)}</div>
        <div className="rca-export">
          <b>Export this report</b>
          {(['docx', 'pdf', 'csv'] as ExportFormat[]).map(format =>
            <button key={format} onClick={() => download(format)} disabled={exporting !== ''}>
              {exporting === format ? 'Preparing…' : `Download .${format}`}
            </button>)}
        </div>
        <p className="disclaimer">{data.disclaimer}</p>
      </div>}
    </>
  )
}

function RcaBlock({ number, title, items, tone }: { number: string; title: string; items: string[]; tone: string }) {
  return <section className={`rca-block ${tone}`}><span>{number}</span><h3>{title}</h3><ul>{items.map(item => <li key={item}>{item}</li>)}</ul></section>
}

function AnalyticsView({ token }: { token: string }) {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { request<AnalyticsData>('/analytics', {}, token).then(setData).catch(e => setError(e.message)) }, [token])
  const maxFailure = Math.max(1, ...(data?.topFailureModes.map(f => f.count) ?? [1]))
  return (
    <>
      <Hero eyebrow="TREND INTELLIGENCE" title="What keeps recurring." subtitle="Failure and action frequency computed live from everything currently indexed." />
      {error && <Notice text={error} />}
      {data && <div className="content-grid">
        <section className="panel wide">
          <PanelHead title="Top failure modes" subtitle={`Across ${data.totalAssets} asset(s), ${data.totalChunks} evidence chunks`} />
          <div className="bar-list">
            {data.topFailureModes.length ? data.topFailureModes.map(f => (
              <div className="bar-row" key={f.failure}>
                <span className="bar-label">{f.failure}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${(f.count / maxFailure) * 100}%` }} /></div>
                <b>{f.count}</b>
              </div>
            )) : <div className="empty"><small>No failure terms extracted yet.</small></div>}
          </div>
        </section>
        <section className="panel">
          <PanelHead title="Assets ranked by risk" subtitle="Most failure events first" />
          <div className="recent-list">
            {data.assetsRankedByRisk.length ? data.assetsRankedByRisk.map(a => (
              <div key={a.assetTag}><span>◎</span><div><b>{a.assetTag}</b><small>{a.failureEvents} failure events · top: {a.topFailure ?? '—'} · {a.documentCount} doc(s)</small></div></div>
            )) : <div className="empty"><small>No assets indexed yet.</small></div>}
          </div>
        </section>
        <section className="panel wide">
          <PanelHead title="Most recorded actions" subtitle="What engineers have been doing about it" />
          <div className="tag-list">{data.topActions.map(a => <span className="risk-tag good" key={a.action}>{a.action} · {a.count}</span>)}</div>
          {!data.topActions.length && <div className="empty"><small>No maintenance actions extracted yet.</small></div>}
        </section>
      </div>}
    </>
  )
}

function RegistryView({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const empty = { tag: '', name: '', location: '', criticality: 'MEDIUM', manufacturer: '', installDate: '', notes: '' }
  const [assets, setAssets] = useState<AssetRegistryEntry[]>([])
  const [form, setForm] = useState(empty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => request<AssetRegistryEntry[]>('/registry/assets', {}, token).then(setAssets).catch(e => setError(e.message)), [token])
  useEffect(() => { load() }, [load])
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try {
      if (editingId) await request(`/registry/assets/${editingId}`, { method: 'PUT', body: JSON.stringify(form) }, token)
      else await request('/registry/assets', { method: 'POST', body: JSON.stringify(form) }, token)
      setForm(empty); setEditingId(null); load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Save failed') }
  }
  const edit = (asset: AssetRegistryEntry) => {
    setEditingId(asset.id)
    setForm({ tag: asset.tag, name: asset.name ?? '', location: asset.location ?? '', criticality: asset.criticality ?? 'MEDIUM', manufacturer: asset.manufacturer ?? '', installDate: asset.installDate ?? '', notes: asset.notes ?? '' })
  }
  const remove = async (asset: AssetRegistryEntry) => {
    if (!window.confirm(`Remove ${asset.tag} from the registry?`)) return
    try { await request(`/registry/assets/${asset.id}`, { method: 'DELETE' }, token); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Delete failed') }
  }
  return (
    <>
      <Hero eyebrow="STRUCTURED METADATA" title="Register what you operate." subtitle="Give assets real identity - location, criticality, manufacturer - beyond what's inferred from document text." />
      {error && <Notice text={error} />}
      <div className="content-grid">
        {isAdmin && <section className="panel">
          <PanelHead title={editingId ? `Edit ${form.tag}` : 'Register a new asset'} subtitle="Visible to every engineer" />
          <form className="registry-form" onSubmit={submit}>
            <label>Asset tag<input required value={form.tag} disabled={!!editingId} onChange={e => setForm({ ...form, tag: e.target.value.toUpperCase() })} placeholder="P-101" /></label>
            <label>Name<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Boiler feed pump" /></label>
            <label>Location<input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="Section A" /></label>
            <label>Criticality
              <select value={form.criticality} onChange={e => setForm({ ...form, criticality: e.target.value })}>
                {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label>Manufacturer<input value={form.manufacturer} onChange={e => setForm({ ...form, manufacturer: e.target.value })} /></label>
            <label>Install date<input type="date" value={form.installDate} onChange={e => setForm({ ...form, installDate: e.target.value })} /></label>
            <label>Notes<textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></label>
            <div className="registry-form-actions">
              <button className="primary" type="submit">{editingId ? 'Save changes' : 'Register asset'}</button>
              {editingId && <button type="button" onClick={() => { setEditingId(null); setForm(empty) }}>Cancel</button>}
            </div>
          </form>
        </section>}
        <section className={`panel ${isAdmin ? '' : 'wide'}`}>
          <PanelHead title="Registered assets" subtitle={`${assets.length} in the registry`} />
          <div className="document-table">
            <div className="table-row table-head"><span>Tag</span><span>Name</span><span>Location</span><span>Criticality</span><span></span></div>
            {assets.map(asset => <div className="table-row" key={asset.id}>
              <span><b>{asset.tag}</b></span><span>{asset.name || '—'}</span><span>{asset.location || '—'}</span>
              <span><em className={`state ${(asset.criticality || '').toLowerCase()}`}>{asset.criticality || '—'}</em></span>
              <span>{isAdmin && <><button className="row-action" onClick={() => edit(asset)}>Edit</button><button className="row-action danger" onClick={() => remove(asset)}>✕</button></>}</span>
            </div>)}
            {!assets.length && <div className="empty table-empty"><span>▦</span><b>No assets registered yet</b><small>{isAdmin ? 'Use the form to register your first asset.' : 'Ask an admin to register assets here.'}</small></div>}
          </div>
        </section>
      </div>
    </>
  )
}

function AuditView({ token }: { token: string }) {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [error, setError] = useState('')
  useEffect(() => { request<AuditLogEntry[]>('/audit', {}, token).then(setLogs).catch(e => setError(e.message)) }, [token])
  return (
    <>
      <Hero eyebrow="ACCOUNTABILITY" title="Who did what, when." subtitle="Every login, upload, deletion, and RCA export, in order." />
      {error && <Notice text={error} />}
      <section className="panel">
        <PanelHead title="Recent activity" subtitle={`${logs.length} events`} />
        <div className="document-table">
          <div className="table-row table-head"><span>When</span><span>Actor</span><span>Action</span><span>Target</span><span>Detail</span></div>
          {logs.map(log => <div className="table-row" key={log.id}>
            <span>{new Date(log.createdAt).toLocaleString()}</span><span><b>{log.actor}</b></span>
            <span>{log.action.replaceAll('_', ' ').toLowerCase()}</span>
            <span>{log.targetType ? `${log.targetType}:${log.targetId}` : '—'}</span>
            <span className="audit-detail">{log.detail || '—'}</span>
          </div>)}
          {!logs.length && <div className="empty table-empty"><span>⏱</span><b>No activity recorded yet</b><small>Actions will appear here as the workspace is used.</small></div>}
        </div>
      </section>
    </>
  )
}

function Hero({ eyebrow, title, subtitle, actions }: { eyebrow: string; title: string; subtitle: string; actions?: React.ReactNode }) {
  return <div className="page-hero"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{actions && <div className="hero-actions">{actions}</div>}</div>
}
function PanelHead({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="panel-head"><div><h3>{title}</h3><p>{subtitle}</p></div><span>•••</span></div>
}
function Notice({ text }: { text: string }) { return <div className="notice">ⓘ {text}</div> }
function formatBytes(bytes: number) { return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB` }
