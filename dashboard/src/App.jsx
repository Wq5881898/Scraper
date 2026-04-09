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

function App() {
  const [rows, setRows] = useState([])
  const [invalidLines, setInvalidLines] = useState(0)
  const [datasetLabel, setDatasetLabel] = useState('Loading bundled sample...')
  const [errorText, setErrorText] = useState('')

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

  const slowestRows = useMemo(
    () => [...rows].sort((a, b) => b.latency - a.latency).slice(0, 10),
    [rows],
  )

  return (
    <main className="app-shell">
      <div className="ambient-shape shape-a" aria-hidden="true" />
      <div className="ambient-shape shape-b" aria-hidden="true" />

      <header className="panel hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Scraper Dashboard</p>
          <h1>React Visual Console For JSONL Runs</h1>
          <p className="hero-description">
            Inspect scraper health, latency behavior, and token-side metrics from `results.jsonl` with upload support.
          </p>
        </div>

        <div className="hero-actions">
          <label className="button-primary" htmlFor="upload-jsonl">
            Upload JSONL
          </label>
          <input id="upload-jsonl" type="file" accept=".jsonl,.txt,.json" onChange={handleFileUpload} />

          <button className="button-secondary" type="button" onClick={() => void loadBundledSample()}>
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
      </header>

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
    </main>
  )
}

export default App
