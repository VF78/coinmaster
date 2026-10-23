# C1 saved-data decision — 2026-10-23

Recommend choosing the single C1 source contract in `owner-contract.md` for focused implementation/review, not an economic GO. C1 adds a current-open-loss dominance gate and a bounded restoration to a temporary selected residual cut. It avoids repeated permanent M1/M2 trims and the rejected5%-stress sizing controller. Expected TOTAL/DD remain UNKNOWN.

Exact clean E4 source is `bd04c9b3858bcda40060a08eff488849c69af5d8`, E4 configuration `ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6`. E4 retains5631617.35953723, DD57.5854104596%; profit-floor headroom161220.844549883 is narrow. Source correction6061446 is report-only precision, separately identified; earlyTP3/SOLbudget modes stay OFF. S0 immutable75ffc9c is not rerun. Scientific lineage and input pins are in the existing E4 receipt and the independent `verifier-preflight` files.

## Full-calendar screening, not new portfolio economics

Final `owner-C1-screen.py` streamed the ORIGINAL archived E4 settled trace (SHA2561342832a43e4b1f86c8e8e011361e9131975a641d574d1d43fa99ecddf2cce11),1,051,199 receipts,24UTC months,83BTC and25SOL observed native position cycles. This reconstructs no alternative positions/cash/equity and launches no engine. Exact monthly zero-hit rows remain in `owner-C1-screen-monthly.csv`; all opportunities/counterexamples in `owner-C1-screen-events.csv` and JSON. Source_quote_ns is the original money/mark observation; receipt_ns has the existing later receipt timing. Native as-of permission is UNKNOWN.

C1 descriptive predicates: original global DD>=40%; select most negative current native position UPnL; its loss strictly exceeds max(0,E-0.50H). Half of actual held lots would be the candidate target, unquantized in this screen. The first candidate opportunity per original native cycle is recorded, not an assertion of actual domain-group claims. Root's monetary dominance gate was proposed AFTER observing the ungated8-opportunity screen, so it is data-informed selection and must not be described as OOS. Full-calendar rescanning rather than filtering those8 first-hit rows found a later June trigger.

|Original event UTC|Selected asset / qty|DD at opportunity|Own native loss / remaining50% cushion|Original excursion maxDD|Conditional restore proxy|
|---|---|---:|---:|---:|---|
|2024-10-03 09:02|SOL1000|40.2103%|4361.00 /1443.34|57.5854%|2024-10-03 20:01|
|2025-01-13 13:03|SOL4000|40.2241%|51816.00 /17017.35|51.4147%|2025-01-13 20:01|
|2025-06-06 08:47|BTC25.840|41.3292%|55590.88 /54059.65|48.3401%|NONE before original cycle end|
|2025-11-27 02:22|BTC163.477|40.1156%|610852.95 /197552.65|54.7928%|2025-12-01 00:01|

There are4 raw opportunities across4 original high-water excursions, three eventually>50% and **one original-below50 false-positive-like intervention** in June. The gate does not eliminate all false positives. Other original excursions, including E4's unresolved July–August2026 decline46.3347%, are not C1-qualified in this screen; zero qualifying states is not proof of safety or absence of native execution changes.

For price/DD restoration availability only, use the first completely post-trigger closedUTC4h that reclaims ORIGINAL trigger mark in leg direction while ORIGINAL DD<=35%, then a following quote retaining both predicates. This is not actual cutVWAP, not the changed candidate account, and not confirmed admission. All3 proxy restores precede original first quantity reduction; actual ordinary-exit decisions and native ownership remain unknown. October proxy re-crosses the original trigger mark at21:04 after20:01 proxy restoration: DD hysteresis and4h confirmation do not eliminate relapse. January/November have no observed trigger-mark recross before original cycle end, which does not prove candidate profitability.

Diagnostic signed re-entry price gap plus two0.055% taker fees, normalized per unit original trigger mark, is1.208512% October,1.885345% January,0.973925% November. This excludes actual gaps/slippage/changed target/partial fills/funding and is NOT cut/restore PnL or an amount to subtract from TOTAL. June originally reclaims trigger price at08:48 but has no within-cycle ORIGINAL DD35+4h restore; the original native cycle ends June7. Thus the deliberately stronger account-risk hysteresis can miss profitable price recovery and permanently retire some actual cut lots. No missed-profit amount is identifiable.

The temporary5%-cushion cap was preparation only and is abandoned. Its ungated8 events include5 original-below50 opportunities; the5% assumption was unsupported and is absent from finalC1. These preparation files are retained with explicit separate names, not presented as additional candidates or economic outcomes.

## Root cause and state adequacy

Observed mechanisms remain distinct: October SOL alpha/dominance while BTC offsets some loss; January BTC-flat SOL residual; November BTC-only short squeeze; June/late2026 inherited realized cash losses plus new positions. A current-open-loss dominance gate targets the first three without imposing permanent caps on every new parent after a loss. It also triggers late in June, demonstrating imperfect separation.

E4 trace provides native qty/side/currentavg/marks and paired native cash/equity adequate for this descriptive scan. It does NOT provide as-of accepted parent completion, pending/ACK/cancel leaves, ordinary/mandatory priority, right consumption or exact domain-group IDs. Finalized orders/fills cannot supply those flags at arbitrary earlier minutes. Therefore4 opportunities are not4 confirmed C1 actions, nor are3 proxies3 implementable restores. New observer-only proposed-decision and actual-fill/credit transitions are a source preflight requirement. Signed funding stays UNKNOWN from the saved funding schema.

C1's exact state, lot/TP/SOL entitlement contract, completed-entry and native timing checks are frozen in `owner-contract.md`; independent review and explicit root source GO remain required. After root choice, implementation can prove feasibility in focused native fixtures and emit minimal causal receipts. No historical run is justified by screening alone. Root budget remains0/4started; no reserved/active engine from this owner.
