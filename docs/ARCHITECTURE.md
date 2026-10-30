# CandleCore Architecture

**Status:** Approved baseline\
**Date:** 2026-10-30\
**Architecture style:** Python-first modular monolith with a separately
deployed web frontend

## 1. Mission

CandleCore is a standalone, mathematically driven market-analysis and
trade-management platform. It will process Delta Exchange market data,
identify market structures using deterministic algorithms, host independently developed, versioned strategy plugins, capture and
evaluate discretionary trading methodologies, and backtest strategies and
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

  Initial data interval               3m for CC-M1 only

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

**There is no platform-wide primary timeframe.** Each strategy instance declares the symbols, timeframes, candle finality requirements and features it needs. The platform derives market-data subscriptions from the union of requirements across enabled strategies, subject to exchange capabilities and operator-approved resource limits. CC-M1 initially collects 3m candles for BTCUSD, ETHUSD and SOLUSD as a narrow first ingestion milestone only. This does not constrain later strategies to 3m.

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

### 5.5 Strategy Plugin Host

-   Loads compatible, explicitly trusted strategy plugins through a versioned public SDK.
-   Supports multiple independently configured strategy instances.
-   Supplies standardized market snapshots, confirmed perception events and feature contracts.
-   Enforces plugin lifecycle, configuration validation, state persistence and compatibility checks.
-   Records structured proposals, explanations, reason codes and evidence references.
-   Separates scalping and intraday profiles while allowing community-defined strategy types.
-   Uses the same plugin contract for live evaluation, historical replay and paper simulation.
-   Does not allow plugins to submit orders, access exchange credentials or bypass centralized risk controls.

### 5.6 Strategy Plugin SDK

The SDK defines the stable extension contract: manifest, plugin API version, configuration schema, event subscriptions, strategy context, decision proposal schema, state snapshot/restore and conformance tests. The exact callable hooks are finalized in a dedicated SDK RFC before the API is declared stable.

Third-party plugins are separate packages/repositories. The core platform does not need to contain every user's strategy.

### 5.7 Risk Manager

### 5.6 Risk Manager

-   Validates size, exposure, loss limits and position constraints.
-   Rejects invalid or unsafe proposals.
-   Is independent from perception and strategy.
-   Cannot be bypassed by future ML filters.

### 5.8 Execution

A paper broker is introduced before any exchange execution. A future
Delta execution adapter must include local idempotency, client-order-ID
reconciliation, order/fill/position state machines, protective-order
verification and emergency shutdown. Live execution requires a separate
explicit authorization and release gate.

### 5.9 Frontend

Next.js App Router + TypeScript. It renders: - Candles and volume. -
Configurable timeframes. - Machine-generated annotations. -
Human-generated drawings. - Strategy plugin discovery/configuration. -
Decision records. - Trade and risk state. -
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

## 8. Public extensibility and plugin safety

CandleCore is designed as a public host platform. The Strategy Plugin API is a first-class architectural boundary, not a late add-on. Plugin packages declare identity, semantic version, compatible API range, configuration schema, supported symbols/timeframes, required perception features, entry point and license. There is no global primary timeframe: each strategy instance declares its own timeframe requirements, including optional multi-timeframe dependencies. The host computes shared data subscriptions from all enabled instances and avoids duplicate collection where requirements overlap.

A plugin returns a structured decision proposal. The host independently validates it and routes it through centralized risk controls. Multiple strategies may run concurrently, each with isolated configuration, state, subscriptions and audit history. Portfolio-level risk is shared and authoritative.

The first plugin release supports explicitly trusted, locally installed packages. Python code running in-process is not sandboxed. Do not automatically install or execute arbitrary community packages. A future public registry requires package provenance, dependency/license review, permission declarations, resource limits and process/container isolation.

### Strategy authoring

The first user-facing authoring path is a deterministic structured builder that emits a versioned declarative strategy definition/AST. A constrained interpreter validates and evaluates it. Complex strategies can use Python plugins. Natural-language-to-strategy conversion is a separate future research decision; no LLM is introduced in the current core. If later explored, it may only propose a draft AST for human review and deterministic validation.

