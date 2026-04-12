import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

const statusPalette = ['#0f766e', '#0891b2', '#f59e0b', '#ea580c', '#dc2626']
const tokenPalette = ['#1d4ed8', '#0f766e', '#b45309', '#be123c', '#1e3a8a', '#14532d']
const numberFormatter = new Intl.NumberFormat('en-US')
const decimalFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const moneyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

const defaultForm = {
  addresses: 'config/testlist.txt',
  curl_config: 'config/curl_config.txt',
  results: 'testdata/results.jsonl',
  qps: '2.0',
  max_workers: '8',
  initial_limit: '3',
  limit: '100',
}

const pageSize = 10
const navItems = [
  { id: 'run', label: 'Run' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'analytics', label: 'Analytics', disabled: true },
  { id: 'reports', label: 'Reports', disabled: true },
]

function coerceNumber(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

function coerceTimestamp(value) {
  const numeric = coerceNumber(value)
  if (!numeric) {
    return null
  }
  if (numeric > 1_000_000_000_000) {
    return numeric
  }
  return numeric * 1000
}

function compactAddress(value) {
  if (!value || typeof value !== 'string' || value.length < 12) {
    return value || 'unknown-token'
  }
  return `${value.slice(0, 6)}...${value.slice(-4)}`
}

function quantile(values, q) {
  if (!values.length) {
    return null
  }
  const sorted = [...values].sort((a, b) => a - b)
  const location = (sorted.length - 1) * q
  const base = Math.floor(location)
  const rest = location - base
  const lower = sorted[base]
  const upper = sorted[base + 1] ?? lower
  return lower + rest * (upper - lower)
}

function parseTokenName(token, index) {
  if (!token || typeof token !== 'object') {
    return `token-${index + 1}`
  }
  return token.token_name || token.name || token.symbol || compactAddress(token.address) || `token-${index + 1}`
}

function parseEntry(entry, index) {
  const payload = entry.parsed_data ?? entry.data ?? null
  const token = Array.isArray(payload) ? payload[0] ?? null : payload
  const tokenPrice = token?.price ?? {}

  const statusCode = coerceNumber(entry.status_code) ?? 0
  const explicitSuccess = entry.success ?? entry.status
  const success =
    typeof explicitSuccess === 'boolean'
      ? explicitSuccess
      : statusCode >= 200 && statusCode < 400 && !entry.error_type

  return {
    index: index + 1,
    source: entry.source_id ?? 'unknown-source',
    taskId: entry.task_id ?? `row-${index + 1}`,
    timestampMs: coerceTimestamp(entry.timestamp),
    latency: coerceNumber(entry.latency_ms ?? entry.latency) ?? 0,
    statusCode: String(statusCode || 'unknown'),
    success,
    tokenName: parseTokenName(token, index),
    symbol: token?.symbol || token?.token_symbol || 'n/a',
    marketCap: coerceNumber(token?.market_cap),
    volume24h: coerceNumber(token?.volume_h24 ?? tokenPrice.volume_24h),
    liquidity: coerceNumber(token?.liquidity_usd ?? token?.liquidity),
    errorType: entry.error_type || 'none',
  }
}

function parseJsonl(rawText) {
  const parsedRows = []
  let invalidLines = 0

  rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line, index) => {
      try {
        parsedRows.push(parseEntry(JSON.parse(line), index))
      } catch {
        invalidLines += 1
      }
    })

  return { parsedRows, invalidLines }
}

function parseApiRecords(records) {
  return (records ?? [])
    .filter((record) => record && typeof record === 'object')
    .map((record, index) => parseEntry(record, index))
}

