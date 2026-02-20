"""Core scraper package.

Provides the base scraper framework, concrete scraper implementations,
adaptive control strategies, metrics collection, and storage backends.

Key modules:
    base            -- BaseScraper abstract class
    scrapers        -- Web1Scraper, Web2Scraper concrete implementations
    factory         -- ScraperFactory for creating scrapers
    controller      -- ThreadPoolController for concurrency management
    smart_controller-- SmartController for adaptive control
    strategies      -- ControlStrategy and concrete strategy classes
    metrics         -- MetricsCollector for runtime statistics
    models          -- Task, ScrapeResult, MetricsSnapshot dataclasses
    rate_limiter    -- RateLimiter for QPS throttling
    backoff         -- BackoffStrategy for exponential retry delays
    storage         -- StorageBase and JsonlStorage for persistence
"""
