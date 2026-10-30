# CandleCore Strategy Plugin System

**Status:** Architecture approved; SDK implementation is scheduled after market-data and perception foundations.  
**Purpose:** Define how independent developers build, configure, test and run strategies on CandleCore.

## 1. Product model

CandleCore is the host platform. A strategy is an extension that uses platform capabilities; it is not a fork of the platform.

The host provides:
- Standardized market data and candle history.
- Versioned perception events and numerical features.
- Chart annotations and replay.
- Strategy lifecycle and configuration.
- Backtesting and paper simulation.
- Centralized risk controls.
- Execution adapters and audit history.

A strategy plugin provides:
- Entry, exit and no-trade logic.
- Strategy-specific state.
- Parameter schema and defaults.
- Explanation/reason codes for each decision.
- Optional custom features, provided they obey the plugin contract.

## 2. Non-negotiable boundary

**Plugins propose decisions; CandleCore owns risk and execution.**

A plugin cannot call the exchange order API, retrieve credentials, mutate portfolio state, bypass risk checks or submit orders. It returns a typed proposal. The host validates it and decides whether to reject, simulate or later route it.

## 3. Initial plugin API

The following is conceptual and will be refined in a versioned SDK RFC:

```python
from typing import Mapping, Protocol, Sequence

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

The SDK may provide a base class with no-op hooks so plugins implement only the events they need. Hook invocation, async support, concurrency and event ordering must be fixed in the SDK RFC before the API is declared stable.

## 4. Manifest

Each package declares a manifest containing:

| Field | Meaning |
|---|---|
| `plugin_id` | Stable reverse-domain or namespace-qualified ID |
| `name` | Human-readable name |
| `version` | Plugin semantic version |
| `api_version` | CandleCore plugin API version |
| `author` | Maintainer identity |
| `description` | What the strategy does |
| `tags` | Scalping, intraday, trend, mean-reversion, etc. |
| `symbols` | Supported instruments |
| `timeframes` | Required intervals |
| `required_features` | Perception features/events consumed |
| `config_schema` | Typed configuration contract |
| `entry_point` | Plugin factory/class |
| `license` | SPDX license identifier |
| `source_url` | Source repository |
| `state_schema_version` | Persistent state compatibility |

Manifest fields are validated before a plugin can be enabled.

## 5. Strategy decision schema

A proposal should carry:
- Unique decision ID.
- Plugin ID, plugin version and instance ID.
- Symbol and strategy profile.
- Decision timestamp.
- Action: BUY, SELL, NO_TRADE or HOLD.
- Optional entry plan, stop-loss and take-profit.
- Reason codes and human-readable explanation.
- Evidence/perception event IDs.
- Expiry and invalidation conditions.
- Plugin configuration hash.

The host adds risk-validation outcome and any paper/execution identifiers. The plugin cannot mark its own proposal as risk-approved.

## 6. Configuration and instances

A plugin package can be installed once and configured as multiple independent instances. Each instance has its own:
- Config and config hash.
- State.
- Symbol/timeframe subscriptions.
- Enabled/disabled state.
- Risk allocation selected by the platform operator.
- Decisions, backtests and performance history.

Do not let a strategy infer that it owns the whole account balance. Portfolio exposure is centralized.

## 7. Determinism and replay

Given identical:
- Plugin package hash.
- Plugin API version.
- Configuration.
- Input event sequence.
- Perception outputs.
- Runtime semantics.
- Random seed (if any),

the plugin should produce identical decisions.

A plugin may not inspect future candles, use wall-clock time as a hidden signal, fetch unrecorded network data or read mutable external state. If a strategy needs external data in a later release, that data must be declared, timestamped, recorded and replayable.

## 8. Plugin lifecycle

`DISCOVERED -> VALIDATED -> INSTALLED -> CONFIGURED -> ENABLED -> RUNNING`

Possible terminal/safety states:
- `DISABLED`
- `FAILED`
- `QUARANTINED`
- `INCOMPATIBLE`

State transitions are audited. A plugin that repeatedly fails, violates time limits or emits invalid decisions can be disabled without affecting the market-data collector or other plugins.

## 9. Security model

Python plugins execute code. Loading a third-party package inside the main process is not a security boundary.

Initial release:
- Only explicitly trusted, locally installed plugins.
- No automatic install-and-run from URLs.
- No credentials or direct exchange client exposed to plugins.
- Narrow context object and typed inputs.
- Dependency/version pinning.
- Package hashes and source metadata.
- Plugin enablement is an explicit operator action.

Before a public plugin marketplace or untrusted community code is supported:
- Run plugins in isolated worker processes or containers.
- Apply filesystem/network restrictions.
- Apply CPU, memory and execution-time limits.
- Verify package provenance and checksums/signatures.
- Review dependency and license metadata.
- Define permission scopes and revocation.
- Test crash containment and state recovery.

## 10. Conformance suite

A plugin must pass:
1. Manifest and schema validation.
2. API-version compatibility.
3. Config validation.
4. Determinism/replay test.
5. State snapshot/restore test.
6. Duplicate and out-of-order event tests.
7. No future-data test.
8. Invalid proposal rejection.
9. Exception/timeout containment.
10. Backtest/live contract parity.
11. Risk boundary test proving plugin cannot submit an order.

Passing conformance establishes technical compatibility, not profitability or safety of a trading idea.

## 11. Packaging and distribution

The initial SDK should support ordinary Python packages with a documented entry-point convention and pinned dependencies. The exact Python entry-point group, package naming convention and SDK release policy will be specified in the SDK RFC.

Do not build a public marketplace in the first implementation. Start with:
- SDK package.
- Example plugin repository/directory.
- Template generator.
- Local plugin registry.
- Compatibility test command.
- Documentation for publishing a package.

A remote registry can be considered after isolation and supply-chain controls exist.

## 12. Strategy authoring paths

There are two distinct ways to create a strategy:

### A. No-code / low-code structured builder

A user selects supported market features and conditions, defines boolean logic and sets parameters. The UI produces a typed declarative strategy definition. The backend validates and interprets that definition deterministically.

### B. Python plugin

A developer implements custom strategy logic against the public SDK. This supports logic that is too complex for the declarative builder.

Natural-language strategy conversion is not part of the initial plugin release. See `STRATEGY_AUTHORING.md` for the future design boundary.

## 13. Versioning policy

- Public plugin API follows semantic versioning.
- Plugin declares the compatible API range.
- Core must reject incompatible plugins before activation.
- Breaking changes require migration notes and updated examples.
- Backtest results pin the plugin package hash, API version, config hash and data revision.
- Deprecated API versions have a documented support window.

## 14. Performance and risk disclosure

Plugin authors must not claim a strategy is profitable based only on win rate or an in-sample backtest. Public examples and any future registry listing should disclose costs, slippage, funding, sample period, instruments, timeframe, drawdown, out-of-sample methodology and assumptions. CandleCore technical compatibility is not an endorsement or investment recommendation.
