# Frozen S0 BTC lifecycle audit

Zero TP1/TP2 thresholds follow the selected wave statistics. Making all three positive is not an established defect fix. Exact S0 has no fixed downside BTC stop.

Identity: scientific source75ffc9c69e9d79c4da4cd0614634a3eeba48d716, TOTAL6,077,107.23887483; settled DD66.2569148647%, callback DD66.3187802497%. Three core source hashes independently matched frozen pins. This is not installed pilot or a current management variant.

## Zero thresholds and real fills

Frozen domain/wave_overlay.py:175-193 uses completed previous same-side EMA waves, next-day open entry, daily CLOSE favorable-return maximum clamped at0, and linear quantiles0.10/0.30/0.60. Intraday highs/lows do not enter MFE. Valid zero order statistics produce zero targets. Native level0/1/2 means TP1/2/3, not an additional TP0.

Existing selected-S0 parent CSV has105 parents;45 passive plans omit level0,31 also omit level1:76 omitted allocations. These are omission counts, NOT all zero threshold counts.

strategy/wave_overlay.py:1457-1529 freezes q0 gross lots/reference then classifies its passivity on fresh q1. Passive branch omits zero BTC allocations; real net fills earn proportional SOL authorization. Lines1531-1555 require earned fill plus executable reference touch and paired accepted session to activate it. No fake TP fill occurs.

Full branch keeps volume but suppresses resting zero targets. domain:407-416 waits for daily favorable close return>=0, then uses actual native MARKET/IOC. strategy:1412-1419 retains owned leaves on adverse executable quotes. Zero is neither automatic immediate exit nor net profit: actual price/fees matter. Older selective lineage found75->73 gross-positive zero fallback fills; two lost fallbacks later closed REGIME. Those counts are not exactS0 counts.

Positive targets (domain:562-586) use P0*(1+side*threshold), original gross-plan fractions0.2125/0.2125/0.575 and native integer lots. Completed split permits resting reduce-only postonlyGTC; already crossed positive targets become real MARKET/IOC/TAKER (strategy:1907-1918, split_cover:186-194).13 catchups matched13 native fills;7/13 lost after allocated entry/exit fees, aggregate-1,817.86exfunding despite positive P0 thresholds. Actual BTC_REDUCE fills earn proportional SOL rights (domain:495-520); submit/ACK alone do not.

## Entry, split and PLANREF

Dailyclose>EMA34 means long, else short; beta0.2..4 and >=8 completed same-side waves in730d gate new episode (domain:361-384). Sizing long5.5/short7.875 times marked active equity, cap30m (strategy:945-950). This is not a15m pattern/reversal entry.

Accepted net lots split half first, remainder postonly0.25% better vs completedfirsthalf actual VWAP. Deadline4h/nextUTCday-1min or early positive target switches remainder to IOC after cancel/ACK; unknown ACK prevents duplicate (split_cover:88-206).

PLANREF freezes firsthalfP0 only for TP/dailyfallback/best_f/trail/earlyTP. Native blended VWAP/cash/PnL remain actual. H=grossReferenceQ*actualblendedVWAP/beta (domain:560). Blended025 management gave4.759m and lost one calendar parent; PLANREF restored105 permissions and6.005m. PositiveTP IOC fixed missed crossed targets and raised TOTAL to6.077m (+71,619.43). These are already implemented historical fixes, not a new opportunity.

All105 accepted plans filled:66limit/17deadline/22earlyTP. Mean normalizedentrycost benefit4.5178bp, worst-77.3137bp. Mean waiting1.395h, max4h1min. Discount helps price/fees; delayed fallback can chase an adverse move and alter exposure timing. Entry cost benefit is not an additive explanation for all TOTAL differences: capital and future quantities also compound differently.

## Actual downside exits

REGIME is daily EMA-side reversal; TRAIL requires best_f>3%, then f<=best_f-0.03, measured from dailyclose relativeP0 (domain:388-395). This is a3percentage-point decline in entry-relative return, not a standing intraday3%peak-price stop or initial lossSL. Group CLOSE_ALL owns native reconciliation.48 parent records contain REGIME,2TRAIL; these are parent-reason occurrences, not fill counts.

