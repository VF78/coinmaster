# CM-113 completed native comparison — lifecycle fixes + 30m cap

Period **[2024-09-01,2026-09-01)**, initial **10,000 USDT**, real canonical Bybit1m inputs, reserve0. Source commits d219ee6 / d7d18cd; source reviewed at d7d18cdc22c0ebb918f202eb9168fcc3159ed9e1.

| Measure | Selective control / cap10m | Corrected variant / cap30m |
|---|---:|---:|
| Terminal ACTIVE+RESERVE, USDT | 3,747,041.97080334 | **5,146,884.95718200** |
| ROI | +37,370.41970803% | **+51,368.84957182%** |
| Native fees, USDT | 597,517.54289494 | 1,144,089.96955003 |
| Maker / taker fees | 43,410.53666080 / 554,107.00623414 | 79,613.24346386 / 1,064,476.72608617 |
| Maker / taker notional | 217,052,683.3040 / 1,007,467,284.0616 | 398,066,217.3193 / 1,935,412,229.2471 |
| BTC fills / entries | 311 / 105 | 311 / 105 |
| SOL fills / add-fills | 221 / 110 | 191 / 95 |
| Native cash maximum relative DD | 62.46697029% | 62.30510948% |
| Liquidations / terminal positions | 0 / 0 | 0 / 0 |

**TOTAL delta +1,399,842.98637866 USDT (+37.35861507% vs control).** Fees increase546,572.42665509; this is not a fee-only improvement. Exactly one economic native run, fresh engine/funding journal, all1,051,200 rows/source and4,206,260 events; completed9m02s, exit0. One setup attempt previously stopped at the fresh-directory CLI guard before engine creation; failure receipt preserved in the job.

Only config changes: opt-in research_v0_selective_lifecycle_repairs=true and candidate.max_parent_notional10m→30m. EMA, BTC/SOL multipliers, z/quantiles, TP fractions, fee floor, positive TP2, funding and protection settings remain unchanged. Data/policy/interval/warmup/seed identities match. No optimizer, deployment, seal, pilot config, orders or credentials changed.

98 relevant tests passed; one substantive independent-review margin correction followed by four focused genuine native account/order proofs. Compile/diff checks pass. Review GO: exactd7d18cd. Canonical missing native reservation was reproduced; only actual reservation credit is now allowed, with reduce-only/opening-order distinction. The margin module and funding implementation remain unchanged.

All556 native orders terminal; all BTC/SOL quantities reconcile;76 omitted levels/76 actual causal activations. All actual BTC entry fills comply with30m: maximum29,999,986.8278; nine q1 lot clamps. Ordinary SOL half/full and zeroBTC partial fallback branches are proved by focused native tests; this full run did not exercise those partial cases.

Attribution from actual fills: BTC delta+1,594,058.42524491; SOL−221,786.9305; unallocated native cash/funding/other residual delta+27,571.49163375. These reconcile combined TOTAL delta but are not individual-fix causal PnL. First divergence is a blocked SOL add on2024-12-23; cap binds much later. Aggregate signed funding is UNKNOWN, count1321(BTC900/SOL421), not zero.

No new demonstrated trade deadlock or quantity defect was found in this completed run. Remaining ROI hypotheses, not implemented: genuinely affordable SOL child sizing after detailed native denial evidence; causal SOL add eligibility near timeout; bounded cap attribution/refinement within approved constraints. Positive TP2 fee-negative rules stay excluded. Raw net_submitted_btc_qty is a pre-clamp proposal in nine records; admitted_net_quantity and confirmed fills are authoritative.

[Comparison JSON](comparison.json) · [Comparison CSV](comparison.csv) · [Detailed audit](audit/README.md) · [Findings JSON](audit/findings.json) · [Closing-fill CSV](audit/economics.csv) · [Independent review](independent-review.md) · [Run receipt](native-run-receipt.json) · [Full native JSON, gzip](native-result.json.gz) · [Funding journal, gzip](native-funding.sqlite.gz).

Full raw JSON SHA2568e4a387260688729563258b84befe34b0bef2479f2fbe369c621fab9cc3281e2. Separate journal raw SHA256221745c0199a2edb72a54cd59934209cc4aaac39b7c3d421ca28261bc56a263f. Immutable originals remain in /var/lib/coinmaster-native-gui/data/runs/jobs/cm113-selective-lifecycle-cap30m-20261009/result-run.

