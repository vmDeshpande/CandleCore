# CandleCore Strategy Authoring

**Status:** Future product design; not part of CC-M1  
**Goal:** Let people express a strategy in a form CandleCore can validate, explain, backtest and execute safely.

## 1. The problem

A user may describe a strategy in natural language:

> If price sweeps a previous 15-minute low, then reclaims the level on a completed 3-minute candle with volume above its recent average, consider a long. The stop goes below the sweep low.

This is not yet an executable specification. Terms such as "previous low", "reclaims", "recent average", "completed", "consider" and "below" need exact definitions.

The system must not guess:
- Which previous low?
- How old can that level be?
- What price tolerance counts as a reclaim?
- Which volume average and lookback?
- Does the entry happen at candle close or next candle open?
- How far below the sweep low is the stop?
- What invalidates the setup?
- What happens if stop and target are both touched in one candle?

## 2. Recommended staged approach

### Stage 1 — Structured strategy builder

Build a UI for selecting:
- Strategy-specific symbols and one or more timeframes (entry, exit, filters and higher-timeframe context).
- Perception event or numerical feature.
- Comparison operator.
- Threshold/parameter.
- Boolean composition (AND, OR, NOT).
- Entry timing.
- Stop/target/invalidation rules.
- Position sizing policy reference.

This is the first authoring mode. It does not need AI.

### Stage 2 — Declarative Strategy Definition

The builder emits a versioned, typed AST/JSON representation. Example, illustrative only:

```json
{
  "schema_version": "1.0",
  "strategy_id": "example.sweep-reclaim",
  "profile": "intraday",
  "conditions": {
    "all": [
      {
        "event": "liquidity_sweep",
        "timeframe": "15m",
        "direction": "bullish",
        "status": "confirmed"
      },
      {
        "feature": "close_reclaimed_level",
        "timeframe": "3m",
        "operator": "equals",
        "value": true,
        "requires_finalized_candle": true
      }
    ]
  },
  "entry": {
    "timing": "next_bar_open"
  },
  "risk": {
    "stop_reference": "sweep_low",
    "stop_buffer": {
      "unit": "ticks",
      "value": 2
    }
  }
}
```

This is a schema illustration, not a committed DSL. Its operators, event vocabulary and semantics must be specified and versioned before implementation.

### Stage 3 — Validation and explanation

Before execution or backtesting, CandleCore should:
- Validate schema and types.
- Check every referenced feature/event exists.
- Check every requested timeframe and symbol is available or can be derived through a validated aggregation path.
- Check multi-timeframe alignment and that higher-timeframe candles were finalized by the decision timestamp.
- Never silently substitute the platform's initial 3m collection interval for a requested strategy timeframe.
- Check warm-up requirements.
- Reject impossible or contradictory conditions.
- Detect use of provisional/future data.
- Require explicit timing and invalidation semantics.
- Produce a human-readable rule explanation.
- Ask for clarification where semantics are ambiguous.

### Stage 4 — Deterministic interpretation

A constrained interpreter evaluates the validated AST against timestamped snapshots. It does not execute arbitrary code. The same interpreter is used in replay and live evaluation.

### Stage 5 — Optional natural-language assistance (future, not approved)

An optional language-to-strategy assistant could translate a written description into a proposed AST. This is a separate research/product decision and is not part of the current no-LLM core.

If explored later:
- It must be optional and disabled by default.
- It must output only a draft declarative AST, never executable Python.
- It must cite the user's original clauses against generated rules.
- It must surface unresolved ambiguities as questions.
- The user must review and approve the exact AST.
- The AST must pass deterministic validation and backtesting.
- It must not access exchange credentials, enable strategies or place orders.
- It cannot alter risk limits.
- No AI output is treated as proof that the intended strategy was captured correctly.

## 3. When a Python plugin is better

Use a Python plugin when strategy logic needs:
- Complex state machines.
- Custom statistical calculations.
- Specialized event handling.
- Custom portfolio-level logic (still subject to host risk controls).
- External data sources that can be made timestamped and replayable.

The plugin must implement the public SDK. Natural-language conversion is not a substitute for a developer reviewing custom code.

## 4. Strategy verification workflow

Every strategy, regardless of authoring path, follows:

`DRAFT -> VALIDATED -> REVIEWED -> BACKTESTED -> PAPER_APPROVED -> ENABLED`

The platform should retain:
- Original human description, if any.
- Structured definition/AST.
- Compiler/interpreter version.
- Plugin version if applicable.
- Config hash.
- Validation errors and clarifications.
- Backtest dataset and assumptions.
- Human approval and activation audit records.

No strategy should move directly from a text description to live execution.
