# CandleCore Technical Specification

**Version:** 0.1\
**Status:** Approved architecture baseline; detailed exchange contract
verification remains a CC-M1 gate\
**Date:** 2026-10-30

## 1. Purpose and scope

This document defines the initial technical contracts for CandleCore. It
is intentionally more specific than the research report, but does not
invent the friend's trading rules or unverified Delta message fields.

### Approved configuration

-   Exchange: Delta Exchange India.
-   Symbols: BTCUSD, ETHUSD, SOLUSD.
-   Primary interval: 3m.
-   Trading styles: scalping and intraday, separated into independently
    configurable profiles.
-   Backend: Python + FastAPI.
-   Frontend: Next.js + TypeScript.
-   Chart: TradingView Lightweight Charts v5.
-   Database: PostgreSQL.
-   Deployment target: Debian + systemd.
-   Execution: paper-only when introduced.

## 2. System invariants

1.  Internal timestamps are timezone-aware UTC.
2.  Exchange timestamps, local receive timestamps and processing
    timestamps are distinct.
3.  Every event that requires future bars for confirmation records both
    event time and confirmation time.
4.  No algorithm may use data unavailable at its historical decision
    time.
5.  A finalized candle is immutable in-place. Corrections are revisions.
6.  Source identity is retained: exchange candle, locally aggregated
    trade candle, mark-price candle and any other feed must not be
    conflated.
7.  OHLCV is validated before canonical use.
8.  Financial values at exchange and persistence boundaries use
    decimal-safe parsing and representation.
9.  Numerical algorithms may use float64 internally with documented
    conversion and tolerances.
10. Live and replay execution call the same perception and strategy
    implementation.
11. Strategy cannot bypass risk controls.
12. No order submission in CC-M1.
13. Screenshots are evidence for human annotation and comparison, not
    numerical market input to perception.
14. Ambiguous source labels remain ambiguous; they are not silently
    promoted to ground truth.

## 3. Delta Exchange integration

### 3.1 Documented historical endpoint

India API base URL:

`https://api.india.delta.exchange`

Historical candles:

`GET /v2/history/candles`

Query parameters: - `resolution` - `symbol` - `start` - `end`

The official documentation states that `start` and `end` are Unix
timestamps in seconds, and a response contains at most 2,000 candles.
The documentation lists `3m` as a supported resolution.

The downloader must therefore: - Split large ranges into bounded windows
that cannot exceed the documented response cap. - Use overlapping
boundary windows where needed to avoid gaps caused by
inclusive/exclusive endpoint semantics. - Deduplicate by canonical
candle identity. - Verify actual response ordering and boundary
semantics with captured contract fixtures. - Never assume a request
returned the entire requested interval. - Record the request window,
response metadata, retrieval time and raw payload.

### 3.2 Public WebSocket

Public endpoint:

`wss://public-socket.india.delta.exchange`

Initial subscription target: - Channel: `candlestick_3m` - Symbols:
`BTCUSD`, `ETHUSD`, `SOLUSD`

Before collector acceptance, verify using official documentation and
captured messages: - Exact subscribe and unsubscribe envelope. - Exact
candle payload schema. - Timestamp unit and meaning. - Whether updates
are repeated provisional snapshots or finalized events. - Heartbeat
message and timeout requirements. - Server-side connection and
subscription limits. - Reconnect and resubscribe behaviour. - Error
message shapes.

Do not copy example payloads from the research report into production
models without validating them against current official documentation
and captured fixtures.

### 3.3 Timestamp normalization

Use an explicit parser per source field. Never infer seconds,
milliseconds, microseconds or nanoseconds from magnitude alone in
production.

Store: - `event_time`: exchange-reported event/candle time. -
`received_at`: local UTC time when bytes/message were received. -
`processed_at`: local UTC time after parsing/validation. -
`candle_open_time`: normalized UTC interval start. - `finalized_at`:
local/derived time when CandleCore finalized the bar.

Keep original timestamp integer and unit in raw event metadata for
audit.

### 3.4 Product metadata

Do not hardcode price tick size, quantity step, contract multiplier,
minimum order size, margin mode, funding schedule or contract type.
Retrieve and version the relevant product metadata from the exchange and
bind each order/risk calculation to a metadata version. Product metadata
is a later execution prerequisite; market-data collection still records
the approved symbols.

