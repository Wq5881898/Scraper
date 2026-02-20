from __future__ import annotations

from typing import Iterable, Dict


def plot_market_cap_trend(rows: Iterable[Dict], output_path: str) -> None:
    """Generate market cap trend chart from scraped rows (future implementation)."""
    raise NotImplementedError


def plot_holder_count_trend(rows: Iterable[Dict], output_path: str) -> None:
    """Generate holder count trend chart from scraped rows (future implementation)."""
    raise NotImplementedError


def plot_volume_trend(rows: Iterable[Dict], output_path: str) -> None:
    """Generate volume trend chart from scraped rows (future implementation)."""
    raise NotImplementedError


def plot_metrics(rows: Iterable[Dict], output_path: str) -> None:
    """Visualization entry point for scraped-data analytics (future).

    Intended for market-cap, holder-count, and volume trend charts.
    This module will be implemented later using matplotlib or similar.
    """
    raise NotImplementedError
