# Scraper
Multi-threaded web scraper for cryptocurrency token data collection with adaptive concurrency control.

Code is organized under the `src/` package.

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate      # On macOS/Linux
# .venv\Scripts\activate       # On Windows
pip install -r requirements.txt
```

## Running the Scraper

Make sure the virtual environment is activated, then run:

```bash
python main.py --run-demo
```

This will scrape token data from gmgn.ai and DexScreener using addresses loaded from `config/testlist.txt`, with adaptive concurrency managed by the SmartController. Results are saved to `testdata/results.jsonl`.

## Running Tests

```bash
python -m unittest discover -s tests -v
```

Or use the automation script, which also writes a timestamped log to `logs/`:

```bash
bash scripts/run_tests.sh
```

The log is saved to `logs/test_run_<timestamp>.log` and a compact summary is printed at the end.

## Summarizing Scrape Results

After running the scraper, summarize `testdata/results.jsonl` by source, success rate, and average latency:

```bash
bash scripts/summarize_results.sh testdata/results.jsonl
```

Pass a different file path as the argument if your output is stored elsewhere. The script prints per-source and overall breakdowns.

## React Visualization Dashboard

A React dashboard is available under `dashboard/` for visual inspection of scraper runs.

```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173` and the UI will load `dashboard/public/results.jsonl` by default.  
You can also upload any JSONL output directly from the page.

## Swagger 2 API

The project now includes a lightweight Flask API with Swagger 2 docs (via `flasgger`):

```bash
python api_server.py --host 127.0.0.1 --port 8000 --results testdata/results.jsonl
```

Then open:

- `http://127.0.0.1:8000/apidocs/` for Swagger UI
- `http://127.0.0.1:8000/summary` for aggregated stats
- `http://127.0.0.1:8000/records?limit=20` for latest rows

## Generating the Test Address List

To refresh the token address list from Binance:

```bash
python testlist.py
```

This writes up to 100 BSC contract addresses to `config/testlist.txt`.