## 4. Market-data architecture

### 4.1 Data sources

Initial milestone: - Exchange-provided traded-price 3m candles.

Later, subject to official channel verification: - Public trade feed for
independent local candle construction. - Order-book feed for spread,
depth and execution research. - Mark-price observations for
risk/liquidation analysis, stored separately.

Do not claim locally constructed candles are complete unless the trade
stream's completeness and recovery semantics are proven. Exchange
candles remain a separately stored source.

### 4.2 Candle lifecycle

Recommended internal states:

  ---------------------------------------------------------------------
  State                              Definition
  ---------------------------------- ----------------------------------
  `OPEN`                             Current interval is being built

  `PROVISIONAL`                      Exchange has supplied a
                                     current/in-progress snapshot

  `FINALIZED`                        Candle is closed according to
                                     documented interval and grace
                                     rules

  `RECONCILED`                       Compared with REST history

  `CORRECTED`                        A later authoritative observation
                                     differs; new revision recorded

  `INVALID`                          Fails validation
  ---------------------------------------------------------------------

Finalization policy must define: - UTC interval alignment. - Interval
close boundary. - Grace period. - Late-message policy. - REST
reconciliation window. - Revision policy.

Do not assume an exchange update is final merely because it is the
latest message received.

### 4.3 Candle validation

For each candle: - `high >= max(open, close)` -
`low <= min(open, close)` - `high >= low` - OHLC values are finite and
positive where instrument rules require. - Volume is nonnegative. -
Symbol and resolution are recognized. - Candle open time aligns with the
configured interval, subject to verified exchange semantics. - Duplicate
identity is detected. - Conflicting observations are recorded as
revisions or discrepancies.

### 4.4 Recovery

On startup or reconnect: 1. Load the last persisted candle/event
watermark for each symbol and timeframe. 2. Establish WebSocket and
subscribe. 3. Buffer incoming updates while the REST gap is checked. 4.
Request historical candles covering the uncertain range, respecting the
2,000-candle cap. 5. Validate and persist recovered candles. 6.
Deduplicate buffered and recovered observations. 7. Reconcile
overlapping candles. 8. Advance the watermark only when continuity
checks pass. 9. Resume normal publication.

The implementation must avoid a race where a live update is overwritten
by an older REST response.

### 4.5 Out-of-order and duplicate events

-   Raw events are retained with a stable local ingestion ID.
-   If the exchange provides a reliable event identifier or sequence,
    use it; otherwise use a documented payload fingerprint for duplicate
    detection.
-   Do not assume a sequence number exists.
-   Buffer or quarantine out-of-order events according to source
    semantics.
-   A late candle update may revise a provisional candle.
-   A correction to a finalized candle creates a new revision and emits
    a correction event.
-   Per-symbol/timeframe watermarks describe the latest continuous
    finalized interval.

### 4.6 Canonical data identity

For exchange candles, use a unique key such as:

`(exchange, symbol, timeframe, candle_open_time, source)`

Keep source in the key so exchange candles and local trade-derived
candles cannot overwrite one another.

## 5. Core data contracts

The following are conceptual Python contracts. Concrete
Pydantic/SQLAlchemy definitions are implementation work.

### 5.1 Market event

``` python
class MarketEvent:
    event_id: UUID
    exchange: str
    symbol: str
    event_type: str
    source: str
    event_time: datetime
    received_at: datetime
    processed_at: datetime
    original_timestamp: int | None
    original_timestamp_unit: str | None
    sequence: int | None
    schema_version: int
    payload: dict
```

### 5.2 Candle observation

``` python
class Candle:
    exchange: str
    symbol: str
    timeframe: str
    source: str
    candle_open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    state: CandleState
    revision: int
    first_received_at: datetime
    last_received_at: datetime
    finalized_at: datetime | None
    reconciled_at: datetime | None
```

### 5.3 Perception event

``` python
class PerceptionEvent:
    event_id: UUID
    algorithm: str
    algorithm_version: str
    config_hash: str
    symbol: str
    timeframe: str
    event_type: str
    event_time: datetime
    confirmed_at: datetime
    invalidated_at: datetime | None
    status: str
    input_event_ids: list[UUID]
    payload: dict
```

