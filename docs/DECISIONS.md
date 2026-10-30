# CandleCore Architecture Decision Log

**Date:** 2026-10-30\
**Status:** Initial decisions approved

## Approved decisions

### ADR-001 --- Independent project

CandleCore is a new, standalone project. It must not fork, copy, extend,
import or depend on the user's existing AI Agent Automation Platform or
any of its repositories.

### ADR-002 --- Python is the authoritative backend

Python owns market data processing, perception, strategy, risk,
backtesting and execution. The UI does not make authoritative trading
decisions.

### ADR-003 --- No LLM or generative AI

No GPT or other LLM APIs, vision-language models, generative AI,
fine-tuning, token-based inference services or expensive GPU inference
dependencies. Conventional ML is optional and deferred.

### ADR-004 --- Exchange and instruments

Initial exchange: Delta Exchange India. Initial instruments: BTCUSD,
ETHUSD and SOLUSD.

### ADR-005 --- Primary timeframe

The initial primary timeframe is 3m. Additional timeframes are supported
by architecture but are not automatically included in CC-M1.

### ADR-006 --- Trading profiles

Both scalping and intraday are in scope. They must be represented as
separate strategy profiles, not collapsed into a single set of entry,
exit and holding-period assumptions.

### ADR-007 --- Frontend

Use Next.js App Router with TypeScript. Charting uses TradingView
Lightweight Charts v5, with the required TradingView attribution.

### ADR-008 --- Backend API

Use FastAPI for versioned REST and WebSocket APIs.

### ADR-009 --- Database

Use PostgreSQL initially, SQLAlchemy 2 and Alembic. Do not require
TimescaleDB at project start. Reconsider only with measured workload
evidence and licensing review.

### ADR-010 --- Exchange integration

Implement a narrow Delta-specific REST and WebSocket adapter using HTTPX
and a maintained asyncio-compatible WebSocket library. CCXT is not a
required core dependency.

### ADR-011 --- Time and financial precision

Use UTC internally. Preserve source timestamp and unit. Use Decimal-safe
financial values at persistence and exchange boundaries; float64 may be
used in numerical analysis behind explicit conversions.

### ADR-012 --- Data corrections

Do not silently mutate finalized historical candles. Preserve revisions
and emit correction events.

### ADR-013 --- Historical friend material

Initial strategy evidence consists of historical screenshots and trade
records. Screenshots are manually reviewed reference material, not the
algorithm's market-data input. Unknown timestamps/prices and uncertain
mappings must remain explicitly uncertain.

### ADR-014 --- Execution safety

No live execution during initial development. Paper trading is the first
execution mode. Live trading requires a separate explicit authorization
and release process.

### ADR-015 --- Development order

Market data -\> charting/perception -\> knowledge capture/strategy -\>
backtesting/paper -\> risk/exchange integration -\> hardening. Do not
prioritize order placement ahead of data and strategy validation.

## Resolved research-report issues

1.  The historical candle endpoint is `/v2/history/candles`, not
    `/v2/products/{symbol}/candles`.
2.  Historical `start` and `end` parameters are Unix seconds; the
    endpoint caps each response at 2,000 candles.
3.  A symmetric swing-window algorithm uses future bars. A pivot becomes
    knowable only after right-side confirmation bars close.
4.  A wick through a level is a candidate sweep pattern, not evidence of
    institutional intent.
5.  A single close beyond a zone is not automatically a confirmed
    high-quality breakout.
6.  Example EMA/RSI rules in the report are not the friend's strategy
    and must not be implemented as such.
7.  ML is deferred until consistent labeled data and out-of-sample
    evidence exist.
8.  A client order ID alone does not guarantee idempotency. A local
    ledger and reconciliation are required.
9.  A candle touching both stop and target has intrabar ambiguity; do
    not assume the favourable outcome.
10. TimescaleDB, Redis, Kafka, microservices and GPU infrastructure are
    not initial requirements.

## Open questions --- do not silently assume

-   Exact Delta WebSocket payload schema and timestamp unit for each
    subscribed channel.
-   Delta heartbeat and reconnect requirements at implementation time.
-   REST candle boundary semantics and ordering.
-   Whether historical trade records contain complete timestamps, fills,
    fees and direction.
-   Screenshot metadata availability and whether chart time/price axes
    are visible.
-   Which timeframes beyond 3m the friend actually uses.
-   Exact entry, stop, target, invalidation and no-trade rules.
-   Whether friend uses mark price, traded price or another reference
    for specific decisions.
-   Product-specific contract, margin, funding and liquidation details
    required before execution.
-   Whether deployment is on the user's own Debian server or a VPS.
-   Frontend authentication and single-user versus multi-user
    requirements.

## Change control

Any change to an approved decision must be recorded here with: -
Decision ID. - Previous decision. - New decision. - Reason. - Impacted
modules and documents. - Migration or compatibility requirements.


## ADR-016 — Public, pluggable strategy platform

**Status:** Approved  
**Decision:** CandleCore is a public host platform with a first-class, versioned Strategy Plugin API. Strategy logic is delivered as independently versioned packages/plugins rather than hardcoded into the platform. Multiple strategy instances may run concurrently with isolated configuration and state. Plugins consume standardized market/perception data and emit structured decision proposals. CandleCore retains centralized risk management and execution authority. The same plugin contract must be used in live evaluation, replay and backtesting.

**Consequences:**
- A plugin SDK, manifest, lifecycle manager, compatibility checks and conformance suite are required.
- Scalping and intraday are initial strategy profiles, not hardcoded limits on plugin types.
- Third-party strategies should be separately packaged and must not require edits to core modules.
- Backtest results pin plugin version/hash, API version, configuration hash and data revision.
- Python in-process plugins are trusted code, not a sandbox.
- A marketplace or automatic install-and-run workflow is deferred until isolation and supply-chain security are implemented.

## ADR-017 — Strategy authoring and natural-language conversion

**Status:** Approved direction; detailed DSL schema deferred.  
**Decision:** The first authoring path is a deterministic structured builder that emits a typed, versioned declarative strategy definition/AST. The host validates and interprets this definition. Developers may implement advanced logic as Python plugins using the public SDK.

Natural-language-to-strategy conversion is explicitly out of current scope. No LLM or generative AI is introduced into the core. It may be evaluated later as a separate optional authoring adapter that can only propose a draft AST for human review and deterministic validation. It must never emit executable arbitrary Python, enable a strategy, change risk controls or place orders.

## ADR-018 — Third-party plugin trust boundary

**Status:** Approved  
**Decision:** Initial plugin support is limited to explicitly trusted, locally installed packages. In-process Python plugin execution is not considered secure isolation. A public marketplace or untrusted plugin execution requires a separate process/container isolation design, resource limits, package provenance and integrity checks, dependency/license review, permission scopes and revocation controls.

## ADR-019 — Public licensing policy remains unresolved

**Status:** Open  
**Decision:** Do not infer a license from repository visibility. Before formal plugin registry publication, maintainers must select the CandleCore repository license and define compatible plugin license metadata/policy. Plugin manifests should declare an SPDX license identifier.
