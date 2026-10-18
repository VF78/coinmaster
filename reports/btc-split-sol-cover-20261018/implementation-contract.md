# Native research implementation contract

Research only. Existing Nautilus1.231 BacktestEngine, native NETTING BTC/SOL,
fee profile, minute execution/venue-mark streams, funding module, queue/maps,
native cache, SQLite journal and minute-risk observer remain the money/order
authority. No production route, SDK/version, manual money ledger or second SOL
executor was added. Core flags default OFF.

## Control and ranking

Reuse V3 long5.5/short7.875, seed10000, reserve0, DPoff,
Bybit[2024-09-01,2026-09-01). Receipt:
reports/selective-lifecycle-cap30m-113/sizing-dd50-comparison/v3-receipt.json.
TOTAL5437208.56951095; native minute global DD67.2863064484%;
minimum marked equity4514.69512879; no liquidation; terminal native FLAT.
V3 source a9cbb737a5239d10b9ffcb97d55f997917945263.
New launch keeps research_btc_direction_sizing=True and the three V3
execution/deferred-selective/lifecycle flags; zero_tp_netting=False.
No subtraction of DD, Sharpe, or standalone SOL PnL from terminal TOTAL.
No guaranteed50%DD or intrabar venue-survival assertion.

## BTC split

One existing episode/intent identifies one accepted BTC parent. Original V3
q0/q1/zero omission selects Q first; normalize/cap full Q once, then split whole
lots floor(Qlots/2), remainder. One-lot exception executes that lot immediately
rather than submitting an empty first child; the audit marks
single_lot_immediate=true. Quantity is conserved, not equal USDT expenditure.
Partial IOC first-leg fills retry only remaining first budget; afterward
second part rests native post-only GTC .25% or .50% outside actual first-leg
VWAP (outward price increment). No optional early confirmation in these two
candidates.

Deadline=min(first submit+4h, UTC23:59). Positive TP eligibility accelerates
completion; cancel ACK/authoritative terminal must resolve the resting entry
before a later quote can submit only the remaining accepted Q as IOC.
Unknown ACK blocks a competing child. No futurebar order admission.
Authoritative denied/rejected/expired or next-UTC noncompletion is explicit
cancelled quantity/reason, not silently considered complete. Late fills
decrease cancelled leaves. Native reduce quantities remain capped by actual
open positions.

The accepted Q fixes TP lot allocation before early partials. Prices use actual
aggregate native entry VWAP; all TP quantities remain native position-capped.
Ordinary targets wait for parent completion. Mandatory daily REGIME/TRAIL and
DP/forced/terminal exits take priority and cancel the parent. There is one
domain episode, H identity, and original gross reference. H keeps the existing
formula grossReferenceQ*actualEntryVWAP/beta (original fallback unchanged);
its money value can change as actual VWAP changes. SOL rights use actual fills
against the full accepted denominator, never the child quantity.

## SOL cover

Only the SOL-COVER variant disables the old overlay and its old hard timeout/
z exits; BTC/group emergency closes remain. One existing native NETTING SOL
owner submits through the same maps/callbacks. Beta=Cov(simple1H_SOL,
simple1H_BTC)/Var(simple1H_BTC) over exactly720 completed paired hourly returns;
finite 0.2<beta<4, frozen per BTC episode, correlation archived.
Feature-only721 closed-hour prices precede Sep1 2024; exact official Bybit
public CSVs and manifest are frozen/hashes included. Native completed-hour
callbacks maintain the rolling estimator afterward. No invented beta.

Base0.5*actualBTCquantity*currentBTCmark/(frozenBeta*currentSOLexecutablePrice)
appears on the first actual BTC fill's next real SOL quote; actual BTC partial
fills, second part, TP and flat update immediately. BTC reductions discard the
tactical budget first; BTCflat cancels pending adds and closes actual SOL.
Prices alone trigger review once per completed1H; absolute coverage drift>5pp
retargets on the next SOL quote. Minor minute-price changes do not churn.
Actual time below50%/above100% must still be reported from native minute marks;
50% is a target, not a claim of continuous realized protection.
Paused initial base remains retryable on the first resumed SOL quote. Failed
local/native base admission is retried after an explicit1H cooldown with
unchanged native margin gates. IOC partial leaves retry without a competing
unknown-ACK order. Subminimum/unfilled leaves are visible in coverage and
native admission audit.

The tactical anchor is the actual native VWAP of the first base quantity
budget, accumulated across its partial native fills and frozen after that
budget completes. No unfilled BTC intention starts a SOL cycle; no unfilled/
partial initial base anchor can arm tactical entry. The4h clock starts the
first actual base fill; later base rebalances do not rewrite this anchor.
COVER_ANCHOR receipts retain actual quantity/notional/VWAP and completion.

One optional tactical cycle: adverseSOL move>=.50%, strictly later closed15m
close beyond previous high (longSOL) or previous low(shortSOL), then the first
future real SOL quote must still improve the anchor by>=.25%. Enter no later
than4h after the first actual base fill. Target total coverage .75 or1.0, including
actual held/pending exposure and current BTC leaves. Partial optional retries
recheck actual BTC, price advantage and4h; no costly fallback. Lost quality,
entry-window expiry, UTCexpiry or BTC reductions cancel pending tactical adds
before competing reductions; unknown ACK remains blocked until resolved.

Tactical anchor return exit requires actual native tactical fill
quantity/notional/entry commission plus explicit taker exit-fee estimate to
be net positive. These are order receipts/trigger evidence, not an alternate
PnL ledger. No known-fee evidence means no profit exit assertion. UTC23:59
expiry, BTC TP/flat, DP and emergencies bypass profit gating; base remains.
One used tactic does not re-arm another cycle.

## Verification and isolated runs

The earlier20/126 passing cases did NOT prove the seven independent review
findings. Consolidated corrections add omitted-zero/net-Q and reference/H,
daily mandatory close, old-timeout suppression, pause/denied base retry,
causal hourly5pp drift, one-lot exception, actual tactical commissions and
partial price/window expiry regressions. Corrected focused and combined logs
are implementation-focused-corrected-tests.log (30) and
implementation-corrected-tests.log (136). Final actual-anchor-only change adds
two native cases and implementation-focused-final-tests.log (32passed);
targeted independent review retains GO and updates only the two changed
source/test hashes. No unnecessary repeat of the unchanged broad suite. Old archive test outputs are restored
from their unchanged HEAD bytes after existing fixtures run.

scripts/launch_split_cover_native.py prepares one frozen source pack, preserving
source/runtime/coinmaster + source/reports warmup layout; all Python/public
venue metadata and canonical dataset-manifest/control-report hashes guarded.
It can launch exactly one chosen variant in existing cm113-v3-risk.slice:
MemoryMax650MiB, Swap0, secretless env, no network, readonly source/venv/data,
private writable job only, flock, no concurrent research process, MemAvailable
>=700MiB, disk>=1GiB. It verifies unchanged protected pilot PID2009732,
NRestarts0/active. Preparing or writing this helper does not authorize launch;
root's independent review GO precedes any full run.

Native result JSON adds split_cover_audit.parents (quantity/filled/cancelled
are quantities, step permits lot conversion), cover events with fixed beta,
native tactical receipt basis and hourly drift checks. Existing fill_audit,
native fill/order CSV, funding SQLite, and compressed minute-native-risk.csv.gz
remain authoritative; signed funding stays UNKNOWN where current native
reporting lacks signed cash-delta attribution. Rank only actual native TOTAL,
then disclose marked DD/minimum/coverage tradeoffs and all execution proxy
limits. Joint run only after separate results; fresh winner repeat required.