### 5.4 Human annotation

``` python
class HumanAnnotation:
    annotation_id: UUID
    symbol: str
    timeframe: str
    annotation_type: str
    author_id: str
    created_at: datetime
    market_time_start: datetime | None
    market_time_end: datetime | None
    price_low: Decimal | None
    price_high: Decimal | None
    anchor_points: list[dict]
    rationale: str | None
    source_asset_id: UUID | None
    timestamp_confidence: str
    price_coordinate_confidence: str
    revision: int
```

### 5.5 Decision record

``` python
class StrategyDecision:
    decision_id: UUID
    symbol: str
    timeframe: str
    profile: str  # SCALPING or INTRADAY
    decision_time: datetime
    decision: str  # BUY, SELL, NO_TRADE
    entry_plan: dict | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    rationale: str | None
    accepted_or_rejected: str | None
    evidence_ids: list[UUID]
    label_provenance: str
    label_confidence: str
```

## 6. Database baseline

Use PostgreSQL. Use SQLAlchemy 2 and Alembic.

Initial logical tables: - `exchange_products` - `raw_market_events` -
`market_trades` (later, when trade feed is integrated) - `candles` -
`candle_revisions` - `data_gaps` - `ingestion_checkpoints` -
`source_assets` - `human_annotations` - `machine_annotations` -
`perception_events` - `strategy_decisions` - `orders` (later) - `fills`
(later) - `positions` (later) - `risk_events` (later)

Use UUID primary keys where useful, UTC `TIMESTAMPTZ`, numeric/decimal
columns for persisted financial values, JSONB for versioned metadata,
and explicit foreign keys. Avoid using a single generic JSON table for
all domain entities.

For candle uniqueness, enforce a unique constraint over the canonical
source identity. Store corrections in `candle_revisions` or a clearly
versioned observation table. Do not overwrite the only historical copy.

## 7. Market Perception Engine

The perception package must be deterministic and testable without I/O.
Every algorithm declares: - Mathematical definition. - Input schema. -
Output schema. - Parameters and defaults. - Confirmation timing. -
Invalidation rules. - Edge cases. - Complexity expectations. - Unit and
replay tests. - Known limitations.

### 7.1 Swing detection

Use a configurable left/right pivot window. A pivot at index `i` is not
knowable until the right-side confirmation bars close.

For a swing high: - Candidate high must satisfy the documented
left-neighbour condition. - It must satisfy the right-neighbour
condition. - Tie handling must be explicit (e.g. deterministic
first/last plateau policy). - Optional prominence filter may use ATR or
tick-normalized distance.

Record `event_time` at the pivot bar and `confirmed_at` at the close of
the final required right-side bar. The backtester must not expose the
pivot to strategy logic before confirmation.

### 7.2 Market structure

Classify confirmed highs/lows into HH, LH, HL and LL. Define
equal-high/equal-low tolerance using tick size or a documented
volatility-normalized tolerance. Support neutral, range and
transitioning states; do not force every observation into
bullish/bearish.

### 7.3 Volatility

Implement ATR and selected realized-volatility measures with explicit
warm-up and missing-data behaviour. Indicator values must be calculated
from data available at the decision timestamp.

### 7.4 Support/resistance

Create candidate zones from confirmed pivots. Use a
volatility-normalized distance metric, but define deterministic
clustering and merge/split rules. Track touches, reaction size, age,
recency, width and invalidation. Do not use K-means with an arbitrary
cluster count as the default production method.

### 7.5 Trendlines

Generate candidates from confirmed swing anchors. Validate using touch
count, normalized residual, intervening price violations, slope and age.
Regression trendlines are statistical descriptors and must not
automatically be labelled discretionary support/resistance.

### 7.6 BOS and CHoCH

Define the structural reference before the break. Distinguish wick
penetration, candle-close confirmation and optional volatility-buffer
confirmation. BOS is a break aligned with the established directional
structure; CHoCH is a qualifying break against it. Store the reference
event and confirmation time.

### 7.7 Liquidity sweep candidates

A candidate bearish sweep of resistance `R` may require
`high > R + epsilon` and `close < R`; bullish support sweep is
symmetric. `epsilon`, reference-level age, close location and optional
volume filters must be configurable. The event is a price-pattern
classification, not proof of institutional intent or stop hunting.

