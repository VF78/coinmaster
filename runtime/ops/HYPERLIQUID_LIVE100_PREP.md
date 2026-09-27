# #101 source-only live100 instance and release preparation

Status: BLOCKED_TP_PRICE_PARITY_ACCOUNT_SCOPE_AND_RELEASE; Project #2 #101 remains Todo. This
plan and the separate `configs/hl-stageg-live.instance.json` are not an installed
release and grant no live-order capability. The Sandbox worker, its state DB,
service identity and 10,000 USDC virtual seed remain separate and unchanged.

## Exact source and artifact identity

- Immutable candidate: `configs/stage-g-v1.json`, canonical candidate SHA-256
  `637762130c76396cd7c6e24644e31b28079a1683e4460d57f103dde42c603b6d`.
- Owner-approved Stage-G strategy source SHA-256
  `5f4ed8f5aaf07188d258b17dbc5a92e0548380143216f3a1828cb1155aca013e`.
  The source-only #101 TP price correction currently has SHA-256
  `0edecde9548533004292d5a6174ef6aeb77596817080c4a160f72aa2dc7dd511`;
  this new hash is **not approved or sealed** and cannot enter a release yet.
  `configs/stage-g-hl-sandbox-approval.json` also seals execution policy
  `eee44dde50781b6364923e6aad8df714860796b0ec7cd6121adef7c25406f687`.
- Pinned execution dependency: Nautilus 1.231.0 patched CPython 3.12 Linux
  x86_64 wheel SHA-256
  `8ff3c6dcc150bc9ced8b96da80c4cf51645acf7efdc2b1d528634a3cad640b46`,
  qualified source/build chain in `configs/hl-live-wheel-manifest.json`.
  The seven-day CI artifact is temporary; future staging must obtain a wheel
  whose bytes match this hash or stop for a separately reviewed artifact.
- A future release must be a read-only content-addressed runtime tree with a
  clean source commit, `scripts/release_manifest.py` trader seal verification,
  an added exact installed-wheel hash check, the live instance-config hash and
  public account fingerprint in its release receipt. Do not repoint the
  Sandbox release or edit `/opt/coinmaster`. No release has been staged here.

## Current public mainnet constraints (2026-09-27 20:43 UTC)

Read-only official `/info` `meta` response SHA-256
`aa725f96351e898c95ab7cbc4062208200ea4fa7346478a10f60748e928b82e5`
reported USDC collateral token 0. BTC: `szDecimals=5`, size step 0.00001,
max leverage 40, margin table 56 (40x below 150m USDC notional; 20x above).
SOL: `szDecimals=2`, size step 0.01, max leverage 20, margin table 54 (20x
below 70m; 10x above). Official rules allow at most five price significant
figures, with perp price decimals at most `6 - szDecimals`, and a 10 USDC
minimum trade notional. ALO is post-only; IOC cancels unfilled remainder.
Current metadata is public, not selected-account leverage or a live fill.
The venue rules are documented in [tick and lot size](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/tick-and-lot-size),
[margin tiers](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margin-tiers),
[minimum-order errors](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/error-responses),
and [order types](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types).

The contemporaneous read-only `/info` `allMids` response SHA-256
`ce17b07264e7a2f85f3118e2e5c6f59f351f8721860e781920a2218bc9175f61`
had BTC 84574.5 and SOL 122.855. Mids are neither executable quotes nor
necessarily venue-valid order prices. At illustrative valid prices BTC 84575
and SOL 122.85, the 10 USDC minimum requires BTC 0.00012 (10.149 USDC) or
SOL 0.09 (11.0565 USDC). With a verified 100 USDC equity and the sealed
7.875x BTC notional multiplier, illustrative BTC entry 0.00931 is 787.39325
USDC; at *hypothetical* selected 10x its initial margin is 78.739325 USDC
plus 0.3543269625 USDC base taker-fee reserve. The first two 21.25% BTC TP
slices round down to 0.00197 each (166.61275 USDC at that price), above the
10 USDC minimum. These figures do not authorize an order: actual BBO/mark,
selected leverage, equity, open/pending BTC+SOL risk, effective account fee,
funding and every resulting child order must be checked at the submit boundary.
The public preflight without account collateral correctly returns
`ACCOUNT_COLLATERAL_UNKNOWN`.

