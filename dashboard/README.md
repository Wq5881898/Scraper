# Scraper React Dashboard

A React + Vite visualization interface for the scraper JSONL outputs.

## Features

- Parses `results.jsonl` style files directly in the browser.
- Supports both data shapes used in this repository (`status`/`success`, `latency`/`latency_ms`, `parsed_data`/`data`).
- Shows key charts and tables:
  - Total requests, success rate, average latency, and P95 latency.
  - Latency timeline (latest 120 records).
  - Source success/failure breakdown.
  - HTTP status distribution.
  - Top market-cap tokens and slowest requests.

## Run Locally

```bash
cd dashboard
npm install
npm run dev
```

Then open `http://localhost:5173`.

## Data Input

- Bundled sample: `dashboard/public/results.jsonl` is loaded on page open.
- Upload any local JSONL file with the **Upload JSONL** button.

## Build

```bash
npm run build
npm run preview
```