## 9. Non-goals for initial milestones

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


## 10. Public strategy plugin architecture

CandleCore is a host platform with a stable strategy extension API. The core platform owns market data, perception, historical replay, backtesting, risk validation, paper execution and exchange adapters. Strategy authors own the trading logic packaged as independently versioned plugins.

### 10.1 Plugin boundary

A strategy plugin:
- Consumes standardized, point-in-time market snapshots and typed perception events.
- Receives a versioned strategy configuration.
- Maintains only explicitly declared strategy state.
- Emits structured strategy decisions and explanations.
- Does not submit, modify or cancel exchange orders.
- Does not access exchange credentials, database sessions or arbitrary host internals.
- Cannot bypass the shared risk manager.
- Must use the same interface in live evaluation, historical replay and paper trading.

### 10.2 Plugin contract

The initial Python SDK should expose a small, versioned Protocol/abstract interface. Conceptual contract:

```python
class StrategyPlugin(Protocol):
    manifest: StrategyManifest

    def validate_config(self, config: Mapping[str, object]) -> None: ...

    def initialize(self, context: StrategyContext) -> None: ...

    def on_market_update(
        self,
        snapshot: MarketSnapshot,
        context: StrategyContext,
    ) -> Sequence[StrategyDecision]: ...

    def on_candle_close(
        self,
        snapshot: MarketSnapshot,
        context: StrategyContext,
    ) -> Sequence[StrategyDecision]: ...

    def snapshot_state(self) -> Mapping[str, object]: ...

    def restore_state(self, state: Mapping[str, object]) -> None: ...

    def shutdown(self) -> None: ...
```

The exact hook set must be finalized in the plugin SDK RFC. Plugins should not be forced to implement both update hooks if their declared event subscription does not need them. A plugin must not receive future candles or unconfirmed events unless explicitly subscribed and labelled as provisional.

### 10.3 Manifest and compatibility

Each plugin declares:
- Unique plugin ID and display name.
- Plugin version.
- Author and description.
- Strategy type/tags, e.g. scalping or intraday.
- Supported symbols and timeframes.
- Required perception features/events.
- Configuration schema and defaults.
- Minimum and maximum supported CandleCore API versions.
- Entry point and package metadata.
- License identifier and source URL.
- Determinism and state-persistence declarations.

Use semantic versioning for the public plugin API. Breaking API changes require a major version and migration notes. Plugin manifests are validated before activation.

### 10.4 Strategy decision contract

A plugin returns a proposal, not an order. The proposal should include:
- Decision ID and plugin identity/version.
- BUY, SELL or NO_TRADE / HOLD action.
- Instrument and strategy profile.
- Decision timestamp and input event references.
- Optional entry, stop and target plan.
- Explanation and machine-readable reason codes.
- Expiry/invalidation conditions.
- Plugin configuration hash.

The platform independently validates the decision, calculates or verifies permitted size, applies portfolio and risk limits, and only then passes an approved intent to the paper/execution adapter.

### 10.5 Lifecycle and isolation

Plugin lifecycle: discovered -> validated -> installed -> configured -> enabled -> running -> disabled/quarantined.

For the first release, only explicitly trusted, locally installed Python plugins may run in-process. Never automatically execute arbitrary code downloaded from a public registry. A future public plugin marketplace requires package provenance, signature/checksum verification, dependency review, permission declarations and process/container isolation. Python in-process plugins are not a security boundary.

Plugins must not perform hidden network calls, filesystem access or background order actions. The host should provide bounded inputs and an explicit context. CPU/time limits and crash isolation are required before supporting third-party untrusted plugins.

### 10.6 Multiple strategies

The platform may run multiple strategies concurrently, but each instance has its own:
- Plugin ID and version.
- Instance ID.
- Configuration and configuration hash.
- State namespace.
- Symbol/timeframe subscriptions.
- Risk allocation/profile.
- Decision and performance history.

Portfolio-level risk remains centralized. Strategies must not independently assume they own the full account balance or net exposure.

### 10.7 Backtesting and reproducibility

