# SPEC.md — Real-Time Listing Aggregation & Pricing Analysis Backend

## 1. Concept & Vision

A production-grade, long-running vehicle listing data collection and pricing intelligence engine. Not a script — a system. Designed for 24/7 operation with structured API outputs, intelligent pricing analysis, and clean separation between the scraping engine, the data pipeline, and the API layer. Built to own, scale, and hand over.

**Tagline the client will recognize:** *"A vehicle intelligence platform backend that never sleeps."*

---

## 2. Design Language

- **Aesthetic:** Data-first engineering tool. No marketing site — a developer dashboard and API.
- **Color palette:** Dark background (stats/logs), monospace for data outputs, accent blue for status indicators.
- **Typography:** `JetBrains Mono` for API responses; `Inter` for docs/admin.
- **Key principle:** All outputs are JSON. Terminal-friendly. Piping-friendly.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  SCRAPING ENGINE                         │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │  Playwright  │   │  Playwright  │   │  Playwright │  │
│  │  Browser #1  │   │  Browser #2  │   │  Browser #N │  │
│  └──────────────┘   └──────────────┘   └─────────────┘  │
│         ▲                ▲                   ▲            │
│         └────────────────┼───────────────────┘            │
│                    Browser Pool                          │
│                      (asyncio)                           │
└──────────────────────┬───────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  EXTRACTOR      │
              │  (parse/normalize│
              │   listing data)  │
              └────────┬────────┘
                       │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
┌────────────┐  ┌────────────┐  ┌────────────────┐
│  DEDUP     │  │  MATCHING   │  │  PRICING       │
│  ENGINE    │  │  ENGINE    │  │  ENGINE        │
└─────┬──────┘  └─────┬──────┘  └───────┬────────┘
      │                │                  │
      └────────────────▼──────────────────┘
                  │
           ┌──────▼──────┐
           │  DATABASE   │
           │  (PostgreSQL)│
           └──────┬──────┘
                  │
           ┌──────▼──────┐
           │  FASTAPI    │
           │  REST API   │
           └─────────────┘
```

---

## 4. Module Specifications

### 4.1 Browser Pool (`browser_pool.py`)

- **Responsibility:** Manages N Playwright browser instances as an async pool.
- **Interface:**
  ```python
  async def acquire() -> BrowserContext
  async def release(context: BrowserContext)
  ```
- **Behavior:** Lazy instantiation, max N concurrent contexts (env: `MAX_CONCURRENT_BROWSERS`, default 5), automatic restart on crash.
- **Anti-detection:** Rotate user-agent per request, randomize viewport, inject stealth JS.

### 4.2 Scraper Manager (`scrapers/`)

One scraper class per marketplace. Base class `BaseScraper`:

```python
class BaseScraper(ABC):
    async def scrape_listings(self, query: ScrapeQuery) -> list[RawListing]
    async def is_healthy(self) -> bool  # health check
```

Initial scrapers (at least 2):
- `AutotraderScraper` — autotrader.com
- `CarguruScraper` — cargurus.com

Each scraper:
- Inherits from `BaseScraper`
- Implements `parse_listing_page(html, url)` → `RawListing`
- Respects `robots.txt` via `robotparser` (allow-listing, not block-listing)
- Exponential backoff on HTTP errors (max 3 retries, base 2s)

### 4.3 Listing Extractor (`extractor.py`)

Normalizes raw HTML/listings into `StructuredListing`:

```python
@dataclass
class StructuredListing:
    title: str
    price: float | None          # USD, None if "Price on request"
    location: str                 # city, state
    description: str
    images: list[str]             # absolute URLs
    listing_url: str              # original listing URL
    scraped_at: datetime          # UTC
    source: str                   # e.g. "autotrader"
    vehicle: "VehicleSpec | None"

@dataclass
class VehicleSpec:
    make: str
    model: str
    year: int
    trim: str | None
    mileage: int | None
    vin: str | None
    exterior_color: str | None
    interior_color: str | None
    fuel_type: str | None
    transmission: str | None
    body_style: str | None
