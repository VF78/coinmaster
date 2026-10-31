# CM2 clean BTC/SOL hedge research

This branch publishes the CM2 research implementation, its request-contract audit and compact run evidence. It is a research snapshot, not a deployment or a live trading release.

## Source versions

`PUBLIC_SOURCE_MAP.json` maps the original research commits and exact file blobs to the corresponding commits on this filtered public branch. Required import dependencies are included byte for byte. Unrelated private history, live configuration and other research reports are excluded.

| Version | Original source | Meaning |
|---|---|---|
| Nominal anchor | 77935a3938d036be76bb8935e6c1eb925505d359 | Physical failure retained; financial recovery is a later report-only qualification |
| Diagnostic controls | 3b654410de84a226c27b0ded6aa11c31ce0d2c12 | BTC-only and BTC-trim paths |
| Initial joint search | 004eecf4b1f0da1b20dc50a3c691d24e3d2928da | Search interrupted after repeated nonflat terminal outcomes |
| Audited correction | b8dab4a0375451c4279db8ce05c7db9cddbe7fd0 | Reviewed request guards, clock freshness and durable drain state |

The corrected implementation has 130 constructor-free tests. Actual native engineering and financial results, including NOT_RUN, FAILED and UNKNOWN states, are recorded separately under `results/`; earlier financial results do not certify the corrected implementation.

Report-only tools retain separate source identities: native attribution `617e150294db6af5516b7bac037a94fb103985f2`, aggregation `424739af85d440c4858381e5cb00fe1b87b25a93`. These do not construct another matching or account-PnL engine.

## Execution contract

CM2 uses a native Nautilus Strategy and account/cache/fill/funding observers. Its seven economic parameters and market features are separate from order validation. Each child is checked for quantity precision, price format, min/max notional and current permissions after normalization. Emergency reductions remain subject to venue child caps; ordinary participation limits remain separate.

Fresh official metadata/specifications confirm BTC size decimals5, SOL2; MARKET caps30m/5m USD; LIMIT caps300m/50m USD. Noninteger perp prices must satisfy both five significant figures and `6 - szDecimals` decimal places; integer prices have the documented exception. See the audit's dated source references. The old BTC15m/150m cached specification is superseded.

Backend classification of MARKET translated to IOC, the reduce-only dust exception, real perpetual cash/fee rounding and live collateral equivalence remain UNKNOWN. Conservative IOC/reduction guards are explicitly research policies. The120-second drain deadline is our operational policy, not a Hyperliquid parameter. Deadline expiry records reconciliation and preserves actual unresolved inventory; it cannot manufacture a flat account.

## Reproduction and limits

Use Python3.12 and pinned NautilusTrader1.231.0 from `runtime/pyproject.toml` and `runtime/uv.lock`. Keep per-host executable hashes: equal package versions do not establish ARM/x86 binary equality.

Constructor-free tests:

```sh
PYTHONPATH=runtime python3.12 -B -s -m unittest discover -s runtime/tests -p 'test_cm2*.py' -v
```

The public runner's no-`--run` path checks a supplied frozen request and reaches the native constructor boundary with zero engine constructions. A ready preflight is not a physical-run authorization. Every actual attempt needs a fresh namespace, budget, explicit scoped admission and shared host lease; spent or interrupted IDs cannot be replayed.

The benchmark is UTC[2024-09-01,2026-09-01), seed10000USDC, reserve0. Historical execution/mark/turnover/funding inputs are a pinned Bybit USDT proxy with current Hyperliquid USDC rules and reference fees. Full-fill/zero-impact M1 matching, assumed capacity and funding-source differences remain MODEL_LIMITED/NOT_FAITHFUL_DIAGNOSTIC. This is not historical Hyperliquid order-book or oracle reconstruction.

Large public market datasets, coherent traces and SQLite journals are retained outside Git with hashes in the result manifest. Compact results include actual statuses, financial checks, monthly endpoints, drawdown episodes and provenance. Unknown or unfinished results are null, never zero. No future-profit or live-readiness claim follows from these files.

`qualified-reference/factorial_full_runner.py` is the exact hash-bound coverage reference used by the validator. Only its coverage function is AST-extracted; do not execute the legacy factorial runner as a CM2 command.
