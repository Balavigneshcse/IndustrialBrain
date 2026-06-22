import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { login, request, Session } from './api'
import type { AssetData, ChatAnswer, DashboardData, DocumentRecord, RcaData } from './types'

type View = 'dashboard' | 'documents' | 'assistant' | 'asset' | 'rca'

const nav: { id: View; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Command center', icon: '⌂' },
  { id: 'documents', label: 'Knowledge library', icon: '▤' },
  { id: 'assistant', label: 'AI copilot', icon: '✦' },
  { id: 'asset', label: 'Asset 360°', icon: '◎' },
  { id: 'rca', label: 'RCA intelligence', icon: '⌁' },
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
          {nav.map(item => (
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
            {(data?.assetTags?.length ? data.assetTags : ['P-101', 'C-201']).map((tag, index) => (
              <button key={tag} onClick={() => navigate('asset')}>
                <span className={`asset-orb orb-${index % 3}`}>{index === 0 ? 'P' : 'C'}</span>
                <span><b>{tag}</b><small>{index === 0 ? 'Centrifugal pump' : 'Process equipment'}</small></span>
                <i>→</i>
              </button>
            ))}
          </div>
          <div className="pattern-callout">
            <div className="signal">⌁</div><div><b>Recurring pattern detected</b><p>P-101 records connect bearing wear with lubricant contamination, misalignment, high vibration and temperature.</p></div>
            <button onClick={() => navigate('rca')}>Investigate →</button>
          </div>
        </section>
        <section className="panel">
          <PanelHead title="Recent questions" subtitle="Latest knowledge activity" />
          <div className="recent-list">
            {data?.recentQueries?.length ? data.recentQueries.map(q => <div key={q.id}><span>?</span><div><b>{q.question}</b><small>{q.mode} · {Math.round(q.confidence * 100)}% confidence</small></div></div>) :
              <div className="empty"><span>✦</span><b>No questions yet</b><small>Ask the copilot about Pump P-101.</small></div>}
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
  const load = useCallback(() => request<DocumentRecord[]>('/documents', {}, token).then(setDocuments).catch(e => setMessage(e.message)), [token])
  useEffect(() => { load() }, [load])
  const upload = async (file?: File) => {
    if (!file) return
    setBusy(true); setMessage('Processing document and building evidence index…')
    const body = new FormData(); body.append('file', file)
    try {
      await request('/documents', { method: 'POST', body }, token)
      setMessage(`${file.name} was indexed successfully.`); load()
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Upload failed') }
    finally { setBusy(false) }
  }
  return (
    <>
      <Hero eyebrow="KNOWLEDGE INGESTION" title="Build the evidence layer." subtitle="Upload maintenance records, inspections, manuals, SOPs and operating data." />
      <section className={`upload-zone ${!isAdmin ? 'disabled' : ''}`}>
        <div className="upload-symbol">⇧</div><div><h3>{busy ? 'Extracting knowledge…' : 'Drop industrial documents here'}</h3><p>PDF, scanned PDF, DOCX, TXT or CSV · Maximum 25 MB</p></div>
        <label className="primary">{isAdmin ? 'Choose files' : 'Admin access required'}<input type="file" accept=".pdf,.txt,.csv,.docx" disabled={!isAdmin || busy} onChange={e => upload(e.target.files?.[0])} /></label>
      </section>
      {message && <Notice text={message} />}
      <section className="panel">
        <PanelHead title="Document library" subtitle={`${documents.length} records in the workspace`} />
        <div className="document-table">
          <div className="table-row table-head"><span>Document</span><span>Type</span><span>Assets</span><span>Status</span><span>Uploaded</span></div>
          {documents.map(doc => <div className="table-row" key={doc.id}>
            <span className="doc-name"><i>▤</i><span><b>{doc.originalName}</b><small>{formatBytes(doc.sizeBytes)} · {doc.summary || doc.errorMessage}</small></span></span>
            <span>{doc.documentType || 'Processing'}</span><span><b>{doc.assetTags || '—'}</b></span>
            <span><em className={`state ${doc.status.toLowerCase()}`}>{doc.status}</em></span><span>{new Date(doc.uploadedAt).toLocaleDateString()}</span>
          </div>)}
          {!documents.length && <div className="empty table-empty"><span>▤</span><b>The library is empty</b><small>Upload the provided synthetic files to begin.</small></div>}
        </div>
      </section>
    </>
  )
}

function Assistant({ token }: { token: string }) {
  const [question, setQuestion] = useState('Why did Pump P-101 fail repeatedly in 2025?')
  const [answer, setAnswer] = useState<ChatAnswer | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ask = async (text = question) => {
    setBusy(true); setError(''); setQuestion(text)
    try { setAnswer(await request<ChatAnswer>('/chat/query', { method: 'POST', body: JSON.stringify({ question: text, assetTag: 'P-101' }) }, token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Question failed') }
    finally { setBusy(false) }
  }
  return (
    <>
      <Hero eyebrow="EVIDENCE-BACKED COPILOT" title="Ask the operation." subtitle="Natural-language answers grounded in your industrial document corpus." />
      <div className="assistant-layout">
        <section className="chat-panel">
          <div className="suggestions">
            {['What maintenance was performed on P-101?', 'What safety steps apply before pump maintenance?', 'Which readings exceeded OEM limits?'].map(text =>
              <button key={text} onClick={() => ask(text)}>{text}</button>)}
          </div>
          <div className="conversation">
            {!answer && !busy && <div className="chat-welcome"><div className="ai-orb">✦</div><h3>What do you need to know?</h3><p>I’ll search the indexed records, connect evidence across files and show exactly where the answer came from.</p></div>}
            {busy && <div className="thinking"><span /><span /><span /> Retrieving relevant evidence…</div>}
            {answer && <>
              <div className="user-message">{question}</div>
              <div className="ai-answer"><div className="answer-head"><span className="ai-orb small">✦</span><b>IndusMind answer</b><em>{Math.round(answer.confidence * 100)}% confidence</em></div><p>{answer.answer}</p><small>Mode: {answer.mode}</small></div>
            </>}
            {error && <Notice text={error} />}
          </div>
          <form className="ask-box" onSubmit={e => { e.preventDefault(); ask() }}>
            <textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about an asset, procedure, incident or operating condition…" />
            <div><span>Asset context: <b>P-101</b></span><button className="primary" disabled={busy}>Ask <i>→</i></button></div>
          </form>
        </section>
        <aside className="evidence-panel">
          <PanelHead title="Source evidence" subtitle={answer ? `${answer.citations.length} passages retrieved` : 'Citations appear with every answer'} />
          {answer?.citations.map((citation, index) => <article className="citation" key={`${citation.source}-${index}`}>
            <div><span>{index + 1}</span><b>{citation.source}</b></div>
            <small>Page {citation.page} · {citation.documentType || 'Industrial record'} · {Math.round((citation.relevance || 0) * 100)}% match</small>
            <p>{citation.excerpt}</p>
          </article>)}
          {!answer && <div className="empty"><span>⌕</span><b>Waiting for a question</b><small>Every answer includes traceable source passages.</small></div>}
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
          <div className="big-orb">P</div><div><span>ROTATING EQUIPMENT</span><h2>{asset.tag}</h2><p>Centrifugal process pump · Boiler Feed Section A</p></div>
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
  const [data, setData] = useState<RcaData | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const generate = async () => {
    setBusy(true); setError('')
    try { setData(await request<RcaData>('/assets/P-101/rca', { method: 'POST' }, token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'RCA failed') }
    finally { setBusy(false) }
  }
  return (
    <>
      <Hero eyebrow="ROOT CAUSE SUPPORT" title="Turn history into action." subtitle="Connect recurring failures, interventions and operating conditions into a traceable investigation brief." actions={<button className="primary" onClick={generate} disabled={busy}>{busy ? 'Analysing evidence…' : 'Generate P-101 RCA'} <span>→</span></button>} />
      {error && <Notice text={error} />}
      {!data && <section className="rca-intro"><div className="rca-graphic"><span>P-101</span><i /><b>Evidence</b><i /><b>Patterns</b><i /><strong>RCA</strong></div><h3>Evidence before inference.</h3><p>IndusMind builds a decision-support brief from uploaded records. It separates observed evidence from probable causes and always preserves the source trail.</p></section>}
      {data && <div className="rca-report">
        <div className="rca-header"><div><span>RCA BRIEF</span><h2>{data.assetTag}: recurring bearing events</h2><p>{data.observedProblem}</p></div><div className="confidence-ring"><b>{Math.round(data.confidence * 100)}%</b><span>evidence confidence</span></div></div>
        <div className="rca-grid">
          <RcaBlock number="01" title="Probable contributors" items={data.probableCauses} tone="risk" />
          <RcaBlock number="02" title="Recommended investigation" items={data.recommendedInvestigation} tone="warn" />
          <RcaBlock number="03" title="Preventive actions" items={data.preventiveActions} tone="good" />
        </div>
        <div className="rca-evidence"><b>Source trail</b>{data.citations.map((x, i) => <span key={i}>{x.source} · p.{x.page}</span>)}</div>
        <p className="disclaimer">{data.disclaimer}</p>
      </div>}
    </>
  )
}

function RcaBlock({ number, title, items, tone }: { number: string; title: string; items: string[]; tone: string }) {
  return <section className={`rca-block ${tone}`}><span>{number}</span><h3>{title}</h3><ul>{items.map(item => <li key={item}>{item}</li>)}</ul></section>
}

function Hero({ eyebrow, title, subtitle, actions }: { eyebrow: string; title: string; subtitle: string; actions?: React.ReactNode }) {
  return <div className="page-hero"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{actions && <div className="hero-actions">{actions}</div>}</div>
}
function PanelHead({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="panel-head"><div><h3>{title}</h3><p>{subtitle}</p></div><span>•••</span></div>
}
function Notice({ text }: { text: string }) { return <div className="notice">ⓘ {text}</div> }
function formatBytes(bytes: number) { return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB` }