```

### 4.4 Deduplication Engine (`dedup.py`)

- **Strategy:** SHA-256 of normalized title + price + location + source domain → `listing_hash`
- **Storage:** PostgreSQL table `dedup_hashes(hash TEXT UNIQUE, listing_id UUID)`
- **Behavior:** If hash exists, skip insert. Re-checks every 24h for same listing re-posted.
- **Fallback:** Fuzzy dedup using `title` Levenshtein distance < 0.85 across same make/model/year within 30 days.

### 4.5 Vehicle Matching Engine (`matching.py`)

- **Input:** New `StructuredListing` with `VehicleSpec`
- **Output:** `list[SimilarListing]` — same make + model + year (±1 year tolerance)
- **Method:** SQL query on `vehicles` table with indexed `make, model, year` columns.

### 4.6 Pricing Engine (`pricing.py`)

- **Price range:** Per make/model/year bucket, compute `P5, P25, P50, P75, P95` percentiles from listings in last 90 days.
- **Classification:**
  - `underpriced`: price < P25
  - `overpriced`: price > P75
  - `fair`: within P25–P75
- **Bucket minimum:** If fewer than 5 listings in bucket, mark `insufficient_data: true`.

### 4.7 Database Schema (`schema.sql`)

```sql
-- Listings
CREATE TABLE listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    price REAL,
    location TEXT,
    description TEXT,
    images TEXT[],         -- PostgreSQL array
    listing_url TEXT UNIQUE NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    listing_hash TEXT UNIQUE NOT NULL,
    -- Vehicle spec
    vehicle_make TEXT,
    vehicle_model TEXT,
    vehicle_year INT,
    vehicle_trim TEXT,
    vehicle_mileage INT,
    vehicle_vin TEXT,
    vehicle_exterior_color TEXT,
    vehicle_fuel_type TEXT,
    vehicle_transmission TEXT,
    vehicle_body_style TEXT,
    -- Analysis
    price_percentile REAL,
    pricing_flag TEXT,     -- 'underpriced' | 'overpriced' | 'fair' | NULL
    price_bucket_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_listings_vehicle ON listings(vehicle_make, vehicle_model, vehicle_year);
CREATE INDEX idx_listings_price ON listings(price);
CREATE INDEX idx_listings_scraped_at ON listings(scraped_at);

-- Price buckets (recomputed nightly)
CREATE TABLE price_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INT NOT NULL,
    p5 REAL, p25 REAL, p50 REAL, p75 REAL, p95 REAL,
    sample_count INT,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(make, model, year)
);

-- Scrape jobs
CREATE TABLE scrape_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL,     -- 'pending' | 'running' | 'done' | 'failed'
    source TEXT,
    query TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    listings_added INT DEFAULT 0,
    error TEXT
);

