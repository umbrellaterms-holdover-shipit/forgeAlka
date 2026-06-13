import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API_BASE = import.meta.env.VITE_APEX_API_BASE || ''
const wireFormats = ['auto', 'openai-responses', 'anthropic-messages', 'chat-completions']

function moneyPerMillion(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '?'
  if (n < 0) return 'dynamic'
  return `$${(n * 1_000_000).toFixed(n === 0 ? 0 : n * 1_000_000 < 1 ? 3 : 2)}/M`
}

function modelLabel(option) {
  const p = option.pricing || {}
  const price = `${moneyPerMillion(p.prompt)} in / ${moneyPerMillion(p.completion)} out`
  return `${option.name || option.id} · ${option.id} · ${price}`
}

async function apiJson(path, body, options = {}) {
  const init = {
    method: options.method || 'POST',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
  }
  if (body !== undefined) init.body = JSON.stringify(body)
  const response = await fetch(`${API_BASE}${path}`, init)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`)
  return data
}

function localId(prefix = 'msg') {
  if (globalThis.crypto?.randomUUID) return `${prefix}_${globalThis.crypto.randomUUID().replaceAll('-', '')}`
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function makeMessage(role, content) {
  const stamp = new Date().toISOString()
  return { id: localId('msg'), role, content, created_at: stamp, updated_at: stamp }
}

function splitSystem(messages) {
  const rows = Array.isArray(messages) ? [...messages] : []
  if (rows[0]?.role === 'system') {
    return { system: rows[0].content || '', messages: rows.slice(1) }
  }
  return { system: '', messages: rows }
}

function JsonBlock({ value }) {
  if (!value) return null
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>
}

function StatusPill({ children }) {
  return <span className="pill">{children}</span>
}

function PreflightModal({ preflight, onCancel, onConfirm }) {
  if (!preflight) return null
  const checks = preflight.checks || []
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <h2>Confirm send</h2>
        <p className="modal-lede">The request has not been sent yet. Review the checks, then choose whether to continue.</p>
        <div className="preflight-box in-modal">
          {checks.map(check => (
            <div key={check.id} className={`preflight-check ${check.level}`}>
              <div>
                <b>{check.id}</b>
                <p>{check.message}</p>
              </div>
              {check.requires_confirmation && <em>needs confirmation</em>}
            </div>
          ))}
        </div>
        {preflight.confirmation_message && <p className="confirm-line">{preflight.confirmation_message}</p>}
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel}>Cancel</button>
          <button onClick={onConfirm} disabled={!preflight.ok}>Continue and send</button>
        </div>
      </div>
    </div>
  )
}

function CheckList({ preflight }) {
  const checks = preflight?.checks || []
  if (!checks.length) return null
  return (
    <div className="preflight-box">
      <b>Last preflight checks</b>
      {checks.map(check => (
        <div key={check.id} className={`preflight-check ${check.level}`}>
          <span>{check.message}</span>
          {check.requires_confirmation && <em>confirmation required</em>}
        </div>
      ))}
    </div>
  )
}

function StatsCard({ stats }) {
  if (!stats) return null
  return (
    <div className="stats-card">
      <span><b>{stats.messages || 0}</b> messages</span>
      <span><b>{stats.turns || 0}</b> turns</span>
      <span><b>{stats.estimated_tokens || 0}</b> est. tokens</span>
      <span><b>{stats.words || 0}</b> words</span>
      <span><b>{stats.characters || 0}</b> chars</span>
    </div>
  )
}

function MessageBubble({ message, onSave, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(message.content || '')

  useEffect(() => setDraft(message.content || ''), [message.content])

  async function save() {
    await onSave(message.id, { content: draft, role: message.role })
    setEditing(false)
  }

  return (
    <div className={`message ${message.role}`}>
      <div className="message-topline">
        <b>{message.role}</b>
        <div className="message-actions">
          <button className="tiny" onClick={() => setEditing(!editing)}>{editing ? 'close' : 'edit'}</button>
          <button className="tiny danger" onClick={() => onDelete(message.id)}>delete</button>
        </div>
      </div>
      {editing ? (
        <div className="edit-box">
          <textarea value={draft} onChange={e => setDraft(e.target.value)} />
          <div className="row"><button onClick={save}>Save edit</button><button className="secondary" onClick={() => setEditing(false)}>Cancel</button></div>
        </div>
      ) : (
        <p>{message.content}</p>
      )}
    </div>
  )
}

function ChatPanel({ activeConversationId, setActiveConversationId, openConversations }) {
  const [model, setModel] = useState('anthropic/claude-sonnet-4.6')
  const [modelOptions, setModelOptions] = useState([])
  const [modelSource, setModelSource] = useState('')
  const [wireFormat, setWireFormat] = useState('auto')
  const [temperature, setTemperature] = useState('0.70')
  const [temperatureEnabled, setTemperatureEnabled] = useState(true)
  const [maxTokens, setMaxTokens] = useState('')
  const [ratesPath, setRatesPath] = useState('.apex-web/rates/openrouter.models.json')
  const [title, setTitle] = useState('')
  const [system, setSystem] = useState('')
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState([])
  const [stats, setStats] = useState(null)
  const [dryRun, setDryRun] = useState(false)
  const [busy, setBusy] = useState(false)
  const [lastMeta, setLastMeta] = useState(null)
  const [lastPreflight, setLastPreflight] = useState(null)
  const [pendingSend, setPendingSend] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    apiJson('/api/models/list', { input: ratesPath, limit: 100 })
      .then(data => {
        if (cancelled) return
        const rows = data.models || []
        setModelOptions(rows)
        setModelSource(data.source || '')
        if (rows.length && !rows.some(row => row.id === model)) {
          setModel(rows[0].id)
        }
      })
      .catch(err => setError(err.message))
    return () => { cancelled = true }
  }, [ratesPath])

  useEffect(() => {
    if (!activeConversationId) return
    let cancelled = false
    apiJson(`/api/conversations/${activeConversationId}`, undefined, { method: 'GET' })
      .then(data => {
        if (cancelled) return
        const split = splitSystem(data.messages || [])
        setTitle(data.title || '')
        setModel(data.model || 'anthropic/claude-sonnet-4.6')
        setWireFormat(data.wire_format || 'auto')
        setSystem(split.system)
        setMessages(split.messages)
        setStats(data.stats || null)
        setLastMeta({ conversation: data })
      })
      .catch(err => setError(err.message))
    return () => { cancelled = true }
  }, [activeConversationId])

  function apiMessages(nextMessages) {
    return system.trim() ? [{ ...makeMessage('system', system), id: 'system' }, ...nextMessages] : nextMessages
  }

  function requestPayload(nextMessages) {
    const payload = {
      conversation_id: activeConversationId || undefined,
      title: title || undefined,
      model,
      wire_format: wireFormat,
      messages: apiMessages(nextMessages),
      dry_run: dryRun,
      rates_path: ratesPath
    }
    if (temperatureEnabled && temperature !== '') payload.temperature = Number(temperature)
    if (maxTokens !== '') payload.max_tokens = Number(maxTokens)
    return payload
  }

  async function persistConversationPatch(updates) {
    if (!activeConversationId) return null
    const data = await apiJson(`/api/conversations/${activeConversationId}`, updates, { method: 'PATCH' })
    setStats(data.stats || null)
    return data
  }

  async function saveTitle() {
    if (!activeConversationId) return
    const data = await persistConversationPatch({ title, model, wire_format: wireFormat, messages: apiMessages(messages) })
    if (data) setLastMeta({ conversation: data })
  }

  async function saveMessage(messageId, updates) {
    const next = messages.map(m => m.id === messageId ? { ...m, ...updates, updated_at: new Date().toISOString() } : m)
    setMessages(next)
    if (activeConversationId) {
      const data = await apiJson(`/api/conversations/${activeConversationId}/messages/${messageId}`, updates, { method: 'PATCH' })
      const split = splitSystem(data.messages || [])
      setMessages(split.messages)
      setSystem(split.system || system)
      setStats(data.stats || null)
      setLastMeta({ conversation: data })
    }
  }

  async function deleteMessage(messageId) {
    const next = messages.filter(m => m.id !== messageId)
    setMessages(next)
    if (activeConversationId) {
      const data = await apiJson(`/api/conversations/${activeConversationId}/messages/${messageId}`, undefined, { method: 'DELETE' })
      const split = splitSystem(data.messages || [])
      setMessages(split.messages)
      setSystem(split.system || system)
      setStats(data.stats || null)
      setLastMeta({ conversation: data })
    }
  }

  async function executeSend(payload, nextMessages) {
    setBusy(true)
    setError('')
    try {
      setMessages(nextMessages)
      setPrompt('')
      const data = await apiJson('/api/chat', payload)
      setLastMeta(data)
      if (!dryRun) {
        const split = splitSystem(data.messages || [])
        setMessages(split.messages)
        setSystem(split.system || system)
        if (data.conversation_id) setActiveConversationId(data.conversation_id)
        if (data.conversation) {
          setTitle(data.conversation.title || title)
          setStats(data.conversation.stats || null)
        }
      }
    } catch (err) {
      setError(err.message)
      setMessages(messages)
    } finally {
      setBusy(false)
      setPendingSend(null)
    }
  }

  async function send() {
    if (!prompt.trim()) return
    setBusy(true)
    setError('')
    setLastPreflight(null)
    const nextMessages = [...messages, makeMessage('user', prompt)]
    const payload = requestPayload(nextMessages)
    try {
      if (!dryRun) {
        const preflight = await apiJson('/api/chat/preflight', payload)
        setLastPreflight(preflight)
        setPendingSend({ payload, nextMessages, preflight })
        return
      }
      await executeSend(payload, nextMessages)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function newConversation() {
    setActiveConversationId(null)
    setTitle('')
    setSystem('')
    setMessages([])
    setStats(null)
    setLastMeta(null)
    setLastPreflight(null)
    setPrompt('')
  }

  return (
    <section className="panel chat-panel">
      <PreflightModal
        preflight={pendingSend?.preflight}
        onCancel={() => setPendingSend(null)}
        onConfirm={() => executeSend(pendingSend.payload, pendingSend.nextMessages)}
      />
      <div className="panel-header">
        <div>
          <h2>Chat</h2>
          <p>Persistent GPT-ish conversations on disk. Sends pass through a preflight pipeline before the request leaves the browser.</p>
        </div>
        <div className="header-actions">
          <StatusPill>{dryRun ? 'dry run' : 'live + preflight'}</StatusPill>
          <button className="secondary" onClick={openConversations}>Manage conversations</button>
          <button className="secondary" onClick={newConversation}>New</button>
        </div>
      </div>
      <div className="settings-grid">
        <label>Conversation title<input value={title} onChange={e => setTitle(e.target.value)} placeholder="auto from first prompt" /></label>
        <label>Model
          <select value={model} onChange={e => setModel(e.target.value)}>
            {!modelOptions.some(option => option.id === model) && <option value={model}>{model}</option>}
            {modelOptions.map(option => <option key={option.id} value={option.id}>{modelLabel(option)}</option>)}
          </select>
        </label>
        <label>Wire format<select value={wireFormat} onChange={e => setWireFormat(e.target.value)}>{wireFormats.map(w => <option key={w}>{w}</option>)}</select></label>
        <label>Max tokens<input value={maxTokens} onChange={e => setMaxTokens(e.target.value)} placeholder="optional" /></label>
      </div>
      <div className="settings-grid two">
        <label className="temperature-control">Temperature
          <div className="slider-row">
            <input type="range" min="0" max="2" step="0.05" value={temperature} disabled={!temperatureEnabled} onChange={e => setTemperature(e.target.value)} />
            <input className="numeric-small" type="number" min="0" max="2" step="0.05" value={temperature} disabled={!temperatureEnabled} onChange={e => setTemperature(e.target.value)} />
          </div>
          <span className="hint-row"><label className="inline-check"><input type="checkbox" checked={temperatureEnabled} onChange={e => setTemperatureEnabled(e.target.checked)} /> send temperature</label></span>
        </label>
        <label>Rates/model snapshot for preflight<input value={ratesPath} onChange={e => setRatesPath(e.target.value)} /></label>
      </div>
      {modelSource && <div className="hint-line">Model dropdown source: {modelSource}{modelSource === 'bundled-starter-catalog' ? ' · run apex models refresh for live prices' : ''}</div>}
      <div className="row top-gap">
        <button onClick={saveTitle} disabled={!activeConversationId}>Save conversation settings</button>
        {activeConversationId && <StatusPill>{activeConversationId}</StatusPill>}
      </div>
      <StatsCard stats={stats} />
      <label className="wide-label">System / instructions<textarea value={system} onChange={e => setSystem(e.target.value)} placeholder="optional" /></label>
      <div className="transcript">
        {messages.length === 0 && <div className="empty">No messages yet. Feed the little model-goblin.</div>}
        {messages.map(m => <MessageBubble key={m.id} message={m} onSave={saveMessage} onDelete={deleteMessage} />)}
      </div>
      <div className="composer">
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Ask something..." onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send() }} />
        <div className="composer-actions">
          <label className="check"><input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} /> Dry run</label>
          <button onClick={send} disabled={busy || !prompt.trim()}>{busy ? 'Sending...' : 'Send'}</button>
        </div>
      </div>
      <CheckList preflight={lastPreflight} />
      {error && <div className="error">{error}</div>}
      <JsonBlock value={lastMeta && (dryRun ? lastMeta : { conversation_id: lastMeta.conversation_id, wire_format: lastMeta.wire_format, endpoint: lastMeta.endpoint, raw: lastMeta.raw, stats: lastMeta.conversation?.stats })} />
    </section>
  )
}

function ConversationsPanel({ onOpen }) {
  const [rows, setRows] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function refresh() {
    try {
      setError('')
      const data = await apiJson('/api/conversations', undefined, { method: 'GET' })
      setRows(data.conversations || [])
      setResult(data)
    } catch (err) { setError(err.message) }
  }

  async function createBlank() {
    try {
      setError('')
      const data = await apiJson('/api/conversations', { title: 'Untitled conversation', messages: [] })
      await refresh()
      onOpen(data.id)
    } catch (err) { setError(err.message) }
  }

  async function remove(id) {
    try {
      setError('')
      await apiJson(`/api/conversations/${id}`, undefined, { method: 'DELETE' })
      await refresh()
    } catch (err) { setError(err.message) }
  }

  useEffect(() => { refresh() }, [])

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Conversations</h2>
          <p>Disk-backed chat records with stats. Open one to edit/delete messages or continue the conversation.</p>
        </div>
        <div className="row"><button onClick={refresh}>Refresh</button><button onClick={createBlank}>New conversation</button></div>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="conversation-list">
        {rows.length === 0 && <div className="empty-list">No saved conversations yet.</div>}
        {rows.map(row => (
          <article key={row.id} className="conversation-card">
            <div>
              <h3>{row.title || row.id}</h3>
              <p>{row.id}</p>
              <StatsCard stats={row.stats} />
            </div>
            <div className="conversation-actions">
              <button onClick={() => onOpen(row.id)}>Open</button>
              <button className="danger" onClick={() => remove(row.id)}>Delete</button>
            </div>
          </article>
        ))}
      </div>
      <JsonBlock value={result} />
    </section>
  )
}

function KeysPanel() {
  const [provider, setProvider] = useState('openrouter')
  const [path, setPath] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function status() {
    try { setError(''); setResult(await apiJson('/api/keys/status', { provider, path: path || undefined })) } catch (err) { setError(err.message) }
  }
  async function save() {
    try {
      setError('')
      const data = await apiJson('/api/keys/set', { provider, path: path || undefined, api_key: apiKey })
      setApiKey('')
      setResult(data)
    } catch (err) { setError(err.message) }
  }
  return (
    <section className="panel">
      <h2>Keys</h2>
      <p>Store API keys in local files. The UI never displays the saved secret again; it only shows file status.</p>
      <div className="settings-grid two">
        <label>Provider<input value={provider} onChange={e => setProvider(e.target.value)} /></label>
        <label>Custom key path<input value={path} onChange={e => setPath(e.target.value)} placeholder="optional" /></label>
      </div>
      <label className="wide-label">API key<input className="secret-input" type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="paste key to save" /></label>
      <div className="row"><button onClick={status}>Status</button><button onClick={save} disabled={!apiKey.trim()}>Save key file</button></div>
      {error && <div className="error">{error}</div>}
      <JsonBlock value={result} />
    </section>
  )
}

function ConvertPanel() {
  const [file, setFile] = useState(null)
  const [toFormat, setToFormat] = useState('md')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function convert() {
    if (!file) return
    setError('')
    setResult(null)
    const form = new FormData()
    form.append('file', file)
    form.append('to_format', toFormat)
    const response = await fetch(`${API_BASE}/api/convert`, { method: 'POST', body: form })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) { setError(data.error || `HTTP ${response.status}`); return }
    setResult(data)
  }

  return (
    <section className="panel">
      <h2>Convert</h2>
      <p>Upload a file, pick a target extension, get a converted artifact back.</p>
      <div className="row">
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
        <input value={toFormat} onChange={e => setToFormat(e.target.value)} aria-label="Target format" />
        <button onClick={convert} disabled={!file}>Convert</button>
      </div>
      {error && <div className="error">{error}</div>}
      {result?.download_url && <a className="download" href={`${API_BASE}${result.download_url}`}>Download result</a>}
      <JsonBlock value={result} />
    </section>
  )
}

function DepsPanel() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  async function doctor() { try { setError(''); setResult(await apiJson('/api/deps/doctor', { tools: ['ffmpeg', 'pandoc'] })) } catch (err) { setError(err.message) } }
  async function dryInstall() { try { setError(''); setResult(await apiJson('/api/deps/install', { tools: ['ffmpeg', 'pandoc'], dry_run: true })) } catch (err) { setError(err.message) } }
  return (
    <section className="panel">
      <h2>Deps</h2>
      <p>Check or dry-run installing the external tools that conversion/media workflows need.</p>
      <div className="row"><button onClick={doctor}>Doctor</button><button onClick={dryInstall}>Dry-run install</button></div>
      {error && <div className="error">{error}</div>}
      <JsonBlock value={result} />
    </section>
  )
}

function ModelsPanel() {
  const [snapshotPath, setSnapshotPath] = useState('.apex-web/rates/openrouter.models.json')
  const [limit, setLimit] = useState(20)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  async function list() { try { setError(''); setResult(await apiJson('/api/models/list', { input: snapshotPath, limit })) } catch (err) { setError(err.message) } }
  async function refresh() { try { setError(''); setResult(await apiJson('/api/models/refresh', { out: snapshotPath })) } catch (err) { setError(err.message) } }
  async function seed() { try { setError(''); setResult(await apiJson('/api/models/seed', { out: snapshotPath })) } catch (err) { setError(err.message) } }
  return (
    <section className="panel">
      <h2>Models</h2>
      <p>Refresh/list an OpenRouter model snapshot used by the cost calculator and chat preflight.</p>
      <div className="settings-grid two">
        <label>Snapshot path<input value={snapshotPath} onChange={e => setSnapshotPath(e.target.value)} /></label>
        <label>Limit<input value={limit} onChange={e => setLimit(Number(e.target.value))} /></label>
      </div>
      <div className="row"><button onClick={list}>List</button><button onClick={seed}>Write starter 45+ catalog</button><button onClick={refresh}>Refresh from OpenRouter</button></div>
      {error && <div className="error">{error}</div>}
      <JsonBlock value={result} />
    </section>
  )
}

function CostPanel() {
  const [rates, setRates] = useState(null)
  const [requests, setRequests] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  async function estimate() {
    if (!rates || !requests) return
    setError('')
    const form = new FormData()
    form.append('rates', rates)
    form.append('requests', requests)
    const response = await fetch(`${API_BASE}/api/cost`, { method: 'POST', body: form })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) { setError(data.error || `HTTP ${response.status}`); return }
    setResult(data)
  }
  return (
    <section className="panel">
      <h2>Cost</h2>
      <p>Upload a rate snapshot and request usage JSON/JSONL. The calculator stays offline and boring, which is exactly what money math should be.</p>
      <div className="stack">
        <label>Rates JSON<input type="file" onChange={e => setRates(e.target.files?.[0] || null)} /></label>
        <label>Requests JSON/JSONL<input type="file" onChange={e => setRequests(e.target.files?.[0] || null)} /></label>
        <button onClick={estimate} disabled={!rates || !requests}>Estimate</button>
      </div>
      {error && <div className="error">{error}</div>}
      <JsonBlock value={result} />
    </section>
  )
}

function App() {
  const [tab, setTab] = useState('chat')
  const [activeConversationId, setActiveConversationId] = useState(null)
  function openConversation(id) {
    setActiveConversationId(id)
    setTab('chat')
  }
  const tabs = {
    chat: <ChatPanel activeConversationId={activeConversationId} setActiveConversationId={setActiveConversationId} openConversations={() => setTab('conversations')} />,
    conversations: <ConversationsPanel onOpen={openConversation} />,
    keys: <KeysPanel />,
    convert: <ConvertPanel />,
    deps: <DepsPanel />,
    models: <ModelsPanel />,
    cost: <CostPanel />
  }
  return (
    <main>
      <header className="hero">
        <div>
          <h1>Apex Web</h1>
          <p>One CLI spine, one Flask API skin, one React cockpit. Less hydra, more launch panel.</p>
        </div>
        <StatusPill>API {API_BASE || 'same-origin'}</StatusPill>
      </header>
      <nav>{Object.keys(tabs).map(name => <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>)}</nav>
      {tabs[tab]}
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App />)
