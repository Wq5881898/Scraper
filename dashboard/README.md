# Scraper React Dashboard

React + Vite interface for running scraper demos, reviewing benchmark behavior, and comparing normalized Web1/Web2 token data.

## Views

- `Run`: submit a scraper demo to `api_server.py` and preview normalized result rows.
- `Dashboard`: inspect stress benchmark throughput, stability, latency, CPU, memory, backoff, and failure signals.
- `Analytics1`: compare the latest Web1 and Web2 records for a selected token.
- `Analytics2`: compare Web1 and Web2 token trends over time.

## Data Flow

- Normalized scraper rows are loaded from `http://127.0.0.1:8000/normalized-records` when the backend is running.
- The browser fallback for normalized rows is `dashboard/public/results.jsonl`.
- Stress benchmark rows are loaded from `http://127.0.0.1:8000/stress-benchmark-summary`.
- The benchmark API reads `testdata/stress_benchmarks/stress_benchmark_summary.json` by default.

## Run Locally

Start the backend from the repository root:

```bash
python api_server.py --host 127.0.0.1 --port 8000 --results testdata/results.jsonl
```

Start the dashboard:

```bash
cd dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`.

## Build and Check

```bash
npm run lint
npm run build
npm run preview
```

The production build can emit a Recharts chunk-size warning. The app is still built successfully unless the command exits with an error.
