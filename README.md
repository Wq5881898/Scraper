# Scraper

Multi-threaded cryptocurrency token scraper with adaptive concurrency control, a Flask API, and a React monitoring dashboard.

The core scraper lives in `src/`. The backend entry points are `main.py` and `api_server.py`. The frontend lives in `dashboard/`.

## Current Features

- Scrape token data from GMGN (`web1`) and DexScreener (`web2`).
- Apply global QPS limiting, retry backoff, and adaptive concurrency through `SmartController`.
- Write scraper output as JSONL under `testdata/`.
- Normalize Web1/Web2 result records for comparison.
- Serve scraper data through a Flask API with Swagger UI.
- Use the React dashboard to run demos, inspect stress benchmark results, and compare Web1/Web2 token data.

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, use:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Install the dashboard dependencies separately:

```bash
cd dashboard
npm install
```

## Run the Backend API

Start the Flask API on port 8000:

```bash
python api_server.py --host 127.0.0.1 --port 8000 --results testdata/results.jsonl
```

On Windows, use `py -3` if `python` is not on `PATH`:

```powershell
py -3 api_server.py --host 127.0.0.1 --port 8000 --results testdata/results.jsonl
```

Useful API URLs:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/apidocs/`
- `http://127.0.0.1:8000/summary`
- `http://127.0.0.1:8000/records?limit=20`
- `http://127.0.0.1:8000/normalized-records`
- `http://127.0.0.1:8000/stress-benchmark-summary`

## Run the Dashboard

Start the React/Vite app:

```bash
cd dashboard
npm run dev
```

Open `http://127.0.0.1:5173/`.

Dashboard views:

- `Run`: launch a scraper demo through the Flask API and preview normalized records.
- `Dashboard`: inspect stress benchmark throughput, stability, latency, CPU, memory, and failure signals.
- `Analytics1`: compare the latest Web1 and Web2 token records field by field.
- `Analytics2`: compare Web1 and Web2 token time-series trends.

Data loading:

- Normalized rows are loaded from `http://127.0.0.1:8000/normalized-records` when the API is running.
- The browser fallback for normalized rows is `dashboard/public/results.jsonl`.
- Stress benchmark data is loaded from `http://127.0.0.1:8000/stress-benchmark-summary`, backed by `testdata/stress_benchmarks/stress_benchmark_summary.json`.

## Run the Scraper CLI

Run a scraper demo from the command line:

```bash
python main.py --run-demo
```

The default demo reads token addresses from `config/testlist.txt`, reads the GMGN cURL template from `config/curl_config.txt`, scrapes enabled sources, and writes JSONL output to `testdata/results.jsonl`.

## Normalize and Summarize Results

Summarize a JSONL result file:

```bash
bash scripts/summarize_results.sh testdata/results.jsonl
```

Or use the API:

```bash
curl http://127.0.0.1:8000/summary
curl http://127.0.0.1:8000/normalized-records
```

Write normalized output through the API:

```bash
curl -X POST http://127.0.0.1:8000/normalize-results \
  -H "Content-Type: application/json" \
  -d '{"path":"testdata/results.jsonl","output_path":"testdata/results.normalized.jsonl"}'
```

## Stress Benchmark

The stress benchmark is documented in `tests/benchmark_stress.md`.

Run it with:

```bash
python tests/benchmark_stress.py --sources web2 --limit 100 --rounds 1
```

Outputs are written under `testdata/stress_benchmarks/`, with the summary at `testdata/stress_benchmarks/stress_benchmark_summary.json`.

## Tests

Run the Python test suite:

```bash
python -m unittest discover -s tests -v
```

On Windows:

```powershell
py -3 -m unittest discover -s tests -v
```

Run the dashboard checks:

```bash
cd dashboard
npm run lint
npm run build
```

The Vite build may warn that the Recharts bundle is larger than 500 kB. That warning does not mean the build failed.

## Refresh Test Addresses

To refresh `config/testlist.txt` from Binance:

```bash
python testlist.py
```

This writes up to 100 BSC contract addresses.
