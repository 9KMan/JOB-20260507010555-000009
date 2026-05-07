# Vehicle Intelligence Platform

Real-Time Listing Aggregation & Pricing Analysis Backend for Vehicle Intelligence Platform SaaS.

## Overview

This platform provides real-time vehicle listing aggregation and pricing analysis capabilities using Python, FastAPI, Playwright, and PostgreSQL.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, asyncpg
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Scraping**: Playwright for web automation
- **Container**: Docker & Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/9KMan/JOB-20260507010555-000009.git
cd JOB-20260507010555-000009

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
python -m app.core.database

# Run the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

```bash
cd docker
docker-compose up -d
```

## API Endpoints

### Vehicles

- `POST /api/v1/vehicles` - Create a new vehicle listing
- `GET /api/v1/vehicles` - List vehicles with filters
- `GET /api/v1/vehicles/{vin}` - Get vehicle by VIN
- `PUT /api/v1/vehicles/{vin}` - Update vehicle

### Pricing

- `POST /api/v1/prices` - Record a price
- `GET /api/v1/prices/{vin}/history` - Get price history
- `POST /api/v1/prices/analyze` - Analyze prices
- `POST /api/v1/pricing/market` - Get market pricing

## Configuration

Environment variables (`.env`):

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/vehicle_intel
REDIS_URL=redis://localhost:6379/0
SCRAPER_INTERVAL=300
LOG_LEVEL=INFO
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Architecture

```
app/
├── api/          # API routes
├── core/         # Core functionality (config, database, logging)
├── models/       # SQLAlchemy models
├── services/     # Business logic
└── scrapers/     # Playwright scrapers
```

## License

MIT
