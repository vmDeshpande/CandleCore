# Kilo Implementation Prompt --- CandleCore CC-M1

You are implementing **CC-M1: Reliable Market Data Foundation** for
CandleCore.

Read these files completely before changing anything:

-   `README.md`
-   `docs/ARCHITECTURE.md`
-   `docs/TECHNICAL_SPECIFICATION.md`
-   `docs/ROADMAP.md`
-   `docs/DECISIONS.md`

The documents are the approved project requirements. If they conflict,
stop and report the conflict rather than inventing a resolution.

## Project identity and hard constraints

CandleCore is a completely new, standalone Python-first project.

-   Do not reuse, copy, fork, import or depend on any other repository.
-   Do not introduce LLMs, generative AI, VLMs, model APIs or GPU
    inference.
-   Do not implement strategy rules, indicators for trading, order
    placement or execution in this milestone.
-   Do not add unnecessary microservices, Redis, Kafka, Kubernetes or
    TimescaleDB.
-   Do not hardcode exchange product precision or invent API payload
    fields.
-   Use UTC internally.
-   Preserve raw source payloads and provenance.
-   Do not silently mutate finalized candles.
-   No live trading. In fact, no order-related code belongs in CC-M1.

## Approved initial scope

-   Exchange: Delta Exchange India.
-   Symbols: BTCUSD, ETHUSD, SOLUSD.
-   Timeframe: 3m only for CC-M1.
-   REST historical endpoint:
    `GET https://api.india.delta.exchange/v2/history/candles`.
-   REST parameters: `resolution`, `symbol`, `start`, `end`.
-   REST `start` and `end`: Unix seconds.
-   REST maximum response: 2,000 candles.
-   Public WebSocket: `wss://public-socket.india.delta.exchange`.
-   Initial WebSocket channel: `candlestick_3m`.
-   Backend: Python + FastAPI.
-   Database: PostgreSQL.
-   ORM: SQLAlchemy 2.
-   Migrations: Alembic.
-   Async I/O: asyncio.
-   HTTP: HTTPX.
-   Tests: pytest; use Hypothesis for properties where useful.
-   Tooling: Ruff and one static type checker (mypy or Pyright; document
    the choice).

## Step 0 --- API contract verification before implementation

Use current official Delta Exchange India documentation. Do not rely
solely on the example payload in the supplied research report.

Verify and document: 1. Exact WebSocket connection and subscribe
envelope. 2. Exact `candlestick_3m` message schema. 3. Timestamp field
meaning and unit. 4. Whether messages are provisional updates, final
candles or both. 5. Heartbeat and timeout behaviour. 6. Reconnect and
resubscribe requirements. 7. REST candle ordering and boundary
semantics. 8. Error and rate-limit response formats. 9. Whether product
metadata is required for interpreting these market-data fields.

Save sanitized real response examples as contract fixtures. Never
include API secrets. If any contract cannot be verified, isolate it
behind an adapter interface and report the blocker; do not guess.

## Step 1 --- Repository scaffold

Create a clean project using a `src/` layout:

``` text
src/candlecore/
  core/
  exchange/delta/
  market_data/
  storage/
  api/
  application/
tests/
  unit/
  integration/
  contract/
  fixtures/
docs/
scripts/
```

Create: - `pyproject.toml` - dependency lock file using the selected
Python package manager - `.env.example` - `.gitignore` - README with
setup/run/test instructions - Alembic configuration - settings
validation - structured logging configuration

Do not add unused dependencies.

## Step 2 --- Domain contracts

Implement typed contracts for: - Raw market event. - Normalized exchange
candle update. - Candle observation. - Candle state. - Data gap. -
Ingestion checkpoint. - Recovery result.

Keep exchange wire schemas separate from internal domain models.
Preserve original timestamps and units alongside normalized UTC values.

Use Decimal-safe parsing for persisted OHLCV values. If numerical
conversion to float is needed, make it explicit and do not use float
values as financial identity keys.

## Step 3 --- Delta REST client

Implement a narrow, async HTTPX client.

Requirements: - Configurable base URL and timeouts. - Bounded retries
only for safe/idempotent GET requests. - Exponential backoff with jitter
for transient failures and rate limits. - Respect server retry guidance
when provided. - Validate response envelope and candle rows. - Split
historical ranges so each request cannot exceed 2,000 candles. - Handle
inclusive/exclusive boundaries using verified behaviour. - Deduplicate
overlapping windows. - Detect incomplete responses and missing
intervals. - Store request parameters and retrieval time. - Never assume
a successful HTTP status means the response is semantically valid.

Provide unit tests with mocked HTTP responses and contract tests with
sanitized official response fixtures.