Result remains **NOT_FAITHFUL_DIAGNOSTIC / ranking_eligible=false**: real1m closes, synthetic zero-spread quotes/size1000, no historicalBBO/L2/impact/slippage proof. Full marked-equity DD and signed funding attribution are unknown. This is measured comparable research, not a live ROI guarantee or deployment approval. Pilot installed81e6318 remains activePID2009732/NRestarts0.

## Implementation receipt retained


Source commit: d219ee6972bb50982e5a683969a862b2ce3f83a6, canonical VPS checkout /root/.openclaw/workspace/coinmaster/coinmaster, branch codex/nautilus-btc-sol-mvp. Base 3b9b9c1386385d6655bcc130dadb3aed59744eef. Source/tests only; no full research run, pilot/deploy/service/seal/credential action.

## Version and invocation

New explicit strategy/diagnostic config: research_v0_selective_lifecycle_repairs=true. The CLI additionally replaces only Candidate.max_parent_notional with 30,000,000. Existing defaults and archived controls retain old behavior/cap. New result label: v0-selective-lifecycle-cap30m.

Ops invocation from the isolated runtime bind with authoritative source/var/data and source/var/data/runs/tp-fee-floor-113/v0/v0.json inputs:
.venv/bin/python -m coinmaster.research.native_baseline --research-v0-execution-repairs --research-v0-deferred-selective-zero-tp --research-v0-selective-lifecycle-repairs --control-report var/data/runs/tp-fee-floor-113/v0/v0.json --data-root var/data --artifact-dir <fresh absolute path>

Not executed here. Existing immutable V0 input/data/fee identity and fresh-dir guards retained. Fee floor, positive TP2, EMA/z/TP fractions/multipliers, funding and deposit-protection settings unchanged.

## Root causes and changes

- Ordinary SOL half/full IOC child terminals dropped the accepted decision's remaining target. A bounded accepted-target metadata map now retains fixed normalized target leaves while the existing domain child/native mapping/quote queue handles execution. Confirmed fills alone subtract leaves. Native cancel/reject/expire/denied terminals can create one residual child after 60s; submitted/unknown ACK and queued children block duplicates. Residual quantity clamps to actual native position. Half completion/cooldown still uses cumulative native lots; no half-to-full promotion. Adds and ordinary new SOL exits cannot compete with an owned exit. Mandatory timeout, forced group, liquidation, terminal and deposit paths clear ownership and retain priority.
- Selective zero-market BTC fallback partial IOC terminals had no next-quote residual. The same metadata/queue mechanism retains only zero-suppressed fallback leaves; a retry requires causal executable quote eligibility at the original confirmed-entry VWAP/wave threshold. Adverse quotes preserve conditional leaves without submitting. Positive-price native resting TP/fallback handling and actual-fill proportional SOL rights remain unchanged.
- Omitted reference touch could latch before entry earned any confirmed fraction. New version records touch only with positive confirmed BTC quantity and positive omitted-level earned fraction. Existing current paired executable-session/backfill guard and once-only activation remain. Same-q1 omitted-level touch is incompatible with that branch's strict passive-reference selection; native proof covers immediate q1 passive fill followed by q2 reference touch.
- Terminal flat early return omitted local q0 cleanup. New version terminalizes unsubmitted queued/domain/selection plans before declaring FLAT, locks future increases, and keeps submitted/unknown ACK parents AWAITING_NATIVE_TERMINAL. No synthetic rejection or submitted parent cleanup; native terminal confirmation is required.
- Admission double-counted current locked collateral by comparing all prospective IM with native free. Final corrected version compares max(0, prospective policy IM+MM minus bounded actual native reserved credit) with native free. Credit per existing position is min(fresh current policy IM+MM, actual native per-instrument IM+MM); initial-margin credit is excluded when any opening/unsupported order shares that instrument. Cache-confirmed reduce-only targets retain position credit. Missing/account-wide/unreserved margin has no invented credit. Native free retains existing native IM/MM and open-order reservations; no refund/reconstruction of native cash or unrealized collateral is fabricated. Native unrealized PnL at that exact policy mark snapshot feeds gross/equity admission; native free remains the conservative collateral budget. This is a fresh total-policy requirement gate with bounded actual-reservation credit alongside unchanged native checks, not replacement accounting.
- q0 saved lots had no final q1 cap check. Final normalized BTC quantity is floor-clamped to max_parent_notional/current executable-side price/native lot step. Gross q0 reference allocations and SOL H remain fixed; actual q1 net-planned denominator and TP allocation use admitted/fill quantities. No whole-trade rejection except cap below one valid lot/minimum/unchanged admission gates. This guarantees pre-submit normalized notional; a market fill can still slip.

