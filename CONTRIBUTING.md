# Contributing to CandleCore

Thank you for your interest in CandleCore. CandleCore is intended to be an extensible public platform for deterministic market analysis and independently developed trading strategies.

## Contribution areas

- Core market-data and exchange adapters.
- Market perception algorithms.
- Strategy Plugin SDK and conformance tests.
- Independent strategy plugins.
- Backtesting and paper simulation.
- Charting and annotation tools.
- Documentation, examples and tests.

## Before contributing

1. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/TECHNICAL_SPECIFICATION.md`, `docs/ROADMAP.md` and `docs/DECISIONS.md`.
2. For strategy work, also read `docs/STRATEGY_PLUGINS.md` and `docs/STRATEGY_AUTHORING.md`.
3. Open an issue or discussion for substantial design changes before implementation.
4. Keep changes focused and include tests and documentation.
5. Never include API keys, exchange secrets, account identifiers or private trading records.

## Strategy plugin contributions

Strategy plugins should be independently packaged and should not require changes to CandleCore core modules.

- Implement the versioned public plugin API.
- Declare plugin metadata, supported API version, dependencies and license.
- Include configuration validation and tests.
- Include deterministic replay fixtures where possible.
- Emit structured decisions with reasons and evidence references.
- Never submit orders directly or bypass host risk controls.
- Disclose backtest assumptions, fees, slippage, funding and out-of-sample limitations.
- Do not claim profitability based only on in-sample results or win rate.

Until plugin isolation is implemented, only trusted local plugins may be loaded. Do not submit code that downloads and executes arbitrary remote packages.

## Engineering expectations

- Python code must be typed where practical.
- Add unit, integration or contract tests appropriate to the change.
- Preserve UTC and event-time/confirmation-time semantics.
- Avoid look-ahead bias and hidden external state.
- Keep exchange-specific details behind adapters.
- Update documentation and decision records when contracts change.
- Do not introduce LLMs, generative AI or GPU inference into the core platform.

## Licensing

CandleCore's repository license and the policy for compatible third-party strategy plugin licenses must be explicitly selected by maintainers. Do not assume that public visibility means code can be reused. Include a license identifier in plugin metadata once the project policy is established.
