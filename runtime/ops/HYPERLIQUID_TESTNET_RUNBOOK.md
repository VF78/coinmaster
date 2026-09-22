# Hyperliquid Stage-G testnet (D3, inactive order lifecycle)

This is a separate `hl-stageg-testnet` OS process with its own state database
and exactly one Nautilus 1.231 `TradingNode`. It uses only the native
Hyperliquid TESTNET data and execution factories. Its immutable Stage-G
candidate is loaded from `configs/stage-g-v1.json`; the canonical candidate
SHA-256 is reported at startup and in status.

`COINMASTER_LIVE_ENABLED` must be `false`, `COINMASTER_HL_TESTNET_ENABLED`
must be `true`, and `COINMASTER_HL_TESTNET_ENVIRONMENT` must be `testnet`.
Any other value refuses startup. This unit has no mainnet route and orders are
hard-disabled for D3; it registers only the public `FeedObserver` and no
trading strategy, so no submit/cancel/reduce/forced-close path exists. Do not
use it to submit an order. A locally empty state DB remains
`UNVERIFIED_REMOTE_STATE`, not reconciled, until a separately authorized
authenticated account/order evidence pass completes.

## Account identity and API wallet

Set `COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS` to the real master or
sub-account address, not an API/agent wallet address. Its absence is a
fail-closed `HL_TESTNET_MASTER_ACCOUNT_ADDRESS_REQUIRED` blocker before an
authenticated query client is constructed. The API-wallet private key is read
only by Nautilus from `HYPERLIQUID_TESTNET_PK` in the service environment; it
is not a Coinmaster config value and must never be logged or copied.

This follows Hyperliquid's official guidance: API/agent wallets sign on behalf
of an account, while account queries require the actual account address; using
the agent address can yield an empty result. See [Nonces and API wallets](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets)
and the [Info endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint).

## Recovery rule

The durable state is `runtime/var/testnet/hl-stageg-testnet.sqlite`. On any
recovered open position/order or pending submit, the worker stays
`MANAGE_ONLY`; it never treats a fresh native cache as proof that exposure is
flat. Only a documented flat restart is reconciled automatically.

Before separately authorizing real testnet lifecycle work, provide the master
account address, fund/approve the testnet account and its agent wallet, verify
authenticated account/order reconciliation, and explicitly authorize submit,
cancel, reduce-only, and flatten tests.