## TP price parity blocker (P1)

The sealed strategy builds a planned BTC TP as a native limit price with
`instrument.make_price(raw_price)` (BTC stock price precision 0.1), checks
post-only against that native/raw price, then the pinned adapter independently
rounds to five significant figures before wire submission. At BTC TP 84583.5,
the native order price remains 84583.5 while the adapter sends 84584. Strict
Info recovery requires the venue `limitPx` equal the native order price and
therefore cannot reconcile that accepted order. For a BUY TP with ask 84584.0,
84583.5 passes the local nonmarketable check but the wire price equals ask and
ALO can reject it. A current-scale SOL price 122.855 becomes native and wire
122.86, but a future SOL 1234.56 becomes wire 1234.6. These values were
reproduced through the installed patched 1.231 instrument and adapter methods,
without submitting an order. The source-only correction now forms one venue-valid native price from stock
instrument precision and five-significant-figure rules, then applies the
post-only BBO check to that exact price. Ten direct price/submit regression
cases pass against the pinned patched wheel, including BTC tie and magnitude
boundaries, both post-only sides, and high-price SOL. The native price equals
the pinned adapter wire calculation, which is the strict Info equality
contract. The existing Stage-G approval intentionally rejects this changed
source with `BLOCKED_SEALED_STRATEGY_MISMATCH`; the owner must explicitly
approve the new exact hash before the seal or a live release can change.

## Live-only guards to satisfy before a separate owner approval

1. Obtain the explicitly selected *separate* 100 USDC-equivalent mainnet
   account reference from the owner, then record only its public fingerprint
   in the release receipt. No verified account fingerprint is configured now.
   Never infer it from chat, a Sandbox observer, or an API signing wallet.
   Read-only `userRole`, `userFees`, clearinghouse/account state and
   `activeAssetData` for that exact account must establish master/subaccount
   role, effective fees, selected BTC/SOL cross leverage, equity and margin.
2. Keep a distinct non-login live service identity, private live StateDirectory
   and SQLite/Redis namespace, unique trader/strategy/order IDs, and a
   separate protected credential source. Only the native live execution owner
   may hold the account+venue singleton lease. The release must use
   `ScopedHyperliquidExecClientFactory` and its strict clean-flat
   LiveExecutionEngine/Info boundary, never the Sandbox execution factory or
   a second accounting engine. The existing Stage-G worker must retain
   `live_order_capability=false`.
3. Confirm a clean-flat first start, exact native Cache/Info/durable identity,
   fresh paired public feeds and warmup, signed-account-to-reference match,
   and the current public format/tier/minimum checks. Planned BTC TP orders
   remain reduce-only ALO/post-only; SOL exits and forced close remain
   reduce-only native IOC/taker. Check child-order minimums and available
   collateral after fee reserve and all current/pending exposure. A missing
   fact fails closed rather than substituting the public maximum leverage.
4. Open exposure after restart, unknown ACK, foreign/manual fills or any
   inconsistent venue fact remains `RECOVERY_REQUIRED` with no automatic
   takeover. Follow `ops/HYPERLIQUID_LIVE_UNCERTAIN_STATE.md`. No live unit,
   credential, deposit, transfer or order is enabled by this preparation.

The current Sandbox natural lifecycle (#99) and an explicit owner decision on
the exact account, capital, credential path and order scope are still required.
Only after those gates and a verified immutable release may #101 be assessed
for `READY_FOR_OWNER_LIVE_APPROVAL`; a real micro-live smoke is a later,
separately authorized action.
