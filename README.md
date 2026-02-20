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

This will scrape token data from gmgn.ai and DexScreener using addresses loaded from `testlist.txt`, with adaptive concurrency managed by the SmartController. Results are saved to `results.jsonl`.

## Running Tests

```bash
python -m unittest discover -s tests -v
```

## Generating the Test Address List

To refresh the token address list from Binance:

```bash
python testlist.py
```

This writes up to 100 BSC contract addresses to `testlist.txt`.