function formatTime(timestampMs) {
  if (!timestampMs) {
    return 'n/a'
  }
  return new Date(timestampMs).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDateTime(timestampMs) {
  if (!timestampMs) {
    return 'n/a'
  }
  return new Date(timestampMs).toLocaleString([], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function formatCount(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return numberFormatter.format(Math.round(value))
}

function formatPercent(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${decimalFormatter.format(value)}%`
}

function formatLatency(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${decimalFormatter.format(value)} ms`
}

function formatMoney(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return moneyFormatter.format(value)
}

function buildSourceData(rows) {
  const grouped = new Map()

  rows.forEach((row) => {
    if (!grouped.has(row.source)) {
      grouped.set(row.source, { source: row.source, requests: 0, successes: 0, failures: 0, latencyTotal: 0 })
    }
    const current = grouped.get(row.source)
    current.requests += 1
    current.latencyTotal += row.latency
    if (row.success) {
      current.successes += 1
    } else {
      current.failures += 1
    }
  })

  return [...grouped.values()].map((item) => ({
    source: item.source,
    requests: item.requests,
    successes: item.successes,
    failures: item.failures,
    successRate: item.requests ? (item.successes / item.requests) * 100 : 0,
    avgLatency: item.requests ? item.latencyTotal / item.requests : 0,
  }))
}

function buildStatusData(rows) {
  const grouped = new Map()
  rows.forEach((row) => {
    grouped.set(row.statusCode, (grouped.get(row.statusCode) ?? 0) + 1)
  })
  return [...grouped.entries()]
    .map(([statusCode, count]) => ({ statusCode, count }))
    .sort((a, b) => b.count - a.count)
}

function buildTopTokenData(rows) {
  return rows
    .filter((row) => row.marketCap && row.marketCap > 0)
    .sort((a, b) => (b.marketCap ?? 0) - (a.marketCap ?? 0))
    .slice(0, 6)
    .map((row) => ({
      tokenName: row.tokenName,
      marketCap: row.marketCap,
      source: row.source,
    }))
}

function StatCard({ label, value, hint }) {
  return (
    <article className="panel stat-card">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      <p className="stat-hint">{hint}</p>
    </article>
  )
}

function RunPage({ form, errors, onChange, onSubmit, onReset, runStatus, message, previewRows, currentPage, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(previewRows.length / pageSize))
  const pagedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return previewRows.slice(start, start + pageSize)
  }, [previewRows, currentPage])

  return (
    <>
      <section className="panel hero-panel">
        <div>
          <p className="eyebrow">Scraper Product Entry</p>
          <h1>Run Scraper</h1>
          <p className="hero-description">
            Configure the same inputs used by the Python demo entry point, validate them in the browser, and prepare a scraper run.
          </p>
        </div>

        <div className="status-box">
          <p className="status-label">Current Status</p>
          <p className={`status-value status-${runStatus}`}>{runStatus.toUpperCase()}</p>
          <p className="status-message">{message}</p>
        </div>
      </section>

      <section className="panel form-panel">
        <form className="run-form" onSubmit={onSubmit}>
          <div className="field-grid">
            <label className="field">
              <span>Address List Path</span>
              <input name="addresses" type="text" value={form.addresses} onChange={onChange} />
              {errors.addresses ? <small>{errors.addresses}</small> : null}
            </label>

            <label className="field">
              <span>Curl Config Path</span>
              <input name="curl_config" type="text" value={form.curl_config} onChange={onChange} />
              {errors.curl_config ? <small>{errors.curl_config}</small> : null}
            </label>

            <label className="field">
              <span>Results Output Path</span>
              <input name="results" type="text" value={form.results} onChange={onChange} />
              {errors.results ? <small>{errors.results}</small> : null}
            </label>

            <label className="field">
              <span>Requests Per Second Limit (QPS)</span>
              <input name="qps" type="number" step="0.1" value={form.qps} onChange={onChange} />
              {errors.qps ? <small>{errors.qps}</small> : null}
            </label>

            <label className="field">
              <span>Max Workers</span>
              <input name="max_workers" type="number" value={form.max_workers} onChange={onChange} />
              {errors.max_workers ? <small>{errors.max_workers}</small> : null}
            </label>

            <label className="field">
              <span>Initial Concurrency Limit</span>
              <input name="initial_limit" type="number" value={form.initial_limit} onChange={onChange} />
              {errors.initial_limit ? <small>{errors.initial_limit}</small> : null}
            </label>

            <label className="field">
              <span>Max Address Count</span>
              <input name="limit" type="number" value={form.limit} onChange={onChange} />
              {errors.limit ? <small>{errors.limit}</small> : null}
            </label>
          </div>

          <div className="button-row">
            <button className="button-primary" type="submit">
              Run Demo
            </button>
            <button className="button-secondary" type="button" onClick={onReset}>
              Reset
            </button>
          </div>
        </form>
      </section>

      <section className="panel preview-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Preview</p>
            <h2>Results Preview</h2>
          </div>
          <p className="preview-count">{previewRows.length} rows loaded</p>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Source</th>
                <th>Timestamp</th>
                <th>Symbol</th>
                <th>Success</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {pagedRows.length ? (
                pagedRows.map((row) => (
                  <tr key={row.taskId}>
                    <td>{row.taskId}</td>
                    <td>{row.source}</td>
                    <td>{formatDateTime(row.timestampMs)}</td>
                    <td>{row.symbol}</td>
                    <td>{row.success ? 'Yes' : 'No'}</td>
                    <td>{row.statusCode}</td>
                    <td>{row.latency}</td>
                    <td>{row.errorType}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="empty-state">
                    No preview rows available yet. Add a sample results.jsonl file or connect the backend run API.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination-row">
          <button className="button-secondary" type="button" onClick={() => onPageChange(Math.max(1, currentPage - 1))} disabled={currentPage === 1}>
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            className="button-secondary"
            type="button"
            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
          >
            Next
          </button>
        </div>
      </section>
    </>
  )
}

function DashboardPage({
  rows,
  invalidLines,
  datasetLabel,
  errorText,
  onFileUpload,
  onReloadSample,
  summary,
  timelineData,
  sourceData,
  statusData,
  topTokenData,
  slowestRows,
}) {
  return (
    <>
      <section className="panel hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Scraper Dashboard</p>
          <h1>React Visual Console For JSONL Runs</h1>
          <p className="hero-description">
            Inspect scraper health, latency behavior, and token-side metrics from results.jsonl with upload support.
          </p>
        </div>

        <div className="hero-actions">
          <label className="button-primary" htmlFor="upload-jsonl">
            Upload JSONL
          </label>
          <input id="upload-jsonl" type="file" accept=".jsonl,.txt,.json" onChange={onFileUpload} />

          <button className="button-secondary" type="button" onClick={onReloadSample}>
            Reload Bundled Sample
          </button>

          <div className="dataset-meta">
            <p>
              Dataset: <span>{datasetLabel}</span>
            </p>
            <p>
              Parsed rows: <span>{formatCount(rows.length)}</span>
            </p>
            <p>
              Skipped lines: <span>{formatCount(invalidLines)}</span>
            </p>
          </div>
        </div>
      </section>

      {errorText ? <p className="error-banner">{errorText}</p> : null}

      <section className="stat-grid">
        <StatCard label="Total Requests" value={formatCount(summary.totalRequests)} hint="Rows parsed from JSONL" />
        <StatCard label="Success Rate" value={formatPercent(summary.successRate)} hint="Success by status or HTTP code" />
        <StatCard label="Average Latency" value={formatLatency(summary.avgLatency)} hint="Mean per-request response time" />
        <StatCard label="P95 Latency" value={formatLatency(summary.p95Latency)} hint="Tail latency pressure indicator" />
      </section>

      <section className="chart-grid">
        <article className="panel chart-card">
          <div className="card-header">
            <h2>Latency Timeline</h2>
            <p>Latest 120 records</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timelineData}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="sequence" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `${value}ms`} />
                <Tooltip
                  formatter={(value) => formatLatency(value)}
                  labelFormatter={(value) => `Request #${value}`}
                  contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }}
                />
                <Line type="monotone" dataKey="latency" stroke="#2563eb" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Source Reliability</h2>
            <p>Success and failure counts per source</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceData}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="source" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value, name) => {
                    if (name === 'successRate') {
                      return formatPercent(value)
                    }
                    return formatCount(value)
                  }}
                  contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }}
                />
                <Bar dataKey="successes" stackId="result" fill="#0f766e" />
                <Bar dataKey="failures" stackId="result" fill="#ea580c" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Status Code Mix</h2>
            <p>Distribution of HTTP status outcomes</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusData}
                  dataKey="count"
                  nameKey="statusCode"
                  cx="50%"
                  cy="50%"
                  outerRadius="72%"
                  label={({ statusCode, percent }) => `${statusCode} (${decimalFormatter.format(percent * 100)}%)`}
                >
                  {statusData.map((segment, index) => (
                    <Cell key={`${segment.statusCode}-${segment.count}`} fill={statusPalette[index % statusPalette.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatCount(value)} contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <section className="chart-grid token-grid">
        <article className="panel chart-card">
          <div className="card-header">
            <h2>Top Market Caps</h2>
            <p>Derived from parsed token payloads</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topTokenData} layout="vertical" margin={{ left: 20, right: 8 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis type="number" tick={{ fontSize: 12 }} tickFormatter={(value) => `${Math.round(value / 1_000_000)}M`} />
                <YAxis dataKey="tokenName" type="category" width={100} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => formatMoney(value)} contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }} />
                <Bar dataKey="marketCap" radius={[8, 8, 8, 8]}>
                  {topTokenData.map((item, index) => (
                    <Cell key={`${item.tokenName}-${item.source}`} fill={tokenPalette[index % tokenPalette.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel table-card">
          <div className="card-header">
            <h2>Slowest Requests</h2>
            <p>Top 10 latency outliers</p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Source</th>
                  <th>Token</th>
                  <th>Latency</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {slowestRows.map((row) => (
                  <tr key={row.taskId}>
                    <td>{compactAddress(row.taskId)}</td>
                    <td>{row.source}</td>
                    <td>{row.tokenName}</td>
                    <td>{formatLatency(row.latency)}</td>
                    <td>{row.statusCode}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <footer className="panel footer-note">
        <p>
          Aggregated traded volume (24h fields): <span>{formatMoney(summary.totalVolume)}</span>
        </p>
      </footer>
    </>
  )
}

function App() {
  const [activeView, setActiveView] = useState('run')
  const [rows, setRows] = useState([])
  const [invalidLines, setInvalidLines] = useState(0)
  const [datasetLabel, setDatasetLabel] = useState('Loading bundled sample...')
  const [errorText, setErrorText] = useState('')
  const [form, setForm] = useState(defaultForm)
  const [errors, setErrors] = useState({})
  const [runStatus, setRunStatus] = useState('idle')
  const [message, setMessage] = useState('Fill in the form and run a scraper demo.')
  const [currentPage, setCurrentPage] = useState(1)

  const loadDatasetText = useCallback((rawText, label) => {
    const { parsedRows, invalidLines: skippedLines } = parseJsonl(rawText)
    setRows(parsedRows)
    setInvalidLines(skippedLines)
    setDatasetLabel(label)
    setErrorText(parsedRows.length ? '' : 'No valid JSONL records were found in the selected file.')
  }, [])

  const loadBundledSample = useCallback(async () => {
    try {
      const response = await fetch('/results.jsonl')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const text = await response.text()
      loadDatasetText(text, 'public/results.jsonl')
    } catch {
      setRows([])
      setInvalidLines(0)
      setDatasetLabel('No bundled sample detected')
      setErrorText('Put a JSONL file in dashboard/public/results.jsonl or upload one from your machine.')
    }
  }, [loadDatasetText])

  useEffect(() => {
    void loadBundledSample()
  }, [loadBundledSample])

  const handleFileUpload = async (event) => {
    const [file] = event.target.files ?? []
    if (!file) {
      return
    }
    const text = await file.text()
    loadDatasetText(text, file.name)
    event.target.value = ''
  }

  const summary = useMemo(() => {
    const totalRequests = rows.length
    if (!totalRequests) {
      return {
        totalRequests: 0,
        successRate: null,
        avgLatency: null,
        p95Latency: null,
        totalVolume: null,
      }
    }

    const successes = rows.filter((row) => row.success).length
    const latencies = rows.map((row) => row.latency).filter((value) => Number.isFinite(value))
    const totalVolume = rows.reduce((sum, row) => sum + (row.volume24h ?? 0), 0)

    return {
      totalRequests,
      successRate: (successes / totalRequests) * 100,
      avgLatency: latencies.length ? latencies.reduce((sum, value) => sum + value, 0) / latencies.length : null,
      p95Latency: quantile(latencies, 0.95),
      totalVolume: totalVolume || null,
    }
  }, [rows])

  const timelineData = useMemo(
    () =>
      rows.slice(-120).map((row) => ({
        sequence: row.index,
        time: formatTime(row.timestampMs),
        latency: row.latency,
        source: row.source,
      })),
    [rows],
  )

  const sourceData = useMemo(() => buildSourceData(rows), [rows])
  const statusData = useMemo(() => buildStatusData(rows), [rows])
  const topTokenData = useMemo(() => buildTopTokenData(rows), [rows])
  const slowestRows = useMemo(() => [...rows].sort((a, b) => b.latency - a.latency).slice(0, 10), [rows])

  function handleChange(event) {
    const { name, value } = event.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setErrors((prev) => {
      if (!prev[name]) {
        return prev
      }
      const next = { ...prev }
      delete next[name]
      return next
    })
  }

  function validateForm() {
    const nextErrors = {}

    if (!form.addresses.trim()) nextErrors.addresses = 'Address list path is required.'
    if (!form.curl_config.trim()) nextErrors.curl_config = 'Curl config path is required.'
    if (!form.results.trim()) nextErrors.results = 'Results output path is required.'
    if (!(Number(form.qps) > 0)) nextErrors.qps = 'QPS must be greater than 0.'
    if (!(Number(form.max_workers) >= 1)) nextErrors.max_workers = 'Max workers must be at least 1.'
    if (!(Number(form.initial_limit) >= 1)) nextErrors.initial_limit = 'Initial limit must be at least 1.'
    if (!(Number(form.limit) >= 1)) nextErrors.limit = 'Limit must be at least 1.'

    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  function handleReset() {
    setForm(defaultForm)
    setErrors({})
    setRunStatus('idle')
    setMessage('Form reset. Ready to run again.')
    setCurrentPage(1)
  }

  async function handleSubmit(event) {
    event.preventDefault()

    if (!validateForm()) {
      setRunStatus('error')
      setMessage('Please fix the validation errors before running.')
      return
    }

    setRunStatus('running')
    setMessage('Running scraper...')

    try {
      const response = await fetch('http://127.0.0.1:8000/api/run-demo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          addresses: form.addresses,
          curl_config: form.curl_config,
          results: form.results,
          qps: Number(form.qps),
          max_workers: Number(form.max_workers),
          initial_limit: Number(form.initial_limit),
          limit: Number(form.limit),
        }),
      })

      let payload = null
      try {
        payload = await response.json()
      } catch {
        payload = null
      }

      if (!response.ok || payload?.status !== 'success') {
        throw new Error(payload?.message || `Run failed with HTTP ${response.status}.`)
      }

      const parsedRows = parseApiRecords(payload.records)
      setRows(parsedRows)
      setInvalidLines(payload.invalid_lines ?? 0)
      setDatasetLabel(payload.results_path || form.results)
      setErrorText('')
      setCurrentPage(1)
      setRunStatus('success')
      setMessage(payload.message || 'Run completed successfully.')
    } catch (error) {
      setRunStatus('error')
      if (error instanceof TypeError) {
        setMessage('Cannot reach the backend API at http://127.0.0.1:8000. Make sure api_server.py is running and try again.')
      } else {
        setMessage(error instanceof Error ? error.message : 'Run failed.')
      }
    }
  }

  return (
    <main className="app-shell">
      <nav className="top-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-tab ${activeView === item.id ? 'nav-tab-active' : ''}`}
            disabled={item.disabled}
            onClick={() => setActiveView(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {activeView === 'run' ? (
        <RunPage
          form={form}
          errors={errors}
          onChange={handleChange}
          onSubmit={handleSubmit}
          onReset={handleReset}
          runStatus={runStatus}
          message={message}
          previewRows={rows}
          currentPage={currentPage}
          onPageChange={setCurrentPage}
        />
      ) : (
        <DashboardPage
          rows={rows}
          invalidLines={invalidLines}
          datasetLabel={datasetLabel}
          errorText={errorText}
          onFileUpload={handleFileUpload}
          onReloadSample={() => void loadBundledSample()}
          summary={summary}
          timelineData={timelineData}
          sourceData={sourceData}
          statusData={statusData}
          topTokenData={topTokenData}
          slowestRows={slowestRows}
        />
      )}
    </main>
  )
}

export default App