### 7.8 Breakout and retest

Use a state machine:
`UNBROKEN -> BREAKOUT_CANDIDATE -> BREAKOUT_CONFIRMED -> WAITING_FOR_RETEST -> RETEST_CANDIDATE -> RETEST_CONFIRMED`,
with `FAILED_BREAKOUT` and expiry transitions. A single close beyond a
zone is not automatically a high-quality breakout.

### 7.9 Candle, volume and momentum features

Begin with explicit body/wick/range ratios, relative volume, rolling
median/mean, ATR, EMA, RSI and rate of change. Features are descriptive
until the friend's rules establish their meaning.

### 7.10 Multi-timeframe context

Higher-timeframe features must use only candles finalized by the
decision time. A still-forming 15m or 1h candle cannot leak its eventual
close into a historical 3m decision.

### 7.11 Event lifecycle

Use explicit states such as `DETECTED`, `CONFIRMED`, `ACTIVE`,
`INVALIDATED`, `EXPIRED`. Store every state transition with timestamp,
reason, algorithm version and relevant evidence.

## 8. Chart and annotation architecture

### 8.1 Frontend structure

Use Next.js App Router + TypeScript. Charting components are client-side
components because Lightweight Charts uses browser rendering. Keep data
loading, authentication and page composition aligned with Next.js
server/client component boundaries.

### 8.2 Lightweight Charts

Use Lightweight Charts v5. Use: - Candlestick series for traded-price
OHLC. - Histogram or appropriate series for volume. - Series primitives
for drawings tied to series/time-price scales. - Pane primitives for
pane-level overlays. - Custom series only when an annotation is better
represented as its own data series.

Comply with the library's Apache-2.0 license and TradingView attribution
requirement. Verify current package APIs before coding; do not rely on
outdated v4 examples.

### 8.3 Annotation provenance

Every annotation has a source: `SYSTEM` or `HUMAN`. Machine annotations
include algorithm version, configuration hash and input event IDs. Human
annotations include author, revision history and optional source
screenshot asset. Never merge or overwrite machine and human drawings.

### 8.4 Screenshot and trade-record ingestion

Historical source material is registered as an asset with: - Asset ID
and file hash. - Original filename and source. - Known
symbol/timeframe. - Known capture timestamp or an explicit unknown
value. - Associated trade-record IDs. - Extraction method and
reviewer. - Confidence and unresolved ambiguities.

A human review interface links screenshot coordinates to chart
time/price anchors. Do not assume screenshot pixel coordinates
correspond exactly to chart values without calibration. If the visible
axes, time range or price scale are insufficient, store
approximate/unknown coordinates and lower confidence.

Trade records should be imported with original fields, source and
mapping notes. Do not infer missing entry, exit, stop or decision
timestamps.

### 8.5 Comparison metrics

Potential comparisons include: - Price-zone intersection-over-union. -
Anchor price error normalized by ATR/tick size. - Time displacement. -
Detection-to-human annotation delay. - Zone persistence and subsequent
reaction. - Human relevance rating.

No single geometric metric should be treated as a full measure of
trading judgment.

## 9. Strategy and profile design

Scalping and intraday are separate strategy profiles that can share
perception outputs. Each profile has explicit: - Eligible
symbols/timeframes. - Entry conditions. - Confirmation rules. -
Invalidation conditions. - Exit logic. - Maximum holding duration. -
Risk budget. - Session or market-state filters, if the trader actually
uses them.

The friend's strategy rules are unknown until the historical records and
screenshots are reviewed. Do not implement example EMA/RSI rules from
the research report as if they were his strategy.

Record BUY, SELL and NO TRADE, plus accepted and rejected opportunities.
Include winning and losing trades and rejected opportunities that later
moved favourably or unfavourably.

## 10. Backtesting

The backtester replays market events chronologically and invokes the
same perception and strategy modules as live operation.

Required modelling before performance claims: - Trading fees and
maker/taker classification. - Slippage. - Funding cash flows. - Partial
fills. - Order types and latency assumptions. - Intrabar stop/target
ambiguity. - Position sizing. - Contract multiplier and settlement
mechanics. - Margin and liquidation where relevant. - Exchange-specific
tick and quantity increments.

