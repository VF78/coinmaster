# CHOP_PAIR_50_NET_v1: recovered native result

**NO_ECONOMIC_GO.** The sole economic candidate decisively fails the DD<=50% goal.

| Native metric | Candidate |
|---|---:|
| Terminal active / TOTAL, reserve 0 | 205.42245876 |
| ROI on seed 10000 | -97.9457754124% |
| Global native-minute DD | 99.8486498555% |
| Conditional upper-to-later-lower OHLC bound | 99.8488859811% |
| Actual native commissions | 11256.90313488 USDT |
| Native order rows / filled-order rows | 217 / 186 |
| Terminal orders | 157 FILLED, 60 CANCELED |
| Native signed remaining BTC / SOL quantity | 0 / 0 |
| Genuine SQLite funding records | 489: BTC340 / SOL149 |
| Complete source minutes / native observations | 1051200 / 3153600 |

Status is **PROVEN_DURABLE_NATIVE_RESULT_INCOMPLETE_AUDIT**, not a fabricated replacement for the original full report. Values above come directly from retained native account-equity samples, native order/fill exports and the fresh funding SQLite journal. The final full gzip pass verifies every contiguous minute of [2024-09-01, 2026-09-01), with exactly three native observations per minute and terminal positions empty. SQLite integrity is OK. Signed aggregate funding remains UNKNOWN because the existing audit stores post-account totals, not component cash deltas.

The final nonflat sample is 2025-04-06 18:37 UTC: LONG 7000 SOL at actual basis 121.88428571428571 and mark105.62, native cash114392.09795879 and marked equity542.09795879. Seven real reduce-only taker SOL SELL fills of1000 at that timestamp complete group closure; the next minute is native flat with cash205.42245876, which remains flat through the interval end. Three conditional OHLC/tier upper-bound maintenance breaches are retained. The native-account MM column itself is0; the source uses a separate pinned tier policy. Native margin-guard liquidation/lockout is consistent with this intraday close and retained margin evidence, but the exact liquidation count and internal domain/pending/gate state were not durably exported. They remain UNKNOWN. No claim of a proven exact liquidation counter or final internal gate state is made.

The native engine completed its event feed and wrote native exports, minute-risk summary and canonical funding journal. The outer packaging runner then rejected a serialization-only config delta: preexisting code now exports research_conditional_sol=false, whereas the winning control omitted this disabled default. A config-only execution of the frozen source assignments proves this is the sole extra key besides the approved carry flag; no engine or monetary code was run for that diagnosis. Original in-memory result/carry admission, rejection, exit, skipped-signal and grant audits were therefore lost and remain UNKNOWN. No economic rerun was performed to replace missing metadata.

Code checkpoint fdcefd633b1e611135d2a2573dbc6ad8dcc5cece remains frozen/default-off. Focused acceptance98PASS and one independent order/money review correction preceded the run. All72 snapshot files remain unchanged;89 source/data/policy/control pins were verified inside the read-only namespace. The initial zero-event startup omitted static public venue inputs; its empty attempt/log were preserved, and the three corrected public files match the winning snapshot hashes exactly. The sole actual event-processing attempt used a distinct fresh funding UUID211f652651c24edbb0df2f62aa2d3be1.

Retained native artifacts, exact hashes and qualifications are in engine-recovered-native-result.json and engine-final-manifest.json. Pilot PID2009732/NRestarts0 remains active; the research slice is empty. No source change, economic repeat, optimizer, deployment or pilot restart followed the negative result.