-- Dedup hash registry
CREATE TABLE dedup_hashes (
    hash TEXT PRIMARY KEY,
    listing_id UUID REFERENCES listings(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.8 API Layer (`api/`)

**Framework:** FastAPI + Uvicorn

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Start a new scrape job |
| `GET` | `/api/jobs/{job_id}` | Get job status |
| `GET` | `/api/jobs` | List recent jobs |
| `GET` | `/api/listings` | Query listings (filter by make, model, year, price, location) |
| `GET` | `/api/listings/{id}` | Get single listing |
| `GET` | `/api/listings/{id}/matches` | Get similar listings |
| `GET` | `/api/price-analysis/{make}/{model}/{year}` | Get price range for vehicle |
| `GET` | `/api/sources` | List configured sources + health |
| `GET` | `/health` | Health check (DB + browser pool) |

**Query filters for `/api/listings`:**
- `make`, `model`, `year__gte`, `year__lte`
- `price__gte`, `price__lte`
- `location` (ILIKE match)
- `pricing_flag` (`underpriced`, `overpriced`, `fair`)
- `source`
- `since` (ISO timestamp — listings scraped after)
- `limit` (default 50, max 500)
- `offset` (pagination)

**Pagination:** Cursor-based via `id > last_seen_id` for efficient deep pagination.

### 4.9 Scheduler / Daemon (`daemon.py`)

- **Responsibility:** Continuous polling for new listings on configured schedules.
- **Config:** `sources.yaml` per source with `crawl_interval_hours`, `enabled: bool`, `default_query`.
- **Behavior:**
  - Cron-style scheduling per source.
  - On trigger: create `scrape_job` record, run scraper, insert listings, update job.
  - If scraper fails 3 consecutive times: pause source, alert (log warning).
- **Graceful shutdown:** SIGTERM drains active browser contexts before exit.

---

## 5. Project Structure

```
vehicle-intelligence-backend/
├── SPEC.md
├── README.md
├── requirements.txt
├── .env.example
├── docker-compose.yml          # Local dev (PostgreSQL + Redis + app)
├── Dockerfile
├── schema.sql
├── sources.yaml                 # Per-source scrape config
│
├── browser_pool.py              # Shared Playwright pool
├── extractor.py                 # Listing normalization
├── dedup.py                     # Deduplication
├── matching.py                  # Vehicle matching
├── pricing.py                   # Price analysis
├── daemon.py                    # Scheduler
│
├── scrapers/
│   ├── __init__.py
│   ├── base.py                  # BaseScraper ABC
│   ├── autotrader.py
│   └── cargurus.py
│
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + CORS
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── jobs.py
│   │   ├── listings.py
│   │   ├── price_analysis.py
│   │   └── sources.py
│   ├── models.py                # Pydantic models
│   └── database.py              # asyncpg connection pool
│
└── tests/
    ├── conftest.py
    ├── test_extractor.py
    ├── test_dedup.py
    ├── test_pricing.py
    └── test_api/
        ├── test_listings.py
        └── test_jobs.py
```

---

## 6. Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Browser automation | Playwright + Stealth | Best JS support + anti-detection |
| Async runtime | asyncio + `asyncioPool` | Concurrent browser contexts |
| Web server | FastAPI + Uvicorn | Async-native, auto-docs |
| Database | PostgreSQL 15 | JSONB support, arrays, strong text search |
| DB client | asyncpg | Async PostgreSQL driver |
| ORM/Query | raw SQL + SQLAlchemy 2.0 async | Predictable queries for analytics |
| Caching | in-process LRU (no Redis needed for MVP) | Simplicity |
| Config | Pydantic Settings + `.env` | Type-safe, 12-factor |
| Testing | pytest + pytest-asyncio + Playwright testserver | |
| Container | Docker + Docker Compose | |

---

## 7. Key Design Decisions

1. **Scraper-per-source pattern:** Each marketplace gets its own class. Adding a new source = add one file. No monolithic scraper.
2. **Browser pool over per-scraper browser:** Shared context pool prevents resource exhaustion. Max 5 concurrent.
3. **PostgreSQL over SQLite:** This needs to handle millions of rows, concurrent writers, and analytical queries (percentiles). SQLite doesn't cut it.
4. **No Redis at MVP:** Caching is in-process LRU. Redis can be added later for multi-instance deployment.
5. **Dedup at write time:** Hash inserted before commit. If dup, transaction rolls back — no orphaned listings.
6. **Price bucket recomputed nightly:** Not on every insert. Nightly batch keeps reads fast.
7. **Listing URL as unique key:** `listing_url` is the natural dedup key across re-scrapes. `listing_hash` handles same vehicle different sources.

---

## 8. Edge Cases

- **JavaScript infinite scroll:** Playwright scrolls to bottom, waits for new items to load, repeats until no new content for 3s.
- **Login/gate required:** All scrapers target publicly accessible listings. No login support at MVP.
- **Image links behind CDN:** Store absolute CDN URLs. Do not download images to disk at MVP (future: optional S3 offload).
- **Price "Call for price":** Store `price = null`, flag appropriately.
- **Missing vehicle spec:** `vehicle` field is nullable. Matching/pricing falls back to title-only if spec absent.
- **Scraper returns 0 listings:** Log warning, job marked `done` with `listings_added=0`. Not a failure.
- **Browser crash mid-job:** Pool detects dead context, spawns replacement, retries current job once.
- **Duplicate listing URL on different source:** Both stored. Cross-source dedup not attempted at MVP.

---

## 9. Acceptance Criteria

- [ ] `GET /health` returns 200 with DB pool size and browser pool status
- [ ] `POST /api/jobs` creates a scrape job and returns `job_id`
- [ ] Scraper completes without exceptions for at least 2 sources
- [ ] Listings appear in `GET /api/listings` within 60s of job completion
- [ ] `GET /api/listings/{id}/matches` returns vehicles of same make/model/year
- [ ] `GET /api/price-analysis/{make}/{model}/{year}` returns percentile breakdown
- [ ] Re-scraping same URL does not create duplicate listing
- [ ] Daemon can run continuously for 24h without memory leaks or zombie browsers
- [ ] All endpoints documented in auto-generated OpenAPI schema at `/docs`
- [ ] README.md includes complete setup instructions for a developer on a fresh machine