If one OHLC candle touches both stop and target and sequence is unknown,
use lower-resolution trades/candles where available or a conservative
documented assumption. Never assume the favourable fill.

Use chronological train/validation/test windows and walk-forward
evaluation. Keep parameter selection separate from final out-of-sample
evaluation. Report net risk-adjusted performance, drawdown, expectancy,
profit factor, exposure, costs and regime stability---not win rate
alone.

## 11. Risk and execution

Risk is a separate deterministic gate. It validates proposed orders
against: - Maximum position and notional exposure. - Maximum loss and
daily loss limits. - Position and symbol limits. - Available margin and
leverage constraints. - Stop-loss and take-profit validity. - Exchange
tick/quantity constraints. - Current order and position reconciliation
state. - Kill-switch and manual disable state.

Paper broker first. Future exchange execution must use client order IDs
plus a local idempotency ledger. A timeout is ambiguous: query the
original client order ID and reconcile before retrying. Never blindly
resubmit. Protective orders must be verified at the exchange. Emergency
shutdown and manual intervention are required.

## 12. API outline

Initial read-only API: - `GET /api/v1/health` -
`GET /api/v1/market/candles?symbol=BTCUSD&timeframe=3m&from=...&to=...` -
`GET /api/v1/market/status` -
`GET /api/v1/market/gaps?symbol=BTCUSD&timeframe=3m` - WebSocket
`/api/v1/stream/market`

Use UTC ISO-8601 timestamps in API JSON. Define pagination and maximum
query ranges. Validate symbols/timeframes. Do not expose exchange
credentials.

Later APIs: - Annotation CRUD. - Human decision records. - Perception
events. - Replay. - Backtest runs. - Paper positions and orders. - Risk
events.

## 13. Observability and operations

Structured logs should include correlation/event IDs, symbol, timeframe,
source, timestamps, and processing stage. Do not log API secrets.

Expose health/readiness checks for: - Process. - Database. - Delta
WebSocket connection. - Subscription state. - Last received event per
symbol. - Last finalized candle per symbol/timeframe. - Data-gap
status. - Recovery state.

Alert on stale feeds, persistent gaps, repeated reconnects, database
write failures and clock drift.

## 14. Testing requirements

-   Unit tests for normalization, timestamp conversion, candle
    validation and lifecycle.
-   Contract tests using captured Delta REST/WS fixtures.
-   Integration tests with PostgreSQL.
-   Fault tests for reconnect, duplicate, out-of-order, malformed
    payload, timeout and database interruption.
-   Replay tests for deterministic recovery and candle sequencing.
-   Property-based tests for OHLC invariants and interval alignment.
-   Migration upgrade tests.
-   No acceptance based only on a successful manual run.

## 15. CC-M1 exit criteria

CC-M1 is complete only when: 1. Historical 3m data is downloaded for all
three approved symbols. 2. REST windows respect the 2,000-candle
response cap. 3. The live collector subscribes to all three symbols. 4.
Payloads and timestamp units are verified against official docs and
captured fixtures. 5. Raw messages and normalized candle observations
are persisted. 6. Candle lifecycle and correction behaviour are tested.
7. Duplicates and out-of-order messages are handled. 8. A simulated
disconnect causes bounded REST recovery. 9. REST recovery cannot
overwrite newer live observations. 10. Missing intervals are detectable
and auditable. 11. API returns historical candles in UTC. 12. Restart is
safe and idempotent. 13. Unit, contract and integration tests pass. 14.
No strategy or order execution code is present in the milestone.

## 16. External references to re-check at implementation time

-   Delta Exchange API documentation: https://docs.delta.exchange/
-   Delta India API base URL: https://api.india.delta.exchange
-   Delta public WebSocket endpoint:
    `wss://public-socket.india.delta.exchange`
-   Lightweight Charts repository, current API and license:
    https://github.com/tradingview/lightweight-charts
-   Lightweight Charts plugin documentation:
    https://tradingview.github.io/lightweight-charts/docs/plugins/intro
-   Next.js App Router documentation: https://nextjs.org/docs/app
-   Next.js TypeScript documentation:
    https://nextjs.org/docs/app/api-reference/config/typescript

These references are not substitutes for contract tests. Re-verify
current endpoint details, message schemas, timestamp semantics, limits,
package versions and licensing immediately before implementation.
