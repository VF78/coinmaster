# Independent read-only source-flow audit

Reviewer risk_candidates_review; HEAD568e9dc, economic winner source d7d18cd. Existing116-test GO applies to498a8fe optional variants, both OFF in control. Two focused scratch native lifecycle probes were authorized by root; no historical engines, source edits or fixes.

D=runtime/coinmaster/domain/wave_overlay.py, S=runtime/coinmaster/strategy/wave_overlay.py, N=runtime/coinmaster/research/native_baseline.py.

| Flow | Source proof | Classification / consequence |
| --- | --- | --- |
| Daily features / prior waves | D97–130,172–193 | Causal closed-bar features; strictly completed earlier waves. Intraday mark freshness does not refresh daily z/EMA. |
| BTC entry | D346–368; S906–920 | One attempt/index/side; valid beta/new UUID; paired daily native equity determines multiplier/capped parent. No downside stop. |
| Selective lifecycle | S749–817,1038–1093 | q0 to later fresh q1,30m expiry/session/terminal gates; actual normalized parent clamp, gross reference retained. |
| Native admission / margin | S1382–1449 | Fresh marks/tier/gross/free admission. Existing50× gross admission is not a portfolio loss limit or guarantee of hedging. |
| Confirmed TP / rights | D456–506; S819–850 | Actual native fill VWAP/lots; proportional rights. Omitted rights require earned real fill, later reference touch and executable session. |
| BTC exits | D372–379; S1264–1360,1698–1699 | REGIME or daily profit trail; best favorable daily entry return must exceed3%, then3-percentage-point retrace. Native cancel then reduce-only IOC remaining actual quantity. REGIME intentionally reevaluates current decision after flat; TRAIL waits later daily decision. Same-day REGIME behavior is intended/tested, not a cooldown defect. |
| SOL adds | D419–426,537 | Opposite BTC side, persistent earned rights; H=(gross BTC reference or initial quantity)×actual BTC VWAP/beta_entry. Each level H×multiplier×right fraction less filled notional. H does not shrink with BTC reductions or equity losses. SOL becomes residual directional exposure, not guaranteed hedge. |
| SOL z / beta | D409–414,513–514 | Current rolling beta/relative/mu, sigma frozen at first SOL fill; size beta_entry frozen. Invalid current beta blocks adds and ordinary z exits lack z; timeout/group exits remain. Intended fallback risk; archived occurrence unmeasured. |
| SOL exits / timeout | D431–448,515–517; S1195–1261 |14-calendar-day hard timeout from first actual SOL fill, checked daily. Half z≤.375; full z≤.125 strictly after stored half decision. Fresh adds reset half progress. Accepted partial exit retries each minute; timeout preempts adds/resting SOL. REGIME/TRAIL group exits supersede. |
| Stale adds | S852–904 | Rejects changed-session old adds, new regime/exit, expired holding. Same daily session remains valid by design; no intraday z recompute. |
| Terminal | S1712–1713 | Selective terminal waits unresolved pending submissions; forced native settlement exported separately. |
| Execution / observation | N779–803; minute_risk94–124 | Paired close marks, daily signal, close quotes. Synthetic zero-spread size1000; cancel ACK can match previous cached book. Native held OHLC endpoints are conditional bounds, not synchronized venue path. |

## Source edge cases independently reproduced

**P1 ordinary close / late opening ACK:** S1686–1699 ordinary REGIME/TRAIL reconciliation ignores unresolved opening submissions: pending wait S1690 and late ACK cancellation S1668–1671 are PORT45-only. Terminal has pending wait S1713. Refined native probe observes OrderSubmitted with open-order cache0/pending1, seeds already-completed ordinary close ordering, then actual native ACK/fill leaves1 SOL position with episode=None. Close-completion ordering is seeded; occurrence in the winner is UNMEASURED. Focused future regression should delay opening ACK across ordinary group-close completion and assert no false flat/reentry, cancel late accepted opening and close any actual late fill. No archived loss or saved money is assigned to this edge.

**P2 cross-day half completion:** Accepted half retry retains original dailyindex S1216–1218; completion stamps that submission index S1565–1566. Native half500 fills250+250 while actual dailyindex advances0→1; stored halfindex0 permits D447 SOL_EXIT remaining500 within the SAME actual completion-day callback/index1. This is a completion-ordering defect candidate if the intended rule refers to actual completion day. Existing same-day partial/next-day full domain fixture does not test cross-day retry. Winner occurrence, fees/ROI/DD impact remain UNMEASURED; no source fix in this audit.

Probe scripts/logs are retained locally in this report folder. Reviewer provided combined-log SHA eb7968b31f2ccf8ebad7d3bc0d618a8f8f34dea086967407302285332e4beda6 and refined ACK log SHA814d1d0946b641cf77037f1f1a8adb90090018c3764f1662d65c1494e5c25e5c. Exact individual file hashes appear in artifact-hashes.json.

## Prior fixes reused, not new work

a9c4d62 causal earned rights; d219ee6 accepted SOL partial exit ownership/terminal pending/cap30m; d7d18cd actual native reserved-margin credit. Existing native integration proofs: test_wave_native_integration.py1795 partial SOL/two episodes,1911 earned-before-touch/terminal unknown ACK,1949 fresh marks/locked credit,1987 actual q1 cap,2019 denied owned child/unknown ACK,2047 immediate real entry then reference touch; older1513 timeout retry,1543 stale queued add,1721 stale q1 expiry. These fixes do not eliminate the separately reproduced ordinary-close pending edge or cross-day half-index edge.
