# CandleCore --- Project Initialization Pack

**Status:** Architecture approved; implementation not started\
**Project type:** Standalone Python-first algorithmic trading platform\
**Initial exchange:** Delta Exchange India\
**Initial instruments:** BTCUSD, ETHUSD, SOLUSD\
**Primary timeframe:** 3 minutes\
**Execution mode:** Paper trading only when execution is introduced

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

## Project rules

1.  CandleCore is independent. Do not reuse, fork, import or depend on
    any other repository.
2.  Python is the authoritative implementation language for market data,
    perception, strategy, risk, backtesting and execution.
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
three-minute candles for the three approved instruments, collects live
three-minute candle updates, persists raw and normalized data, detects
gaps, performs bounded recovery and exposes read-only historical data
through FastAPI.

CC-M1 must not place orders, generate trading signals or implement
strategy rules.