Backtesting invokes the same plugin contract used by live evaluation. Persist:
- Plugin package/version and API version.
- Source revision or immutable package hash.
- Configuration hash.
- Input dataset identity and revision.
- Perception algorithm versions.
- Runtime/environment metadata.
- Random seed where relevant.
- Output decisions and fill assumptions.

A backtest result is not reproducible if any of these inputs are unknown.

### 10.8 Plugin conformance suite

The SDK must include tests for:
- Manifest validation.
- API compatibility.
- Configuration validation.
- Deterministic output for identical inputs.
- No future-data access.
- Correct state snapshot/restore.
- Duplicate event handling.
- Invalid decision rejection.
- Exception and timeout behaviour.
- Replay/live contract parity.
- Risk-manager separation.

A plugin that fails conformance cannot be marked compatible with a production CandleCore release.

## 11. Strategy authoring and natural-language strategy descriptions

The first strategy-authoring experience will be structured and deterministic, not an AI interpreter.

The planned progression is:

1. **Structured strategy builder:** Users select typed conditions, comparisons, indicators, perception events, timeframes and logical operators.
2. **Declarative Strategy Definition (DSL):** The builder emits a versioned, typed abstract syntax tree (AST) / JSON document. The DSL is constrained to supported operations and has explicit timestamp semantics.
3. **Validation and preview:** The system checks missing parameters, incompatible timeframes, unavailable features, look-ahead risks and ambiguous rules. It displays a readable explanation of the compiled rules.
4. **Human approval:** The author reviews and confirms the exact rule set before it becomes an executable strategy definition.
5. **Compilation:** The validated definition is interpreted by a deterministic rule engine or compiled into a normal strategy plugin.
6. **Advanced Python plugins:** Developers can implement custom logic using the public SDK when the DSL is insufficient.

Natural-language-to-strategy conversion is a separate future research item. No LLM or generative-AI dependency is introduced now. If reconsidered, it must be an optional, isolated authoring adapter that proposes a DSL/AST for human review. It must never directly create executable arbitrary Python, enable a strategy, alter risk controls or place orders. Ambiguous English must produce clarification requests, not guessed rules.

## 12. Public ecosystem and contribution policy

CandleCore's core remains independently maintained and the plugin API is versioned. Public contributors may submit:
- Core improvements through normal review.
- Strategy plugins in separate packages/repositories.
- Perception algorithms through reviewed core contributions.
- Example plugins and conformance tests.
- Documentation and strategy-definition examples.

A plugin's performance claims must disclose data period, instrument, timeframe, costs, assumptions, out-of-sample methodology and known limitations. CandleCore must not endorse profitability solely because a plugin passes technical conformance.

The repository's software license and the plugin license compatibility policy must be selected explicitly before publishing a formal plugin registry. Public visibility alone does not grant permission to reuse code.


## 13. Strategy-driven timeframe orchestration

There is no global default or primary timeframe for strategy evaluation. A strategy manifest and each configured instance declare:
- Required symbols/instruments.
- Required candle intervals/timeframes.
- Which intervals are used for entries, exits, filters and higher-timeframe context.
- Whether it needs finalized candles only or also provisional updates.
- Required warm-up history and lookback windows.
- Required perception events/features and their source timeframes.

The platform's data-requirements planner computes the union of requirements across all enabled strategy instances, deduplicates overlapping feeds and schedules acquisition/recovery for the required data. It must expose unavailable intervals, unsupported exchange resolutions, stale feeds and resource limits rather than silently substituting another timeframe.

A strategy may consume multiple timeframes simultaneously. Higher-timeframe values must be point-in-time correct: only bars finalized and knowable by the strategy decision timestamp may be used. Lower-timeframe data may be aggregated into a higher timeframe only when source coverage, alignment and correction semantics are defined and the derived series is explicitly identified. Do not assume arbitrary higher-timeframe candles can be reconstructed from incomplete lower-timeframe data.

CC-M1 remains intentionally scoped to 3m collection for BTCUSD, ETHUSD and SOLUSD. That is a milestone constraint, not a permanent product constraint or global primary timeframe.
