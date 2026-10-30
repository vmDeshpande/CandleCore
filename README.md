# CandleCore

CandleCore is a deterministic, explainable, Python-first market-data and algorithmic trading platform.

CC-M1 (this milestone) delivers the **market-data foundation**: historical backfill, real-time WebSocket collection, raw-event and candle persistence, candle lifecycle with revisions, gap detection/recovery, and database-backed HTTP APIs — all for Delta Exchange India public market data.

No exchange credentials are required for CC-M1 public market-data collection. No trading, strategies, indicators, or private APIs are implemented in this milestone.

## Architecture

CandleCore is organized into clear service boundaries:

- `src/candlecore/core/` — configuration (Pydantic v2 settings), structured logging, Decimal utilities, timestamp normalization, domain contracts.
- `src/candlecore/exchange/delta/` — Delta Exchange India clients:
  - `rest_client.py` — historical candle downloader with pagination, retry (bounded exponential backoff + jitter), HTTP 429 `Retry-After`, 5xx/timeout/network handling.
  - `ws_client.py` — candlestick WebSocket collector with per-symbol health, heartbeat/timeout, reconnect/resubscribe, and no duplicate connections.
  - `schemas.py` — Pydantic v2 response and candle schemas.
- `src/candlecore/market_data/` — domain processing:
  - `normalization.py` — REST/WS message → normalized candle update with OHLCV validation.
  - `lifecycle.py` — candle lifecycle engine (OPEN/PROVISIONAL/FINALIZED/RECONCILED/CORRECTED/INVALID), duplicate handling, revision preservation.
- `src/candlecore/storage/` — SQLAlchemy 2 models, async database session/engine lifecycle, and repositories.
- `src/candlecore/application/` — orchestration: ingestion pipeline, gap recovery service, application lifecycle (startup/shutdown).
- `src/candlecore/api/` — FastAPI application with database-backed endpoints.

## CC-M1 collection scope

- Exchange: Delta Exchange India
- Symbols: BTCUSD, ETHUSD, SOLUSD
- Timeframe: 3m (collection interval only — not a platform-wide primary timeframe)

## Repository structure

```
CandleCore/
├── alembic/                  # Alembic migration configuration + versions
├── src/candlecore/           # Python package
│   ├── api/                  # FastAPI app + routes + deps
│   ├── application/          # ingestion, gap recovery, orchestrator
│   ├── core/                 # config, contracts, logging, timestamps, decimal utils
│   ├── exchange/delta/       # REST client, WS client, schemas
│   ├── market_data/          # normalization, candle lifecycle
│   └── storage/              # database, models, repositories
├── tests/                    # unit, contract, integration tests
├── pyproject.toml            # project metadata + dependencies
├── alembic.ini               # Alembic configuration
├── .env.example              # example environment configuration
└── README.md
```

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- PostgreSQL 14+ (for persistence; Alembic migrations target PostgreSQL)
- Delta Exchange India public endpoints (no credentials needed for CC-M1)

## Installation

```bash
# Clone the repository
cd CandleCore

# Sync dependencies and create the uv-managed virtual environment
uv sync

# Activate the virtual environment (PowerShell)
.venv\Scripts\Activate.ps1
```

## Environment setup

Copy `.env.example` to `.env` and adjust values as needed:

```bash
cp .env.example .env
```

Edit `.env` to set `DATABASE_URL` to your PostgreSQL instance. The remaining defaults target the Delta Exchange India public endpoints and the CC-M1 collection scope (BTCUSD, ETHUSD, SOLUSD @ 3m).

## PostgreSQL setup

Create the database and user referenced by `DATABASE_URL`:

```sql
CREATE DATABASE candlecore;
CREATE USER candlecore WITH PASSWORD 'candlecore';
GRANT ALL PRIVILEGES ON DATABASE candlecore TO candlecore;
```

The application creates its tables via Alembic migrations on startup; no manual table creation is required.

## Alembic migrations

CandleCore uses Alembic with SQLAlchemy 2. The initial migration is tracked in `alembic/versions/0001_initial_schema.py`.

Generate/check migrations:

```bash
uv run alembic heads
uv run alembic upgrade head --sql     # preview SQL without a database
uv run alembic upgrade head           # apply migrations (requires PostgreSQL)
uv run alembic downgrade -1           # downgrade one revision
```

## Running the API

The canonical FastAPI entry point is `src/candlecore/api/main.py`:

```bash
uv run uvicorn candlecore.api.main:app --reload
```

or

```bash
uv run uvicorn candlecore.api.main:app --host 0.0.0.0 --port 8000
```

The API serves:

- `GET /api/v1/health` — application, database, and collector health
- `GET /api/v1/market/status` — exchange, symbols, connection status, per-symbol health, ingestion progress, recovery status
- `GET /api/v1/market/candles` — stored candles (symbol, timeframe, start, end, limit)
- `GET /api/v1/market/gaps` — stored data gaps (symbol, timeframe, fill status)

All endpoints are backed by PostgreSQL; none return hardcoded or placeholder data.

## Starting the collector

The WebSocket collector is wired through the application orchestrator and started as part of the FastAPI application lifespan. It subscribes to `candlestick_3m` for BTCUSD, ETHUSD, and SOLUSD, tracks per-symbol last-message time independently, and reconnects with bounded exponential backoff plus jitter.

## Historical backfill

The REST historical downloader (`DeltaRestClient.get_candles_chunked`) fetches candles in bounded chunks (max 2,000 per request), deduplicates by candle time, normalizes to ascending chronological order, and handles overlapping chunk boundaries. It is usable by both initial backfill and gap recovery.

## Gap recovery

The gap recovery service detects missing candle intervals per exchange/symbol/timeframe (excluding the current incomplete candle), persists detected gaps, recovers missing data via REST backfill, normalizes and persists recovered candles, and marks gaps filled only after successful verification. Checkpoints are updated only after successful processing so recovery can resume after restart.

## Running tests

```bash
uv run pytest
uv run pytest --cov=candlecore
```

Unit and contract tests run without a live exchange or database (they use mocked exchange clients). Integration tests in `tests/integration/` require a PostgreSQL instance reachable via `CANDLECORE_TEST_DATABASE_URL` (default `postgresql+asyncpg://candlecore:candlecore@localhost:5432/candlecore_test`); they skip when PostgreSQL is unavailable.

## Code quality

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run alembic upgrade head
```

## Troubleshooting

- **Alembic cannot connect** — ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct. Alembic strips the `+asyncpg` driver for synchronous migrations (uses `psycopg2-binary`).
- **Import errors** — run `uv sync` to install dependencies and activate the virtual environment.
- **Tests skipped** — integration tests skip when PostgreSQL is unavailable; this is expected in environments without a database.

## License

Private / internal.
