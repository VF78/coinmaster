# Proposed audited child contract — source only

Base: b21a518b7413b37bae5ed5a04f38b54f0f6a45ff. This source is NOT adopted.
Active004e and all old snapshots/results remain unchanged. No economic engine
or pipeline API probe has run for this revision.

The only economic execution change is request admission/segmentation: official
profile caps now bound each child, including risk/terminal reductions; ordinary
participation remains an additional cap. Existing418f residual prevention remains.
No whole-position cap is imposed. Native MARKET construction is unchanged.
Price and backend classification of its real HL wire request remain UNKNOWN.

Protected BTC LIMIT IOC uses our own aggressive SELL-floor/BUY-ceil legal-price
rule. Valid native decimals and five-significant-figure/integer-exception checks
are followed by the existing current-child permission and positive-net geometry
at that normalized worst-fill limit. The rounding band is at most one legal
formatting quantum; no guessed venue/slippage band is installed. An unacceptable
price or geometry HOLDs without market fallback. Original BBO and normalized
limit have separate provenance; the latter is never called an executable quote.

Known profile caps are MARKET BTC30m/SOL5m and LIMIT BTC300m/SOL50m, selected from
instrument rules independently of account-selected leverage. Ambiguous IOC uses
their minimum as an explicitly conservative MODEL rule, not a claim that all IOC
is MARKET. GTC LIMIT validation uses its own cap; this patch introduces no GTC
trading path. Native quantity/price/type/TIF/reduce-only shape is checked again
immediately before ownership/persist/submit. Margin admission runs once for an
increase after normalization; no duplicate IM/free-collateral calculation added.

Opening minimum10 is official. Applying the existing10 floor to reductions is
explicitly CONSERVATIVE_RESEARCH_POLICY: real dust/full-close exceptions remain
UNKNOWN. Holds retain inventory and blockers; no waiver, fake fill or false flat.

Freshness uses native clock, positive uncrossed own BBO, age<=120s and monotonic
retained quote/mark timestamps. Ordinary increases need known fresh marks and
causal fresh features. Verified owned reductions may use fresh BBO while mark
risk measurement is explicitly UNKNOWN. Missing marks do not borrow quotes or1
for valuation.

The120s drain duration is an approved OWN operational research choice, not an HL
parameter or eighth economic parameter. First-start/deadline/scoped-zero IDs and
reconcile latch are compact checkpoint domain fields. A public native-clock
alert fires without new quotes; expiry cancels unsafe ordinary rights and blocks
increases. Only guarded reductions continue. Actual inventory and ACKs remain
authoritative; a child/callback/load cannot reset the deadline. The scope clears
only on known native scoped-flat plus resolved owned orders. Foreign quarantine
is independent and never washed out by flat. This proves no OS-cold recovery.

Newmodel CM2_AUDITED_CHILD_REQUEST_V1, helper source hash and a separate contract
hash/profile evidence/fixed operational-policy fields enter child admission,
report source_hashes, config_hash and checkpoint identity. Native fill policy_hash
is unchanged and is not represented as the whole contract hash. Raw diagnostic
MODEL_LIMITED/NOT_FAITHFUL status is preserved. Old result comparability is not
claimed; future comparisons require this exact execution contract and controls.

Verification:130 constructor-free unittest cases PASS,7.008s. New tests include
actual callback methods on explicit plain fakes, native instrument/order objects
and actual public TestClock alert delivery, with BacktestEngine blocked. They
cover both cap boundaries/types/assets, integer exception/rounding, emergency
and terminal segmentation, post-rounding ordinary participation, invalid final
native quantity, protected cost HOLD, fresh/stale/future BBO, no fake-mark
valuation, deadline idempotence/no-feed alert, original-deadline journal restore
and malformed checkpoint rejection. No native fills, funding, cash trajectory,
same-engine financial replay or full-run equivalence is proved by these tests.
Existing37 and dust-native fixture evidence remain separate old-source evidence.

Review follow-up: normal hedge/regime SOL release starts a SOL-only deadline even
when cancel_increases=False and BTC core remains held. Owned zero-net pending
orders also retain the scope until actual terminal ACKs. Mirrored real-decision,
public TestClock-object and journal restoration regressions cover this edge.