## Step 4 --- Delta public WebSocket collector

Implement an asyncio-compatible client.

Requirements: - One persistent connection where possible; no reconnect
storm. - Subscribe to BTCUSD, ETHUSD and SOLUSD on `candlestick_3m`. -
Validate every message against the verified wire schema. - Heartbeat
handling exactly as documented. - Reconnect with exponential backoff and
jitter. - Restore subscriptions after reconnect. - Track last message
time per symbol. - Handle malformed messages without crashing the
process. - Preserve raw message payloads. - Expose connection and
subscription health. - Support graceful shutdown.

Do not invent a sequence number if Delta does not provide one. Do not
infer timestamp units from magnitude in the production parser.

## Step 5 --- Candle lifecycle and recovery

Implement: - Candle identity and source. - Provisional update
handling. - Finalization policy with documented UTC interval boundary
and grace period. - Late update handling. - Correction/revision
records. - Duplicate detection. - Out-of-order update handling. -
Per-symbol/timeframe watermark. - Gap detection. - REST backfill after
startup and disconnect. - Merge logic that cannot let stale REST data
overwrite newer live observations.

Keep exchange candle observations distinct from any future locally
aggregated trade candles.

## Step 6 --- PostgreSQL persistence

Use SQLAlchemy 2 and Alembic.

Initial tables: - `raw_market_events` - `candles` - `candle_revisions` -
`data_gaps` - `ingestion_checkpoints`

Use: - UTC `TIMESTAMPTZ`. - Decimal-capable numeric columns. -
Appropriate indexes and unique constraints. - Foreign keys where
appropriate. - Explicit transaction boundaries. - Idempotent persistence
operations.

Do not store every domain object as an unstructured JSON blob. JSONB is
acceptable for raw payloads and versioned metadata.

Test migration from an empty database and migration upgrade behaviour.

## Step 7 --- FastAPI read-only endpoints

Implement: - `GET /api/v1/health` - `GET /api/v1/market/status` -
`GET /api/v1/market/candles` - `GET /api/v1/market/gaps`

Requirements: - Validate symbol and timeframe. - Use UTC ISO-8601 in
responses. - Bound date range and result count. - Stable chronological
ordering. - Clear error responses. - No credentials in responses. - No
order or trade submission routes.

WebSocket streaming may be implemented only after the normalized event
contract is stable.

## Step 8 --- Testing and fault injection

Required tests: - Timestamp conversion and unit preservation. - Candle
OHLC invariants. - Interval alignment. - Duplicate messages. -
Out-of-order messages. - Provisional candle updates. - Finalization
boundary. - Late correction and revision. - REST response cap and window
splitting. - Overlapping REST windows. - Missing candle detection. -
WebSocket disconnect/reconnect. - Subscription restoration. - Heartbeat
timeout. - Malformed payload. - Rate-limit and transient HTTP errors. -
Database interruption and restart. - REST recovery racing with live
messages. - Idempotent persistence. - FastAPI query validation. -
Migration tests.

Use deterministic clocks in tests; avoid sleeps where possible.

## Step 9 --- Operational documentation

Document: - Environment variables. - Local PostgreSQL setup. - Database
migrations. - Running historical backfill. - Starting the collector. -
Health checks. - Logs. - Recovery behaviour. - Known API limitations. -
How to replay contract fixtures. - How to stop the process safely.

## Acceptance criteria

CC-M1 is complete only when: 1. Historical 3m candles download for
BTCUSD, ETHUSD and SOLUSD. 2. Every REST window respects the
2,000-candle cap. 3. Live WebSocket updates are received for all three
symbols. 4. Wire schemas and timestamp units are verified and
fixture-tested. 5. Raw events and normalized candles persist. 6. Candle
state transitions are tested. 7. Duplicate and out-of-order events are
handled. 8. Missing intervals are detected. 9. Reconnect triggers
bounded historical recovery. 10. Stale REST data cannot overwrite newer
live state. 11. Corrections are preserved as revisions. 12. FastAPI
returns correct UTC historical candles. 13. Process restart is safe and
idempotent. 14. Unit, contract and integration tests pass. 15. Lint and
static type checks pass. 16. No strategy, risk, order or execution
implementation is introduced.

## Required final report

At completion, report: - Files created/changed. - Architecture
implemented. - Exact Delta API contracts verified, with official
documentation URLs. - Dependencies and versions. - Database schema and
migration result. - Tests run and results. - Any known limitations. -
Acceptance criteria passed/failed. - Exact commands to run the service
locally.

Do not claim completion if an acceptance criterion has not been
demonstrated. Do not proceed to CC-M2 without review and approval.