## Verification

Authoritative full relevant log: verification.log, SHA256 86b9fd33dbbf4f7d8681bf66f673cb7751dbdbf54f07640d356cef92fe7535db.
Command: runtime/.venv/bin/pytest -q tests/test_wave_overlay.py tests/test_wave_native_integration.py tests/test_native_baseline.py (working directory runtime).
Result: 98 passed, 80 warnings in 63.55s. Warnings are existing Pandas Timestamp.utcnow deprecations.
Python compile and git diff --check pass.

Native proof:
- SOL half target1000/full target2000, initial partial IOC250, authoritative cancel and 60s cadence, residual native fill completion in two sequential episodes, confirmed flat between episodes; half never becomes full.
- BTC zero TP partial0.100 at101, adverse99 after cadence causes no retry, eligible102 completes native target; proportional rights at adverse quote strictly between0 and1, then1 only after confirmed residual fill.
- Actual pinned native MarginAccount total9994, IM6000/MM500 locks produce free3494; fresh BTC200 mark yields native unrealized profit6000 for equity/gross. For the corrected proof fresh BTC110 yields native unrealized profit600 (gross limit0.73); policy prospective minus actual bounded6500 reservation permits SOL10*100; SOL50 fails; stale/future policy marks fail. Cached daily100 marks cannot decide the admission.
- Long/short q0 gross1000 at30000 and q1 at30030 clamp to999.000 BTC, native q1 notional29,999,970; one more native lot would breach30m. Gross reference1000 and H30,030,000 preserved; normalized TP targets sum999000 lots.
- Pre-fill touch then real partial entry/non-touch does not latch; later real touch does. Native immediate q1 fill then accepted paired-session q2 touch grants omitted rights exactly once. Existing stale/backfill guard tests retained.
- Unsubmitted terminal q0 queue/domain plan clears; submitted unknown native ACK stays pending/unflat until actual cancel. Denied accepted SOL child preserves target; unknown ACK cannot duplicate retry; forced group clears local residual owner.

Initial focused development checks caught fixture audit-key, native stage-boundary/default fraction/JSON tuple-list assumptions and disabled-path unbound clock access; corrected before final verification. No historical ROI archive or full24m run inspected/executed. Corrected TOTAL remains unknown pending independent review and separately coordinated comparison.


## Independent-review correction (supersedes initial margin basis)

The pre-correction incremental-policy gate was invalid on canonical pinned1.231 CustomData delivery: BybitTierMarginModule((),...) never receives those marks in pre_process, while strategy policy receives them. A bounded exact native-engine proof shows total/free9994, native IM0/MM0, current fresh policy6019.8, SOL50 incremental5025, and admission True before correction despite total prospective11044.8. The module/funding model is unchanged.

Final gate credits only actual native per-instrument reservations, bounded by current fresh policy cost. Opening/unsupported native orders get no IM credit; confirmed reduce-only TP can retain it. Native free stays untouched, and account-wide/missing locks get zero credit. After correction the same canonical SOL50 is denied and SOL10 admitted.

Separate actual pinned MarginAccount/native order proof: actual native total9994, IM6000/MM500, free3494. An opening GTC order sharing BTC suppresses IM credit and SOL10 is denied; a confirmed reduce-only GTC target retains bounded position credit and SOL10 is allowed. SOL50 denied in both; account free unchanged. Fresh positive-PnL gate/stale/future mark proof retained with BTC110 rather than200, making its actual native reservation shortfall explicitly covered.

New proof artifacts: margin-review-before.log (one passing pre-fix repro) and margin-review-after.log (four passing corrected native cases). Prior98-test verification applies to unchanged paths; no broad suite or full24m run repeated during this correction. Final correction commit recorded by coordinator.
