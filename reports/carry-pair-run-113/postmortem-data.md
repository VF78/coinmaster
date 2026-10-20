# CHOP_PAIR_50_NET_v1 native forensic

Scope: existing durable native CSV and risk traces only. One synchronized streaming pass per trace, no new economic run, replay/matching/PnL engine, optimization, or reconstructed carry/liquidation/domain audits. Signed funding and realized asset PnL components remain unknown.

## Observed actual fills

The first eight fill-report rows are identical. On 2024-09-17 00:00Z candidate sells 222.7 SOL at131.38 while retaining1.219 BTC long; control instead sells1.219 BTC reduce-only at58159.9 and opens BTC short at00:01/00:34. At16:08Z candidate closes SOL222.7 at134.73 and BTC1.219 at61217.2. This changes BTC calendar and subsequent equity sizing; it is not an additive independent hedge over an unchanged BTC baseline.

Terminal SOL exposure is built by native BUY1000 fills each midnight Mar31 and Apr1–6 at124.73,124.45,126.63,117.31,117.07,122.75,120.25. Native final basis121.88428571428571 and quantity7000 are directly persisted. BTC final5.642 reduction is Apr6 18:04Z. Seven SOL SELL1000 reductions at105.63 occur20:37Z, eachfee58.0965. Last trace exposure at20:37Z has nativecash114392.09795879, nativeU -113850, equity542.09795879; permanentflat205.42245876 appears20:38Z.

Same-date control explicitly sells SIX SOL1000 reductions Apr2 00:00Z at126.63; candidate instead buys1000 SOL then continues daily additions. Control opens freshBTCshort Apr3 and finalBTC reduction isApr6 18:07Z. ControlSOL additions Apr3 00:02Z at117.05 thenApr4–6 yield4000basis119.28 bycandidatecollapse. Thus quantity, costbasis, cashbuffer, BTCcalendar and exitpath all differ beforeterminal.

Nativefee total11256.90313488 consists BTC7786.89155248 andSOL3470.01158240. The final nativeSOLunrealized loss113850 alone is10.1 times allfees. Fee tuning cannot by itself explain/repair this collapse; this is not a counterfactual ROI estimate.

## Interpretation and limits

The code analyst identifies the final daily1000 additions and independentBTC TP as ordinaryalpha outside activecarry: activecarry blocks domainDaily and independent intents and closes whenBTCquantity changes. The observed SOL-only tail therefore does not establish a carry-orphan bug. It establishes an unprotected exposure and materially changed tradepath. Specific missingcarry exit reasons/domain state/liquidation counters remain UNKNOWN.

Reject this v1 economically: terminal205.42245876, ROI−97.9457754124%, minuteDD99.8486498555%. This run cannot reject every pairing concept, or prove any particular parameter optimum. No inference of signedfunding or realized perasset PnL is made.

At most three repair prechecks, before considering another engine: (1) verify changedBTCcalendar andSOLexitownership at Sep17 andApr2 from persisted exactintent/domain evidence; (2) require an explicit ordinaryalpha SOL risk budget afterBTC closes, stress actual7000SOL againstnativeequity and comparecontrol4000 onidenticalmarks; (3) persist economicresult andcarry/domain/liquidation audits before metadata validation, so any later candidate is attributable. All outcomes and ROI of modifications remain untested.

## Native trace verification and comparable times
The synchronized streaming pass consumed exactly 3,153,600 rows of each trace with matching timestamps and phases; reproduced minute DD99.84864985552820898675873133% candidate and66.31878024969152066570091116% control. Candidate peak135726.63539696 is2025-03-25 20:12Z, cash126398.11609696, BTC7.973long, nativeU9328.5193. FirstDD50 is2024-10-11 19:07Z with onlyBTC2.356short: E11219.94597794,cash18014.06097794. FirstDD80/90 are2025-01-13 14:34/14:36Z with onlySOL2596.9long,basis186.64994069852517: E14834.79305178/6239.05405178,cash51009.45605178. Repeated tail exposure predates terminalfailure.
The first changed window improved relative to control: at2024-09-17 16:08Z BEFOREclosefills are reflected bynextminute, candidateE13556.09116573 versuscontrol7076.87453045. Candidatecash13341.24936573,nativeU214.8418. Firstcarry is not evidence pairing immediatelyfailed. No realized pairPnL inferred.
Minute rows labeled by close_available_ns of priorOHLC; boundary orderreport ts_last can appear innextminute trace. Exactphase preserved inJSON/CSV.
| UTC | Candidate equity | Control equity | Candidate SOL | Control SOL |
|---|---:|---:|---:|---:|
| 2024-09-17T00:01:00+00:00 | 10582.75942514 | 10525.25478497 | 222.7 | 0 |
| 2024-09-17T16:08:00+00:00 | 13556.09116573 | 7076.87453045 | 222.7 | 0 |
| 2025-04-02T00:00:00+00:00 | 91937.64723671 | 764801.65309281 | 2000.0 | 6000.0 |
| 2025-04-06T18:04:00+00:00 | 36942.09795879 | 816616.53147213 | 7000.0 | 4000.0 |
| 2025-04-06T18:07:00+00:00 | 37362.09795879 | 818323.02296063 | 7000.0 | 4000.0 |
| 2025-04-06T20:37:00+00:00 | 542.09795879 | 797283.02296063 | 7000.0 | 4000.0 |
| 2025-04-06T20:38:00+00:00 | 205.42245876 | 801563.02296063 | 0 | 4000.0 |

At2025-04-06 18:07Z both are SOL-only on110.88 mark. Candidate SOLnotional776160 /equity37362.09795879 =20.77399x; control443520 /818323.02296063 =0.54199x. Candidate153 prequote minute samples SOL-only from18:05 to20:37; nativepostquote showsBTCflat18:04. This direct exposure/buffer mismatch is stronger evidence than grossfee totals; not a simulatedstress outcome.
