# CandleCore Roadmap

**Status:** Approved dependency-aware roadmap\
**Planning style:** Milestone-based; duration estimates are indicative,
not commitments.

## Guiding rule

Do not implement execution before market data, perception, strategy
semantics and paper simulation have been validated. No milestone
silently authorizes live trading.

## Phase 0 --- Architecture and requirements

**Status:** Architecture baseline approved.

Deliverables: - Architecture and technical specification. - Decision
log. - Delta API contract checklist. - Data contracts. - Test and
release gates. - Initial repository structure.

Exit: - User approves the technical specification. - Unresolved
assumptions are explicitly listed. - CC-M1 scope is fixed.

## Phase 1 --- CC-M1: Market-data foundation

Deliverables: - Python package and development tooling. - Delta REST
historical downloader. - Delta public WebSocket candle collector. -
BTCUSD, ETHUSD and SOLUSD 3m subscriptions as the first collection slice. Keep the data model and interfaces timeframe-generic; 3m is not a platform default. - Payload normalization and
timestamp conversion. - Candle validation and lifecycle. - PostgreSQL
schema and Alembic migrations. - Raw event persistence. - Gap detection
and REST recovery. - Read-only FastAPI historical endpoint. - Contract,
unit and integration tests. - Operational documentation.

Exit: - All CC-M1 acceptance criteria in `TECHNICAL_SPECIFICATION.md`
pass. - No trading signals or order submission.

## Phase 2 --- Charting and market observation

Deliverables: - Next.js App Router + TypeScript application. -
Lightweight Charts v5 integration. - Historical candle loading. - Live
candle updates. - Volume panel. - Symbol selector for BTCUSD, ETHUSD and
SOLUSD. - Strategy-aware chart timeframe selection, with multiple intervals available according to configured data coverage. - Backend stream
contract. - TradingView attribution.

Exit: - Chart data matches persisted backend data. -
Disconnect/reconnect does not corrupt displayed state. - Frontend is a
read-only visualization client.

## Phase 3 --- Perception foundation

Deliverables: - Swing high/low detection with confirmation time. - Tie
and plateau handling. - Market structure classification. - ATR and
volatility features. - Deterministic event schemas. - Algorithm
version/config hashes. - Machine annotation persistence and rendering. -
Historical replay fixtures.

Exit: - Synthetic and historical examples pass. - No future-bar
information leaks into decisions. - Human review can compare algorithm
output with chart.

## Phase 4 --- Advanced perception

Deliverables: - Support/resistance zone construction. - Trendline
candidate generation and validation. - BOS and CHoCH. - Liquidity sweep
candidates. - Breakout/retest state machine. - Candle patterns. - Volume
and momentum features. - Multi-timeframe context. - Event invalidation
and expiry.

Exit: - Each algorithm has a written definition, tests, known
limitations and replay evidence. - No repainting or look-ahead
violations in the replay suite.

## Phase 5 --- Human knowledge capture and strategy reconstruction

Deliverables: - Historical screenshot asset registry. - Trade-record
importer and mapping. - Human chart annotation tools. - Timestamp/price
calibration workflow. - BUY/SELL/NO TRADE decision records. -
Accepted/rejected opportunity labels. - Label provenance and
confidence. - Separate scalping and intraday profiles. - Rule
specification and deterministic strategy implementation.

Exit: - Friend's rules are documented and reviewed. - Unknown or
ambiguous rules remain explicit. - Strategy can be replayed
deterministically.

## Phase 6 --- Backtesting and paper simulation

Deliverables: - Event-driven historical replay. - Simulated order and
fill models. - Fees and slippage. - Funding and contract mechanics. -
Intrabar ambiguity policy. - Position sizing and PnL. - Walk-forward
evaluation. - Performance and robustness reports. - Paper broker.

Exit: - Reproducible runs. - Chronological evaluation. - No future
leakage. - Baseline performance report includes costs and risk metrics.

## Phase 7 --- Risk and exchange execution integration

Deliverables: - Deterministic risk gates. - Exposure and loss limits. -
Delta private API adapter. - Order state machine. - Client-order-ID
reconciliation. - Partial fill handling. - Position reconciliation. -
Protective order verification. - Kill switch and manual intervention. -
Paper-mode end-to-end operation.

Exit: - Fault-injection and reconciliation tests pass. - Paper operation
runs under observation. - Live trading remains disabled.

## Phase 8 --- Operational hardening

Deliverables: - Debian deployment. - systemd services. - Nginx/TLS. -
Secret management. - Database backup and restore verification. -
Structured logs and alerts. - Resource and load testing. - Extended
live-market paper forward testing. - Operational runbooks.

