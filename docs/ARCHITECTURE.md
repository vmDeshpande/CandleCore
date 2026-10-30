# CandleCore Architecture

**Status:** Approved baseline\
**Date:** 2026-10-30\
**Architecture style:** Python-first modular monolith with a separately
deployed web frontend

## 1. Mission

CandleCore is a standalone, mathematically driven market-analysis and
trade-management platform. It will process Delta Exchange market data,
identify market structures using deterministic algorithms, capture and
evaluate a discretionary trading methodology, backtest strategies and
eventually support controlled paper execution.

CandleCore does not use LLMs, generative AI, vision-language models or
token-based inference services. Machine learning is optional,
conventional and deferred until sufficient labeled observations exist.

## 2. Approved initial configuration

  -----------------------------------------------------------------------
  Concern                             Decision
  ----------------------------------- -----------------------------------
  Exchange                            Delta Exchange India

  Instruments                         BTCUSD, ETHUSD, SOLUSD

  Primary timeframe                   3m

  Trading styles                      Scalping and intraday, represented
                                      as separate strategy profiles

  Backend                             Python + FastAPI

  Frontend                            Next.js App Router + TypeScript

  Chart                               TradingView Lightweight Charts v5

  Database                            PostgreSQL

  ORM / migrations                    SQLAlchemy 2 / Alembic

  Async                               asyncio

  Numerical stack                     NumPy, Pandas; SciPy when justified

  Tests                               pytest, Hypothesis

  Deployment                          Debian Linux + systemd

  Execution                           Paper-only when introduced
  -----------------------------------------------------------------------

Other timeframes may be configured later. The initial data milestone is
limited to the approved three-minute interval unless a later decision
explicitly expands scope.

## 3. Architectural principles

-   The backend is the authority for market data, calculations,
    decisions, risk and execution state.
-   The frontend is a visualization and human-input client, not a
    trading-decision engine.
-   The perception engine must run headlessly without a browser,
    screenshot, database or exchange connection.
-   Market perception, strategy, risk and execution are separate
    modules.
-   Exchange-specific payloads remain inside the Delta adapter.
-   All event and decision timestamps are timezone-aware UTC.
-   Financial values are stored and exchanged using decimal-safe
    representations. Float64 may be used inside numerical analysis after
    an explicit conversion boundary.
-   Events are append-only where practical. Corrections create revisions
    rather than silently rewriting history.
-   Live processing and historical replay share the same domain logic.
-   All algorithm outputs are versioned and reproducible.

## 4. Logical architecture

``` mermaid
flowchart TD
    D[Delta Exchange India] --> X[Delta Adapter]
    X --> I[Ingestion and Normalization]
    I --> V[Validation and Candle Lifecycle]
    V --> P[(PostgreSQL)]
    V --> E[Market Event Publisher]
    E --> M[Market Perception Engine]
    M --> S[Strategy Engine]
    S --> R[Risk Manager]
    R --> B[Paper Broker]
    B --> P
    M --> P
    S --> P
    F[Next.js UI] <--> A[FastAPI]
    A <--> P
    E --> A
    H[Historical Replay] --> M
    H --> S
    H --> Q[Backtest Simulator]
    Q --> P
```

## 5. Component responsibilities

### 5.1 Exchange adapter

-   Calls documented Delta REST endpoints.
-   Maintains public WebSocket subscriptions.
-   Validates and parses exchange messages.
-   Normalizes exchange timestamps and symbol identifiers.
-   Handles rate limits, heartbeat, reconnect and subscription
    restoration.
-   Does not make strategy decisions.

### 5.2 Market-data subsystem

-   Persists original received payloads and normalized observations.
-   Validates OHLCV consistency.
-   Maintains provisional and finalized candle state.
-   Detects duplicates, out-of-order events and missing intervals.
-   Recovers gaps through bounded REST backfill.
-   Preserves source provenance and revisions.

### 5.3 Storage

PostgreSQL is the initial persistence layer. TimescaleDB is not required
for the first milestone. Evaluate it only if measured query or retention
workloads justify the extension and its licensing/deployment model.

### 5.4 Market Perception Engine

Pure, deterministic algorithms consume validated market observations and
emit typed events, features and annotations. Initial algorithm sequence:

