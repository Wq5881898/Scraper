import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

const numberFormatter = new Intl.NumberFormat('en-US')
const decimalFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const comparisonDecimalFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
})
const preciseDecimalFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 5,
  maximumFractionDigits: 5,
})
const moneyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

const defaultForm = {
  selected_sources: ['web1', 'web2'],
  addresses: 'config/testlist.txt',
  curl_config: 'config/curl_config.txt',
  results: 'testdata/results.jsonl',
  qps: '2.0',
  max_workers: '4',
  initial_limit: '2',
  limit: '100',
}

const pageSize = 10
const navItems = [
  { id: 'run', label: 'Run' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'analytics', label: 'Analytics1' },
  { id: 'analytics2', label: 'Analytics2' },
]
const sourceOptions = [
  { id: 'web1', label: 'Web1' },
  { id: 'web2', label: 'Web2' },
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

function deriveDemoRunConfig(qpsValue) {
  const safeQps = Math.max(1, Math.ceil(Number(qpsValue) || 1))
  return {
    maxWorkers: Math.max(4, safeQps * 2),
    initialLimit: Math.max(1, safeQps),
    limit: 100,
  }
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
    priceUsd: coerceNumber(token?.price) ?? coerceNumber(tokenPrice.price),
    symbol: token?.symbol || token?.token_symbol || 'n/a',
    marketCap: coerceNumber(token?.market_cap),
    fdv: coerceNumber(token?.fdv),
    volume24h: coerceNumber(token?.volume_h24 ?? tokenPrice.volume_24h),
    liquidity: coerceNumber(token?.liquidity_usd ?? token?.liquidity),
    holderCount: coerceNumber(token?.holder_count),
    circulatingSupply: coerceNumber(token?.circulating_supply),
    totalSupply: coerceNumber(token?.total_supply),
    maxSupply: coerceNumber(token?.max_supply),
    price1m: coerceNumber(tokenPrice.price_1m),
    price5m: coerceNumber(tokenPrice.price_5m),
    price1h: coerceNumber(tokenPrice.price_1h),
    price6h: coerceNumber(tokenPrice.price_6h),
    price24h: coerceNumber(tokenPrice.price_24h),
    priceChangeM1Pct: null,
    priceChangeM5Pct: null,
    priceChangeH1Pct: null,
    priceChangeH6Pct: null,
    priceChangeH24Pct: null,
    createdAtUtc: token?.created_at_utc ?? null,
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
    .map((record, index) => {
      if ('parsed_data' in record || 'data' in record) {
        return parseEntry(record, index)
      }

      return {
        index: index + 1,
        source: record.source_id ?? 'unknown-source',
        taskId: record.task_id ?? `row-${index + 1}`,
        timestampMs: coerceTimestamp(record.timestamp),
        latency: coerceNumber(record.latency_ms ?? record.latency) ?? 0,
        statusCode: String(coerceNumber(record.status_code) ?? 'unknown'),
        success: Boolean(record.success),
        tokenName: record.token_name || record.name || `token-${index + 1}`,
        priceUsd: coerceNumber(record.price_usd),
        symbol: record.symbol || 'n/a',
        marketCap: coerceNumber(record.market_cap),
        fdv: coerceNumber(record.fdv),
        volume24h: coerceNumber(record.volume_h24),
        liquidity: coerceNumber(record.liquidity_usd),
        holderCount: coerceNumber(record.holder_count),
        circulatingSupply: coerceNumber(record.circulating_supply),
        totalSupply: coerceNumber(record.total_supply),
        maxSupply: coerceNumber(record.max_supply),
        price1m: coerceNumber(record.price_1m),
        price5m: coerceNumber(record.price_5m),
        price1h: coerceNumber(record.price_1h),
        price6h: coerceNumber(record.price_6h),
        price24h: coerceNumber(record.price_24h),
        priceChangeM1Pct: coerceNumber(record.price_change_m1_pct),
        priceChangeM5Pct: coerceNumber(record.price_change_m5_pct),
        priceChangeH1Pct: coerceNumber(record.price_change_h1_pct),
        priceChangeH6Pct: coerceNumber(record.price_change_h6_pct),
        priceChangeH24Pct: coerceNumber(record.price_change_h24_pct),
        createdAtUtc: record.created_at_utc || null,
        errorType: record.error_type || 'none',
      }
    })
}

function parseStressBenchmarkSummary(payload) {
  const records = Array.isArray(payload) ? payload : Array.isArray(payload?.records) ? payload.records : []

  return records
    .filter((record) => record && typeof record === 'object')
    .map((record, index) => {
      const statusCodeCounts = record.status_code_counts ?? {}
      const errorTypeCounts = record.error_type_counts ?? {}
      const totalRecords = coerceNumber(record.total_records) ?? 0
      const successCount = coerceNumber(record.success_count) ?? 0
      const failureCount = coerceNumber(record.failure_count) ?? 0
      const backoffTriggers = coerceNumber(record.backoff_trigger_count) ?? 0
      const http200Count = coerceNumber(statusCodeCounts['200']) ?? 0
      const finalSslFailures = coerceNumber(errorTypeCounts.SSLError) ?? 0
      const finalConnectionFailures = coerceNumber(errorTypeCounts.ConnectionError) ?? 0
      const firstAttemptRetryCount =
        Array.isArray(record.round_results)
          ? record.round_results.reduce((sum, roundResult) => {
              const events = Array.isArray(roundResult?.backoff?.events) ? roundResult.backoff.events : []
              return sum + events.filter((event) => coerceNumber(event?.attempt) === 1).length
            }, 0)
          : 0
      const firstTrySuccessRate = totalRecords ? ((totalRecords - firstAttemptRetryCount) / totalRecords) * 100 : 0

      let mainSignal = 'none'
      if (failureCount > 0 && finalSslFailures > 0) {
        mainSignal = 'SSLError'
      } else if (failureCount > 0 && finalConnectionFailures > 0) {
        mainSignal = 'ConnectionError'
      } else if (backoffTriggers > 0) {
        mainSignal = 'Backoff'
      }

      return {
        id: record.label ?? `benchmark-${index + 1}`,
        label: record.label ?? `Benchmark ${index + 1}`,
        workers: coerceNumber(record.max_workers) ?? 0,
        initialLimit: coerceNumber(record.initial_limit) ?? 0,
        rounds: coerceNumber(record.rounds) ?? 0,
        totalRecords,
        successCount,
        failureCount,
        successRate: coerceNumber(record.success_rate_pct) ?? (totalRecords ? (successCount / totalRecords) * 100 : 0),
        firstTrySuccessRate,
        firstAttemptRetryCount,
        elapsedSec: coerceNumber(record.elapsed_sec) ?? 0,
        avgLatency: coerceNumber(record.avg_latency_ms) ?? 0,
        throughput: coerceNumber(record.throughput_rps) ?? 0,
        http200Count,
        http429Count: coerceNumber(record.http_429_count) ?? 0,
        timeoutCount: coerceNumber(record.timeout_count) ?? 0,
        connErrorCount: coerceNumber(record.conn_error_count) ?? 0,
        backoffTriggers,
        finalSslFailures,
        finalConnectionFailures,
        avgCpu: coerceNumber(record.resource_usage?.avg_cpu_pct),
        peakMemory: coerceNumber(record.resource_usage?.peak_memory_mb),
        sourceLabel: Array.isArray(record.sources) ? record.sources.join(', ') : 'n/a',
        addressesPerRound: coerceNumber(record.addresses_per_round) ?? totalRecords,
        mainSignal,
      }
    })
    .sort((left, right) => left.workers - right.workers)
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

function formatMinuteTime(timestampMs) {
  if (!timestampMs) {
    return 'n/a'
  }
  return new Date(timestampMs).toLocaleString([], {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
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

function formatRate(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${decimalFormatter.format(value)} req/s`
}

function formatCpu(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${decimalFormatter.format(value)}%`
}

function formatMemory(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${decimalFormatter.format(value)} MB`
}

function formatMoney(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return moneyFormatter.format(value)
}

function formatPreciseNumber(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return preciseDecimalFormatter.format(value)
}

function formatCompactMoney(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000_000) {
    return `$${decimalFormatter.format(value / 1_000_000_000)}B`
  }
  if (absolute >= 1_000_000) {
    return `$${decimalFormatter.format(value / 1_000_000)}M`
  }
  if (absolute >= 1_000) {
    return `$${decimalFormatter.format(value / 1_000)}K`
  }
  return moneyFormatter.format(value)
}

function formatComparisonValue(value, type = 'text') {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  if (type === 'money') {
    return formatCompactMoney(value)
  }
  if (type === 'number') {
    return comparisonDecimalFormatter.format(value)
  }
  if (type === 'percent') {
    return formatPercent(value)
  }
  if (type === 'datetime') {
    return value
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }
  return String(value)
}

function areDifferent(left, right) {
  const leftEmpty = left === null || left === undefined || left === ''
  const rightEmpty = right === null || right === undefined || right === ''
  if (leftEmpty && rightEmpty) {
    return false
  }
  return left !== right
}

function areDisplayValuesDifferent(left, right, type = 'text') {
  const leftEmpty = left === null || left === undefined || left === ''
  const rightEmpty = right === null || right === undefined || right === ''
  if (leftEmpty && rightEmpty) {
    return false
  }
  return formatComparisonValue(left, type) !== formatComparisonValue(right, type)
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

function buildMetricTimeline(rows, selectedToken, valueKey) {
  return [...rows]
    .filter((row) => row.tokenName === selectedToken)
    .sort((a, b) => (a.timestampMs ?? 0) - (b.timestampMs ?? 0))
    .map((row, index) => ({
      index: index + 1,
      time: formatMinuteTime(row.timestampMs),
      fullTime: formatDateTime(row.timestampMs),
      web1: row.source === 'web1' ? row[valueKey] ?? null : null,
      web2: row.source === 'web2' ? row[valueKey] ?? null : null,
    }))
}

function buildYAxisDomain(data, keys) {
  const values = data
    .flatMap((item) => keys.map((key) => item[key]))
    .filter((value) => typeof value === 'number' && Number.isFinite(value))

  if (!values.length) {
    return ['auto', 'auto']
  }

  const min = Math.min(...values)
  const max = Math.max(...values)

  if (min === max) {
    const padding = Math.max(Math.abs(min) * 0.05, 1)
    return [min - padding, max + padding]
  }

  const padding = Math.max((max - min) * 0.08, 1)
  return [min - padding, max + padding]
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

function AnalyticsPage({ rows }) {
  const tokenOptions = useMemo(() => {
    return [...new Set(rows.map((row) => row.tokenName).filter(Boolean))].sort((a, b) => a.localeCompare(b))
  }, [rows])

  const [selectedToken, setSelectedToken] = useState('')

  useEffect(() => {
    if (!tokenOptions.length) {
      setSelectedToken('')
      return
    }
    if (!selectedToken || !tokenOptions.includes(selectedToken)) {
      setSelectedToken(tokenOptions[0])
    }
  }, [tokenOptions, selectedToken])

  const latestBySource = useMemo(() => {
    const tokenRows = rows.filter((row) => row.tokenName === selectedToken)
    const pickLatest = (sourceId) =>
      [...tokenRows]
        .filter((row) => row.source === sourceId)
        .sort((a, b) => (b.timestampMs ?? 0) - (a.timestampMs ?? 0))[0] ?? null

    return {
      web1: pickLatest('web1'),
      web2: pickLatest('web2'),
    }
  }, [rows, selectedToken])

  const comparisonFields = [
    { key: 'tokenName', label: 'Token Name' },
    { key: 'source', label: 'Source' },
    { key: 'priceUsd', label: 'Price', type: 'number' },
    { key: 'price1m', label: 'Price 1M', type: 'number' },
    { key: 'price5m', label: 'Price 5M', type: 'number' },
    { key: 'price1h', label: 'Price 1H', type: 'number' },
    { key: 'price6h', label: 'Price 6H', type: 'number' },
    { key: 'price24h', label: 'Price 24H', type: 'number' },
    { key: 'priceChangeM1Pct', label: 'Price Change 1M', type: 'percent' },
    { key: 'priceChangeM5Pct', label: 'Price Change 5M', type: 'percent' },
    { key: 'priceChangeH1Pct', label: 'Price Change 1H', type: 'percent' },
    { key: 'priceChangeH6Pct', label: 'Price Change 6H', type: 'percent' },
    { key: 'priceChangeH24Pct', label: 'Price Change 24H', type: 'percent' },
    { key: 'liquidity', label: 'Liquidity', type: 'money' },
    { key: 'marketCap', label: 'Market Cap', type: 'money' },
    { key: 'fdv', label: 'FDV', type: 'money' },
    { key: 'volume24h', label: 'Volume 24H', type: 'money' },
    { key: 'holderCount', label: 'Holder Count', type: 'number' },
    { key: 'circulatingSupply', label: 'Circulating Supply', type: 'number' },
    { key: 'totalSupply', label: 'Total Supply', type: 'number' },
    { key: 'maxSupply', label: 'Max Supply', type: 'number' },
    { key: 'createdAtUtc', label: 'Created At', type: 'datetime' },
    { key: 'success', label: 'Success' },
  ]

  return (
    <>
      <section className="panel hero-panel">
        <div>
          <p className="eyebrow">Analytics1</p>
          <h1>Cross-Source Token Comparison</h1>
          <p className="hero-description">
            Select one token and compare the latest normalized Web1 and Web2 records field by field. Different values are highlighted.
          </p>
        </div>
        <div className="status-box">
          <p className="status-label">Selected Token</p>
          <select className="analytics-select" value={selectedToken} onChange={(event) => setSelectedToken(event.target.value)}>
            {tokenOptions.length ? (
              tokenOptions.map((token) => (
                <option key={token} value={token}>
                  {token}
                </option>
              ))
            ) : (
              <option value="">No token data loaded</option>
            )}
          </select>
          <p className="status-message">
            {latestBySource.web1 || latestBySource.web2 ? 'Latest records ready for comparison.' : 'No records found for this token yet.'}
          </p>
        </div>
      </section>

      <section className="panel preview-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Comparison</p>
            <h2>Latest Web1 vs Web2</h2>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Field</th>
                <th>Web1</th>
                <th>Web2</th>
              </tr>
            </thead>
            <tbody>
              {comparisonFields.map((field) => {
                const left = latestBySource.web1?.[field.key] ?? null
                const right = latestBySource.web2?.[field.key] ?? null
                const mismatch = areDisplayValuesDifferent(left, right, field.type)

                return (
                  <tr key={field.key} className={mismatch ? 'comparison-mismatch' : ''}>
                    <td>{field.label}</td>
                    <td>{formatComparisonValue(left, field.type)}</td>
                    <td>{formatComparisonValue(right, field.type)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function AnalyticsTimeSeriesPage({ rows }) {
  const tokenOptions = useMemo(() => {
    return [...new Set(rows.map((row) => row.tokenName).filter(Boolean))].sort((a, b) => a.localeCompare(b))
  }, [rows])

  const [selectedToken, setSelectedToken] = useState('')

  useEffect(() => {
    if (!tokenOptions.length) {
      setSelectedToken('')
      return
    }
    if (!selectedToken || !tokenOptions.includes(selectedToken)) {
      setSelectedToken(tokenOptions[0])
    }
  }, [tokenOptions, selectedToken])

  const priceTimeline = useMemo(() => buildMetricTimeline(rows, selectedToken, 'priceUsd'), [rows, selectedToken])
  const holderTimeline = useMemo(() => buildMetricTimeline(rows, selectedToken, 'holderCount'), [rows, selectedToken])
  const liquidityTimeline = useMemo(() => buildMetricTimeline(rows, selectedToken, 'liquidity'), [rows, selectedToken])
  const fdvTimeline = useMemo(() => buildMetricTimeline(rows, selectedToken, 'fdv'), [rows, selectedToken])

  const charts = [
    {
      title: 'Price',
      hint: 'Price trend over time',
      data: priceTimeline,
      formatter: (value) => formatPreciseNumber(value),
      tickFormatter: (value) => preciseDecimalFormatter.format(value),
    },
    {
      title: 'Holder Count',
      hint: 'Holder count over time',
      data: holderTimeline,
      formatter: (value) => formatComparisonValue(value, 'number'),
      yAxisDomain: buildYAxisDomain(holderTimeline, ['web1', 'web2']),
      tickFormatter: (value) => Math.round(value),
    },
    { title: 'Liquidity', hint: 'Liquidity trend over time', data: liquidityTimeline, formatter: (value) => formatComparisonValue(value, 'money') },
    { title: 'FDV', hint: 'FDV trend over time', data: fdvTimeline, formatter: (value) => formatComparisonValue(value, 'money') },
  ]

  return (
    <>
      <section className="panel hero-panel">
        <div>
          <p className="eyebrow">Analytics2</p>
          <h1>Time-Based Token Comparison</h1>
          <p className="hero-description">
            Select one token and compare Web1 and Web2 across time with simple side-by-side trend lines.
          </p>
        </div>
        <div className="status-box">
          <p className="status-label">Selected Token</p>
          <select className="analytics-select" value={selectedToken} onChange={(event) => setSelectedToken(event.target.value)}>
            {tokenOptions.length ? (
              tokenOptions.map((token) => (
                <option key={token} value={token}>
                  {token}
                </option>
              ))
            ) : (
              <option value="">No token data loaded</option>
            )}
          </select>
          <p className="status-message">
            {selectedToken ? 'The charts below compare the latest time series for the selected token.' : 'No token data loaded yet.'}
          </p>
        </div>
      </section>

      <section className="chart-grid analytics-grid">
        {charts.map((chart) => (
          <article key={chart.title} className="panel chart-card">
            <div className="card-header">
              <h2>{chart.title}</h2>
              <p>{chart.hint}</p>
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart.data}>
                  <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                  <XAxis dataKey="time" tick={{ fontSize: 12 }} minTickGap={24} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    domain={chart.yAxisDomain ?? ['auto', 'auto']}
                    tickFormatter={(value) => (chart.tickFormatter ? chart.tickFormatter(value) : value)}
                  />
                  <Tooltip
                    formatter={(value) => chart.formatter(value)}
                    labelFormatter={(value, payload) => payload?.[0]?.payload?.fullTime || value}
                    contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }}
                  />
                  <Line type="monotone" dataKey="web1" stroke="#1d4ed8" strokeWidth={2.5} dot={false} connectNulls />
                  <Line type="monotone" dataKey="web2" stroke="#0f766e" strokeWidth={2.5} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </article>
        ))}
      </section>
    </>
  )
}

function RunPage({ form, errors, onChange, onSubmit, onReset, runStatus, message, previewRows, currentPage, onPageChange }) {
  const sortedPreviewRows = useMemo(
    () =>
      [...previewRows].sort((left, right) => {
        const leftTime = left.timestampMs ?? 0
        const rightTime = right.timestampMs ?? 0
        if (rightTime !== leftTime) {
          return rightTime - leftTime
        }
        return String(right.taskId).localeCompare(String(left.taskId))
      }),
    [previewRows],
  )

  const totalPages = Math.max(1, Math.ceil(sortedPreviewRows.length / pageSize))
  const pagedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return sortedPreviewRows.slice(start, start + pageSize)
  }, [sortedPreviewRows, currentPage])

  return (
    <>
      <section className="panel hero-panel">
        <div>
          <p className="eyebrow">Scraper Product Entry</p>
          <h1>Run Scraper</h1>
          <p className="hero-description">
            Choose the source and request speed, then launch a scraper demo run with browser-side validation.
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
          <div className="source-selector">
            <div className="source-selector-copy">
              <span className="field-heading">Data Sources</span>
              <p>Select one or more scraper sources. This layout can scale later for Web3 and more sources.</p>
            </div>
            <div className="source-option-row">
              {sourceOptions.map((source) => (
                <label key={source.id} className="source-chip">
                  <input
                    name="selected_sources"
                    type="checkbox"
                    value={source.id}
                    checked={form.selected_sources.includes(source.id)}
                    onChange={onChange}
                  />
                  <span>{source.label}</span>
                </label>
              ))}
            </div>
            {errors.selected_sources ? <small className="field-error">{errors.selected_sources}</small> : null}
          </div>

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
          </div>

          <div className="button-row">
            <button className="button-primary" type="submit">
              Run Scraper
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
          <p className="preview-count">{sortedPreviewRows.length} rows loaded</p>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Source</th>
                <th>Timestamp</th>
                <th>Name</th>
                <th>Success</th>
                <th>Status</th>
                <th>Price</th>
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
                    <td>{row.tokenName}</td>
                    <td>{row.success ? 'Yes' : 'No'}</td>
                    <td>{row.statusCode}</td>
                    <td>{row.priceUsd ?? '--'}</td>
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
  benchmarkRows,
  datasetLabel,
  errorText,
  onFileUpload,
  onReloadSample,
  dashboardSummary,
}) {
  return (
    <>
      <section className="panel hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Scraper Monitoring</p>
          <h1>Scraper Monitoring Dashboard</h1>
          <p className="hero-description">Track scraper throughput, stability, resource usage, and error signals.</p>
        </div>

        <div className="hero-actions">
          <label className="button-primary" htmlFor="upload-jsonl">
            Upload Summary JSON
          </label>
          <input id="upload-jsonl" type="file" accept=".json" onChange={onFileUpload} />

          <button className="button-secondary" type="button" onClick={onReloadSample}>
            Reload Stress Benchmark Sample
          </button>

          <div className="dataset-meta">
            <p>
              Dataset: <span>{datasetLabel}</span>
            </p>
            <p>
              Benchmark configs: <span>{formatCount(benchmarkRows.length)}</span>
            </p>
            <p>
              Requests per config: <span>{formatCount(dashboardSummary.requestsPerConfig)}</span>
            </p>
            <p>
              Sources: <span>{dashboardSummary.sourceLabel}</span>
            </p>
          </div>
        </div>
      </section>

      {errorText ? <p className="error-banner">{errorText}</p> : null}

      <section className="stat-grid">
        <StatCard label="Best Stable Threads" value={formatCount(dashboardSummary.bestStable?.workers)} hint="Highest stable concurrency found in the benchmark" />
        <StatCard label="Best Stable Throughput" value={formatRate(dashboardSummary.bestStable?.throughput)} hint="Best throughput before backoff or failures appeared" />
        <StatCard label="Best Stable Avg Latency" value={formatLatency(dashboardSummary.bestStable?.avgLatency)} hint="Average latency at the best stable thread level" />
        <StatCard label="Best Stable Avg CPU" value={formatCpu(dashboardSummary.bestStable?.avgCpu)} hint="CPU usage is aggregated across cores" />
        <StatCard label="Best Stable Peak Memory" value={formatMemory(dashboardSummary.bestStable?.peakMemory)} hint="Peak memory at the best stable thread level" />
        <StatCard label="First Backoff Threads" value={formatCount(dashboardSummary.firstBackoff?.workers)} hint="First thread level that triggered retry backoff" />
        <StatCard label="Failure Starts At" value={formatCount(dashboardSummary.firstFailure?.workers)} hint="First thread level with final request failures" />
        <StatCard label="Final SSL Failures" value={formatCount(dashboardSummary.totalFinalSslFailures)} hint="Final failed requests with SSLError" />
      </section>

      <section className="chart-grid monitor-grid">
        <article className="panel chart-card">
          <div className="card-header">
            <h2>Throughput vs Threads</h2>
            <p>Overall scraper throughput under higher concurrency</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmarkRows}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="workers" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => decimalFormatter.format(value)} />
                <Tooltip
                  formatter={(value) => formatRate(value)}
                  labelFormatter={(value) => `${value} threads`}
                  contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }}
                />
                <Line type="monotone" dataKey="throughput" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Average Latency vs Threads</h2>
            <p>Latency cost of pushing concurrency higher</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmarkRows}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="workers" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `${Math.round(value)}ms`} />
                <Tooltip
                  formatter={(value) => formatLatency(value)}
                  labelFormatter={(value) => `${value} threads`}
                  contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }}
                />
                <Line type="monotone" dataKey="avgLatency" stroke="#ea580c" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Average CPU vs Threads</h2>
            <p>CPU usage rises as more workers stay active</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmarkRows}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="workers" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `${Math.round(value)}%`} />
                <Tooltip formatter={(value) => formatCpu(value)} labelFormatter={(value) => `${value} threads`} contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }} />
                <Line type="monotone" dataKey="avgCpu" stroke="#0f766e" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Peak Memory vs Threads</h2>
            <p>Memory cost grows with more aggressive concurrency</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmarkRows}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="workers" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => `${Math.round(value)}MB`} />
                <Tooltip formatter={(value) => formatMemory(value)} labelFormatter={(value) => `${value} threads`} contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }} />
                <Line type="monotone" dataKey="peakMemory" stroke="#8b5cf6" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Success Rate vs Threads</h2>
            <p>Final success versus first-try success before backoff recovery</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={benchmarkRows}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="workers" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} tickFormatter={(value) => `${value}%`} />
                <Tooltip
                  formatter={(value, _dataKey, item) => [formatPercent(value), item?.name ?? 'Success Rate']}
                  labelFormatter={(value) => `${value} threads`}
                  contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }}
                />
                <Line type="monotone" dataKey="successRate" name="Final Success Rate" stroke="#16a34a" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="firstTrySuccessRate" name="First-Try Success Rate" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel chart-card">
          <div className="card-header">
            <h2>Failures and Backoff</h2>
            <p>Final failures and retry pressure by thread level</p>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={benchmarkRows}>
                <CartesianGrid strokeDasharray="4 4" stroke="#d4d7dc" />
                <XAxis dataKey="workers" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => formatCount(value)} labelFormatter={(value) => `${value} threads`} contentStyle={{ borderRadius: 12, border: '1px solid #d9e0ea' }} />
                <Bar dataKey="backoffTriggers" fill="#f59e0b" />
                <Bar dataKey="failureCount" fill="#334155" />
                <Bar dataKey="finalSslFailures" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <section className="panel table-card full-width-card">
        <div className="card-header">
          <h2>Thread-Level Benchmark Summary</h2>
          <p>Final benchmark values used by this monitoring dashboard</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Label</th>
                <th>Workers</th>
                <th>Records</th>
                <th>Success Rate</th>
                <th>First-Try Success</th>
                <th>Time (s)</th>
                <th>Throughput</th>
                <th>Avg Latency</th>
                <th>Backoff</th>
                <th>Final Failures</th>
                <th>Final SSL</th>
                <th>Avg CPU</th>
                <th>Peak Mem</th>
                <th>Main Signal</th>
              </tr>
            </thead>
            <tbody>
              {benchmarkRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.label}</td>
                  <td>{formatCount(row.workers)}</td>
                  <td>{formatCount(row.totalRecords)}</td>
                  <td>{formatPercent(row.successRate)}</td>
                  <td>{formatPercent(row.firstTrySuccessRate)}</td>
                  <td>{decimalFormatter.format(row.elapsedSec)}</td>
                  <td>{formatRate(row.throughput)}</td>
                  <td>{formatLatency(row.avgLatency)}</td>
                  <td>{formatCount(row.backoffTriggers)}</td>
                  <td>{formatCount(row.failureCount)}</td>
                  <td>{formatCount(row.finalSslFailures)}</td>
                  <td>{formatCpu(row.avgCpu)}</td>
                  <td>{formatMemory(row.peakMemory)}</td>
                  <td>{row.mainSignal}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function App() {
  const [activeView, setActiveView] = useState('run')
  const [rows, setRows] = useState([])
  const [invalidLines, setInvalidLines] = useState(0)
  const [datasetLabel, setDatasetLabel] = useState('Loading bundled sample...')
  const [errorText, setErrorText] = useState('')
  const [benchmarkRows, setBenchmarkRows] = useState([])
  const [dashboardDatasetLabel, setDashboardDatasetLabel] = useState('Loading stress benchmark sample...')
  const [dashboardErrorText, setDashboardErrorText] = useState('')
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
      const response = await fetch('http://127.0.0.1:8000/normalized-records?path=testdata/results.jsonl')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = await response.json()
      const parsedRows = parseApiRecords(payload.records)
      setRows(parsedRows)
      setInvalidLines(payload.invalid_lines ?? 0)
      setDatasetLabel(payload.normalized_results_path || 'testdata/results.normalized.jsonl')
      setErrorText(parsedRows.length ? '' : 'No valid normalized records were found.')
    } catch {
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
        setErrorText('Start api_server.py for normalized data, or put a JSONL file in dashboard/public/results.jsonl, or upload one from your machine.')
      }
    }
  }, [loadDatasetText])

  const loadDashboardSummaryText = useCallback((rawText, label) => {
    const payload = JSON.parse(rawText)
    const parsedSummary = parseStressBenchmarkSummary(payload)
    setBenchmarkRows(parsedSummary)
    setDashboardDatasetLabel(label)
    setDashboardErrorText(parsedSummary.length ? '' : 'No valid stress benchmark configs were found in the selected summary file.')
  }, [])

  const loadDashboardSample = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/stress-benchmark-summary?path=testdata/stress_benchmarks/stress_benchmark_summary.json')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = await response.json()
      const parsedSummary = parseStressBenchmarkSummary(payload)
      setBenchmarkRows(parsedSummary)
      setDashboardDatasetLabel(payload.path || 'testdata/stress_benchmarks/stress_benchmark_summary.json')
      setDashboardErrorText(parsedSummary.length ? '' : 'No valid stress benchmark configs were found.')
    } catch {
      try {
        const response = await fetch('/stress_benchmark_summary.json')
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const text = await response.text()
        loadDashboardSummaryText(text, 'public/stress_benchmark_summary.json')
      } catch {
        setBenchmarkRows([])
        setDashboardDatasetLabel('No stress benchmark sample detected')
        setDashboardErrorText('Start api_server.py for stress benchmark data, or upload stress_benchmark_summary.json from your machine.')
      }
    }
  }, [loadDashboardSummaryText])

  useEffect(() => {
    void loadBundledSample()
  }, [loadBundledSample])

  useEffect(() => {
    void loadDashboardSample()
  }, [loadDashboardSample])

  const handleFileUpload = async (event) => {
    const [file] = event.target.files ?? []
    if (!file) {
      return
    }
    const text = await file.text()
    loadDatasetText(text, file.name)
    event.target.value = ''
  }

  const handleDashboardFileUpload = async (event) => {
    const [file] = event.target.files ?? []
    if (!file) {
      return
    }
    try {
      const text = await file.text()
      loadDashboardSummaryText(text, file.name)
    } catch {
      setBenchmarkRows([])
      setDashboardDatasetLabel(file.name)
      setDashboardErrorText('The selected file is not a valid stress benchmark summary JSON file.')
    }
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

  const dashboardSummary = useMemo(() => {
    const sorted = [...benchmarkRows].sort((left, right) => left.workers - right.workers)
    const bestStable = [...sorted]
      .filter((row) => row.successRate === 100 && row.failureCount === 0 && row.backoffTriggers === 0)
      .sort((left, right) => right.throughput - left.throughput)[0] ?? null
    const firstBackoff = sorted.find((row) => row.backoffTriggers > 0) ?? null
    const firstFailure = sorted.find((row) => row.failureCount > 0) ?? null

    return {
      bestStable,
      firstBackoff,
      firstFailure,
      requestsPerConfig: sorted[0]?.totalRecords ?? null,
      sourceLabel: sorted[0]?.sourceLabel ?? 'n/a',
      totalFinalSslFailures: sorted.reduce((sum, row) => sum + (row.finalSslFailures ?? 0), 0),
    }
  }, [benchmarkRows])

  function handleChange(event) {
    const { name, value, type, checked } = event.target
    setForm((prev) => {
      if (name === 'selected_sources' && type === 'checkbox') {
        const nextSelected = checked
          ? [...prev.selected_sources, value]
          : prev.selected_sources.filter((item) => item !== value)
        return { ...prev, selected_sources: nextSelected }
      }
      return { ...prev, [name]: value }
    })
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

    if (!form.selected_sources.length) nextErrors.selected_sources = 'Select at least one source.'
    if (!form.addresses.trim()) nextErrors.addresses = 'Address list path is required.'
    if (!form.curl_config.trim()) nextErrors.curl_config = 'Curl config path is required.'
    if (!form.results.trim()) nextErrors.results = 'Results output path is required.'
    if (!(Number(form.qps) > 0)) nextErrors.qps = 'QPS must be greater than 0.'

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
      const derivedConfig = deriveDemoRunConfig(form.qps)
      const response = await fetch('http://127.0.0.1:8000/api/run-demo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          selected_sources: form.selected_sources,
          addresses: form.addresses,
          curl_config: form.curl_config,
          results: form.results,
          qps: Number(form.qps),
          max_workers: derivedConfig.maxWorkers,
          initial_limit: derivedConfig.initialLimit,
          limit: derivedConfig.limit,
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

      const parsedRows = parseApiRecords(payload.normalized_records ?? payload.records)
      setRows(parsedRows)
      setInvalidLines(payload.invalid_lines ?? 0)
      setDatasetLabel(payload.normalized_results_path || payload.results_path || form.results)
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
      ) : activeView === 'analytics' ? (
        <AnalyticsPage rows={rows} />
      ) : activeView === 'analytics2' ? (
        <AnalyticsTimeSeriesPage rows={rows} />
      ) : (
        <DashboardPage
          benchmarkRows={benchmarkRows}
          datasetLabel={dashboardDatasetLabel}
          errorText={dashboardErrorText}
          onFileUpload={handleDashboardFileUpload}
          onReloadSample={() => void loadDashboardSample()}
          dashboardSummary={dashboardSummary}
        />
      )}
    </main>
  )
}

export default App
