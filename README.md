# CandleCore — Open, Pluggable Algorithmic Trading Platform

**Status:** Architecture approved; implementation not started\
**Project type:** Public, extensible Python-first algorithmic trading platform\
**Initial exchange:** Delta Exchange India\
**Initial instruments:** BTCUSD, ETHUSD, SOLUSD\
**Initial CC-M1 data interval:** 3 minutes only; strategy instances choose their own timeframes\
**Execution mode:** Paper trading only when execution is introduced

## What CandleCore is

CandleCore is an open, extensible host platform for deterministic market analysis and algorithmic trading research. The platform provides market data, charting, perception algorithms, historical replay, backtesting, centralized risk controls and execution adapters.

**Strategies are plugins.** Users and contributors can build, package, configure, test and run independent strategies without modifying CandleCore's core engine. Scalping, intraday, trend-following, mean-reversion and community strategies use the same versioned Strategy Plugin API.

A strategy plugin proposes structured decisions. CandleCore owns risk validation and execution. Plugins cannot access exchange credentials or submit orders directly.

### Core platform vs. strategy plugins

| CandleCore core | Independent strategy plugins |
|---|---|
| Exchange data and normalized candles | Entry/exit/no-trade rules |
| Market perception and features | Strategy-specific state |
| Charting and annotations | Strategy parameters and configuration |
| Replay and backtesting runtime | Decision explanations and reason codes |
| Risk manager and paper/execution adapters | Structured decision proposals |

CandleCore is not an English-to-code system today. Initial authoring will use a deterministic structured builder and a versioned declarative strategy definition. Natural-language conversion is a separate future research item and is not part of the current core.

## Documents

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `docs/ARCHITECTURE.md`              System boundaries, component
                                      topology and technology decisions

  `docs/TECHNICAL_SPECIFICATION.md`   Data contracts, pipeline,
                                      algorithms, persistence and
                                      interfaces

  `docs/ROADMAP.md`                   Dependency-aware phases and exit
                                      criteria

  `docs/DECISIONS.md`                 Approved architecture decisions and
                                      unresolved questions

  `docs/CC-M1_KILO_PROMPT.md`         Implementation-agent prompt for the
                                      first milestone
  -----------------------------------------------------------------------

Additional strategy ecosystem documents:
- `docs/STRATEGY_PLUGINS.md` — plugin contract, lifecycle, compatibility, security and conformance.
- `docs/STRATEGY_AUTHORING.md` — structured strategy builder and future natural-language authoring boundary.
- `CONTRIBUTING.md` — contribution expectations.

## Project rules

1.  CandleCore is independent. Do not reuse, fork, import or depend on
    any other repository.
2.  Python is authoritative for market data, perception, strategy runtime,
    risk, backtesting and execution. The public strategy SDK is a stable,
    versioned extension boundary.
3.  No LLMs, generative AI, vision-language models, token-based
    inference APIs or GPU inference dependencies.
4.  No automated live order execution. Paper mode only until separately
    authorized.
5.  All internal timestamps are timezone-aware UTC.
6.  Every market-derived event must preserve its event time and the time
    it became knowable.
7.  Historical replay and live operation must share the same perception
    and strategy code.
8.  No look-ahead bias, silent candle mutation or unrecorded data
    correction.
9.  Do not infer a trading rule from an ambiguous screenshot or
    incomplete trade record.
10. Do not move to the next milestone until the current milestone's
    acceptance criteria are demonstrated.
11. Strategies are independently versioned plugins; the core must not
    hardcode one user's strategy as the only supported strategy.
12. Plugins propose decisions only. Centralized CandleCore risk controls
    and execution adapters remain authoritative.
13. Do not automatically download and execute untrusted community code.
14. No AI-generated strategy code or natural-language conversion is in
    the current scope.

## Source hierarchy

-   The user-approved configuration in `docs/DECISIONS.md` is
    authoritative for project choices.
-   `docs/TECHNICAL_SPECIFICATION.md` is authoritative for interfaces
    and behaviour.
-   Official Delta Exchange API documentation is authoritative for
    exchange contracts.
-   The supplied Deep Research report is an initial research reference,
    not an unquestionable specification.

## Initial development target

CC-M1 is the reliable market-data foundation. It downloads historical
three-minute candles for the three initial instruments as the first ingestion slice. This is a CC-M1 scope limit, not a platform-wide or strategy-level primary timeframe. Later data subscriptions are derived from the active strategies' declared symbol/timeframe requirements. It collects live updates, persists raw and normalized data, detects
gaps, performs bounded recovery and exposes read-only historical data
through FastAPI.

CC-M1 must not place orders, generate trading signals, implement strategy rules or implement the plugin runtime. It must preserve the clean architectural boundary needed for the later Strategy Plugin API.