Exit: - Stable, recoverable paper deployment. - Documented rollback and
incident response.

## Optional research track --- Classical ML

This track is not a prerequisite for core development.

Start only when: - Labels are consistent and provenance is retained. -
There are enough independent examples. - Feature availability is
point-in-time correct. - A deterministic baseline exists. -
Chronological out-of-sample evaluation is possible.

Candidate models: scikit-learn models, XGBoost or LightGBM. ML may
score/filter strategy candidates only; it cannot bypass deterministic
risk controls. Retain ML only if it improves out-of-sample net
risk-adjusted performance and robustness.

## Dependency graph

``` mermaid
flowchart TD
    A[Phase 0 Architecture] --> B[Phase 1 Market Data]
    B --> C[Phase 2 Charting]
    B --> D[Phase 3 Perception Foundation]
    D --> E[Phase 4 Advanced Perception]
    C --> F[Phase 5 Human Annotation]
    E --> F
    F --> G[Phase 5 Strategy Reconstruction]
    G --> H[Phase 6 Backtesting and Paper Broker]
    H --> I[Phase 7 Risk and Exchange Integration]
    I --> J[Phase 8 Hardening]
    G -. optional .-> K[Classical ML Research]
    H -. validation .-> K
```

## First development milestone: CC-M1

**Goal:** A restart-safe, auditable Delta market-data recorder. The first CC-M1 slice collects 3m candles for BTCUSD, ETHUSD and SOLUSD, with historical backfill, live collection, gap recovery, PostgreSQL persistence and a read-only API. The long-term platform must support data requirements derived from each enabled strategy's declared symbols and timeframes; 3m is not a global primary timeframe.

**Explicit exclusions:** trading rules, signals, ML, paper orders and
live orders.


## Phase 5A — Strategy Plugin Foundation and SDK

This is a first-class platform capability, not an optional add-on. The initial plugin foundation is delivered alongside strategy reconstruction, before broad community strategy adoption.

Deliverables:
- Versioned Strategy Plugin API and compatibility policy.
- Python SDK and plugin manifest.
- Plugin discovery/registration for trusted local packages.
- Strategy configuration schema and independent strategy instances.
- Standardized market snapshot and perception-event interfaces.
- Structured decision proposal contract.
- Plugin lifecycle and state snapshot/restore.
- Conformance test suite and reference example plugins.
- Centralized risk boundary proving plugins cannot submit orders.
- Plugin metadata including source, version, dependencies and license.
- Documentation and contributor guide for third-party plugin authors.

Exit:
- At least one reference plugin runs through historical replay and paper simulation using the same interface.
- Multiple instances have isolated state/configuration.
- Incompatible plugin API versions are rejected.
- Invalid proposals are rejected by the host.
- No plugin can access exchange credentials or bypass risk controls.
- Untrusted packages are not automatically downloaded or executed.

## Phase 5B — Strategy Authoring and Human Knowledge Capture

Deliverables:
- Historical screenshot asset registry and trade-record importer.
- Human annotation and timestamp/price calibration.
- Structured strategy builder.
- Versioned declarative Strategy Definition / AST schema.
- Deterministic schema/type/feature/timeframe validation.
- Human-readable explanation of compiled rules.
- Human approval before a definition can be backtested or enabled.
- Friend's strategy packaged as a first-party example plugin once its rules are documented.
- Separate scalping and intraday configurations.

Natural-language-to-strategy translation is deferred. No AI translator is required for the initial plugin system. A future optional assistant may propose a draft AST for review; it must never generate and execute arbitrary Python or bypass risk controls.

Exit:
- A strategy can be authored through the structured builder or Python SDK.
- The same definition/plugin can be replayed, backtested and paper-run.
- Ambiguities require explicit clarification rather than guessed rule semantics.

Update Phase 6 — Backtesting and paper simulation:
- Add plugin-aware run manifests that pin plugin package hash, plugin API version, config hash, perception versions and dataset revision.
- Run every strategy through the same replay and fill simulation interfaces.
- Compare multiple plugins under identical data and execution assumptions.
- Keep plugin decisions separate from host risk approvals and simulated fills.

Update Phase 7 — Risk and exchange execution integration:
- Enforce centralized portfolio-level risk across all concurrently running strategy instances.
- Allocate explicit risk budgets to strategy instances.
- Prevent strategies from assuming exclusive ownership of account balance or positions.
- Preserve plugin decision -> risk validation -> execution audit chain.
