# Hyperliquid Stage-G public-MAINNET-data / native-sandbox dry run (D3)

This is a separate `hl-stageg-testnet` OS process with its own state database
and exactly one Nautilus 1.231 `TradingNode`. It uses only the native public
Hyperliquid MAINNET data factory and Nautilus `SandboxExecutionClient`; no
Hyperliquid execution factory is registered. Its immutable Stage-G
candidate is loaded from `configs/stage-g-v1.json`; the canonical candidate
SHA-256 is reported at startup and in status.

## D4 process boundary

`coinmaster-hl-stageg-testnet.service` is the trader unit. It owns exactly one
Nautilus `TradingNode`, its testnet state DB, and the separate protected
`/etc/coinmaster-hl-stageg-testnet.env` non-secret guard environment. The unit runs as
the non-login `coinmaster-hl` identity, while the runtime API/research unit
runs as distinct `coinmaster-research`; their StateDirectories are `0700` and
they share only the read-only `/srv/coinmaster/runtime` release. It neither
requires nor is required by `coinmaster-runtime.service`; stop/restart either
unit independently. Research remains API-owned child subprocesses, one
canonical worker at a time on the shared VPS. Each child receives a private
`runs/jobs` artifact directory and a scrubbed environment: no Hyperliquid or
Bybit credential, trader/paper/control DB path, or API/relay token is inherited.

The local layout check is read-only and does not start a node:

```sh
.venv/bin/python scripts/process_isolation_doctor.py
```

`COINMASTER_LIVE_ENABLED` must be `false`, `COINMASTER_HL_TESTNET_ENABLED`
must be `true`, and `COINMASTER_HL_TESTNET_ENVIRONMENT` must be `mainnet`.
Any other value refuses startup. The unit registers the public `FeedObserver`
and the sealed Stage-G `WaveOverlayStrategy` only after its warmup and approval
gate pass. Its sole execution client is local native Sandbox; it cannot query
an account, sign, transfer, or place an exchange order. A local Sandbox cache
is never exchange reconciliation. This virtual process uses public HL MAINNET
data; the historical `testnet` name is only its isolated service identity.

## Recovery rule

The durable state is
`/var/lib/coinmaster-hl-stageg-testnet/hl-stageg-testnet.sqlite`. On any
recovered open position/order or pending submit, the worker stays
`MANAGE_ONLY`; it never treats a fresh native cache as proof that an exchange
is flat. Only a documented flat local restart is reconciled automatically.

Observed public funding/marks remain observations. Sandbox commissions and
margin are local native-model outcomes; account-specific Hyperliquid fees,
funding cash and margin remain unknown and are never presented as observed.
