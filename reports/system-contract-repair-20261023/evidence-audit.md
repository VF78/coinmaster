# SC-00/SC-02 evidence audit

Exact E4 archive and unchanged historical source `bd04c9b` were reused. No historical engine, S0/E4 rerun, ML fit, service or deployment was performed. The existing72-pin S0 audit was reused; only focused E4 paths and native archive fields were recounted.

| Claim | Status | Evidence |
|---|---|---|
| synthetic_quote_1000 | VERIFIED | Synthetic BBO size; not venue historical liquidity |
| SOL_96_of98_1000_cancel | VERIFIED | Saved native field recount in JSON |
| BTC_zero_TPs | VERIFIED | Saved native field recount in JSON |
| q1_local_sensitivity | VERIFIED | Pinned Nautilus Price(Decimal,precision1), BTC native tick0.1, of shifted quote. Branch classification only; no synthetic fill/money claim |
| SOL_BTCflat_linkage | VERIFIED | Saved native field recount in JSON |
| SOL_H_gross_additive_rights | VERIFIED | H gross BTC reference, additive budgets, actual reductions earn rights, group flat gates next BTC; source+saved72pin audit reused |
| R2C_XS_calendar | VERIFIED | P0 exact XS verified21checks; reuse archived field-by-field comparison |
| R2C_flat_fix_no_economic_change | VERIFIED | Saved native field recount in JSON |
| continuous_SOL_hedge | CONTRADICTED | SOL-only durations and cycles; selectivealpha/sourcegate, not continuous hedge |
| H_BTC_predictive_benefit | HYPOTHESIS | Offline causal data/prefix tests do not prove economic benefit; native candidate required |

The synthetic1000SOL governor is verified:98 SOL_ADD orders,96 filled1000 and canceled remainder, plus fully filled54.5 and197.5. Largest request24Jul2026 was395673.9SOL and filled1000. This is fixtureBBO size, not demonstrated venue liquidity. Source daily-index retry and additive levels are verified; explicitchild-policy equivalence belongs to SC-01 and remains NOT_TESTED by this offline evidence.

Causal exact-source TP reconstruction confirms TP1zero83/83 and TP2zero58/83. Q1 perturbation uses pinned native Price precision1 (BTC tick0.1). Changed branches by signedbp: {'-5': 25, '-2': 9, '-1': 6, '-.5': 3, '-.1': 0, '.1': 1, '.5': 7, '1': 10, '2': 17, '5': 30}. This measures branch sensitivity, not full native strategy economics.

Native fill durations give56.91671376457894466423470174% of SOL-active time with BTCflat and13/25SOLcycle starts at BTCflat. H uses original gross BTC and tierbudgets add. Existing native R2C/XS comparison confirms337matching BTC fill calendars/prices/reasons with292quantity differences; fullR2/R2C traces and nativecash/fills/orders/funding prove the flatpredicatefix had no observed economic effect. The localized Oct/Jan improvement and later compoundedBTCdrawdown cannot be attributed to the corrected floatdefect.

The dataset has83actualparents:50first and33repeat within50actualEMA waves.81potentialMAE/MFE labels are completed,2are censored incomplete waves. Labels use minuteMARK closes strictly after first actual fill through completedD1EMA-switch; they remain potential remaining-wave movement, not actual trade losses. ATR14 uses exact E4 closedOHLC Wilder seed and divides by frozenq0wire. First actual fill label price, native completedfirstchild management PLANREF, and blendedmoneyVWAP are separate fields.

Strictpast Q90 has24eligible repeat decisions;19wouldreducek. This is a descriptive offline pilot activation estimate on archivedE4parents; an H_BTC path changes capital/parents/SOLrights and requires full native validation. Decimal linear(n−1) interpolation, min8eachgroup, sidespooled, ready_at<decision are frozen. Available groups/independentwaves/Q90/k/fallback are exported for everydecision.

Decision-held inventory, pendingorders, nativeinternalq0equity and exact internalE4gate state are not fully exported. They are UNKNOWN in the archive dataset; acceptedparent does not prove the full gate-state vector. Candidate hooks owned by the soleengineowner must provide those fields. SC-02 internal decision-state coverage remains pending hook evidence; this offline archive does not close that acceptance item. Signedassetfunding remains UNKNOWN.

Offline archive eligibility/invariance tests (precomputed completed labels; not a live-hook prefix integration test): 28/28 PASS. Tests include futureparent/futureMAEinvariance, exact feature/ATRprefixes, strictready equality exclusion, incompletewave exclusion, native tick rounding, parentweight/firstrepeat and missinglabel handling. See data-tests.json and canonical-source data_source.py.

The scoped active-source rule register has43active base/E4 rows with source, purpose, origin, separate implementation/economic statuses, ablation evidence, problem, KEEP/FIX/TEST/DEFER and exact originalrequest0–4 mapping. Numerical choices without isolated robust evidence remain HYPOTHESIS/NOT_TESTED. Correct nativeownership is kept; no claim of arbitrary intent is made.

Existing11externalmethods/sources, twoactual2×2TOTALcontrasts, exposure/cashattribution, riskheadroom and minimumvariance-versusinversebeta calculations are reused in rule-registry.json. New work applies local sensitivity, causal sampleavailability and native lifecycle recounts. PBO/OOS/portfolio benefit are not invented from incomplete evidence.

Seven recipe-specific E4peak/trough/recovery snapshots and exactDDidentities are in seven-episodes.json. Full candidate accounting, all24months/newglobalmaxima, explicitpolicyequivalence and H_SOL/H_BTC outcomes remain separate SC-01/03/04/05 acceptance work; this pack does not assert DD50/90 success.