Resolved config has btc_close_stop_fraction=null, portfolio_loss_limit_fraction=null, DP OFF, fee floor OFF; BTC20/B25 research off. No fixed BTC downside stop guarantees DD50. Native margin/admission restrict increases; terminal settlement is not a trading stop. Historical liquidation applicability remains unvalidated despite zero counter.

## All-positive TP proposal and known issues

Removing zero-wave observations or adding positive/fee floors changes empirical distribution, entry netting, exposure, SOL rights and compounding. It is an economic policy, not a missing-value repair. Older pre-S0 fee-floor removed82 negative feeallocatedTPs but TOTAL fell3,386,491.65->2,661,216.57 (-725,275.08). This refutes automatic portfolio benefit, not an exactS0 comparison. ExactS0 alternative TOTAL/DD are UNKNOWN.

Old lifecycle findings must not be transplanted blindly: frozen source already has earned-before-touchguard1537-1538, q1cap normalization1859-1865, acceptedreduction residualownership2012-2020 and crossed positiveTP IOC1907-1918. No new established execution defect explaining66%DD or promising50/90 was found in this narrow pass. New entryconfirmation/SL/allpositiveTP value remains unproven.

Historical NOT_FAITHFUL_DIAGNOSTIC: L2/spread/slippage/historicalmargin/liquidation qualification absent; signedfunding UNKNOWN. Exact source/report hashes and code references in source-audit.json. Only the two owned report files written; source edits/test/native/model runs/market streams/deploy/pilot actions:0.

## Requested final clarifications

Structural resolution mismatch: domain175-193 anchors each statistical wave to next-day OPEN (bars[start+1].btc_open), samples dailyCLOSE fromstart+1 throughend inclusive the first opposite observed signalbar, and clips maximum at0. ExactS0 native_baseline863-894 matches TP against1mEXECUTION-CLOSE synthetic bid/ask, marks1mMARK-CLOSE. OHLCsourcebars exist only in other disabled variants, so this is DAILY-CLOSE statistics versus1mCLOSE execution, NOT exact intraminutehigh/low execution. A positive intraday move can therefore coexist withzero dailyMFE. This is a design-resolution difference; economic advantage from changing it is UNKNOWN. A future completed-wave post-entry1m/highlowMFE hypothesis requires separate consent/precheck and must exclude first-dayhighs/lows BEFORE causal entry; no catalogue or threshold run here.

Generic BTC_REDUCE is not automatically zeroTP: domain407-416 emits reasonNone for ANY eligible non-omitted threshold missing a resting owner, including positive fallback. strategy2044-2047 preservesreason during residual requeue. Root-supplied L0=42/L1=31 must not be relabeled zero without per-entry wavevector. FULL entryaudit does not export thatvector per root; no complete vector located in inspected reports. Recovery from an existing thintrace is UNKNOWN, not a reason to reuse olderV0zero labels.

Reentry: strategy2595-2611 clears the episode only after nativegroupflat/order/pending reconciliation. REGIME immediately reruns current accepted dailydecision, so a fresh opposite-side episode may be created on that same signal after closure. TRAIL does not immediately rerun; a subsequent accepted dailydecision can reenter the SAME EMA regime if beta/wave/admission gates pass. ExactS0 has no extra fixed cooldown/permanent trend lockout. BTCflat from TP alone does not create a new episode while old group/SOL remains owned. Each genuinely new episode recomputes wavelevels/sizing/beta/H and obtains a new actual firsthalfP0, with long5.5/short7.875 preserved.

Trail example: longP0=100, best DAILYclose110 givesbest_f=.10; laterdailyclose107 givesf=.07 and triggersf<=best_f-.03. It is3percentagepoints of entry-relative return afterbest_f>.03, not3%lossSL. This is a decision condition, NOT a nativefill promise at107.

Stats-agent saved-export crosscheck (direct result, no new reviewer stream):155 actual BTC reductions;0 share first-entry timestamp and0 share completed-entry timestamp. Generic73 (L0=42,L1=31) are all delayed, all price-positive versus both frozenP0 and actualblendedVWAP, none at<=1bp return. These facts directly refute immediate-at-entry execution on this saved path; they do not establish fee-net profit. TP2 count28 includes13 positiveIOCcatchups. FULL frozenwavevector absent, so generic73 zero-wave attribution remainsUNKNOWN.