1.  Swing highs and lows.
2.  Market structure.
3.  ATR and volatility.
4.  Support/resistance zones.
5.  Trendline candidates.
6.  BOS and CHoCH.
7.  Liquidity-sweep candidates.
8.  Breakout/retest state machine.
9.  Candle and volume features.
10. Multi-timeframe context.
11. Event lifecycle and invalidation.

### 5.5 Strategy Engine

-   Evaluates explicit, versioned strategy rules.
-   Separates scalping and intraday profiles.
-   Produces candidate decisions and explanations.
-   Records BUY, SELL and NO TRADE.
-   Does not submit orders or bypass risk controls.
-   Does not assume the friend's rules before evidence is captured.

### 5.6 Risk Manager

-   Validates size, exposure, loss limits and position constraints.
-   Rejects invalid or unsafe proposals.
-   Is independent from perception and strategy.
-   Cannot be bypassed by future ML filters.

### 5.7 Execution

A paper broker is introduced before any exchange execution. A future
Delta execution adapter must include local idempotency, client-order-ID
reconciliation, order/fill/position state machines, protective-order
verification and emergency shutdown. Live execution requires a separate
explicit authorization and release gate.

### 5.8 Frontend

Next.js App Router + TypeScript. It renders: - Candles and volume. -
Configurable timeframes. - Machine-generated annotations. -
Human-generated drawings. - Decision records. - Trade and risk state. -
Historical replay and analytics.

The frontend communicates with FastAPI through versioned REST and
WebSocket contracts. The browser must not be responsible for
authoritative indicator or strategy calculations.

## 6. Deployment topology

Initial deployment is a single Debian host with: - Python application
process managed by systemd. - PostgreSQL service. - Next.js process
managed by systemd or a justified Node deployment method. - Nginx
reverse proxy and TLS. - Environment-based secrets outside source
control. - Database backups and restore tests. - Structured logs and
health endpoints.

Do not add Docker, Redis, Kafka, Kubernetes or distributed services
without a measured need and an architecture decision record.

## 7. Technology choices and constraints

  -----------------------------------------------------------------------
  Technology              Role                    Policy
  ----------------------- ----------------------- -----------------------
  Python 3.12+            Backend and research    Primary

  asyncio                 Concurrent I/O          Adopt

  HTTPX                   REST client             Adopt

  websockets              WebSocket client        Adopt after contract
                                                  verification

  Pydantic                Boundary validation     Adopt

  NumPy / Pandas          Numerical analysis      Adopt

  SciPy                   Selected scientific     As needed
                          routines                

  FastAPI                 HTTP and WebSocket API  Adopt

  SQLAlchemy 2            Database access         Adopt

  Alembic                 Schema migrations       Adopt

  PostgreSQL              Persistence             Adopt

  Next.js / TypeScript    UI                      Adopt

  Lightweight Charts v5   Chart rendering         Adopt; comply with
                                                  attribution

  pytest / Hypothesis     Testing                 Adopt

  Ruff                    Lint and formatting     Adopt

  mypy or Pyright         Static typing           Select one in project
                                                  setup

  CCXT                    Potential future        Not required initially
                          exchange abstraction    

  scikit-learn / XGBoost  Optional classical ML   Deferred
  -----------------------------------------------------------------------

## 8. Non-goals for initial milestones

-   Live order execution.
-   ML-based trading decisions.
-   Automated screenshot interpretation.
-   Full TradingView charting product.
-   Multi-exchange support.
-   Multi-user tenancy.
-   Distributed event streaming.
-   High-frequency/low-latency colocated execution.
-   Claims that a detected wick proves institutional stop hunting.

## 9. Key design risks

1.  Pivot confirmation delay and repainting.
2.  Incomplete trade-feed reconstruction.
3.  Exchange candle revisions and timestamp semantics.
4.  False precision in manually reconstructed screenshot labels.
5.  Strategy overfitting to a small number of examples.
6.  OHLC intrabar ambiguity in backtests.
7.  Delta product-specific contract, fee, funding and margin mechanics.
8.  Scalping and intraday rules being incorrectly collapsed into one
    profile.
9.  Frontend chart overlays becoming coupled to the perception engine.
10. Data corrections or missing intervals contaminating historical
    evaluation.
