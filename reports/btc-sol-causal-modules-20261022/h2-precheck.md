# H2 residualCUSUM: rejected before native

**NO_NATIVE_GO.** The fixed rule never alarms during earlySOL1, so it cannot address the required early loss. Do not retune k/h/window to make this case pass. No native/engine/model/productsource/pilot changes.

All26originalSOLintervals evaluated; all24months represented in JSON.26causal currentdailybeta reconstructions;90days/2160strictlypreentryhourlylogreturns, fixed mean/populationstd andentrybeta; G0=0,k=.5,h=5, once50%remaindercut/cancelpendingadds/no restore. Hourinterval muststart at/afteractualentry.

## Decisive early case

EarlySOL1: actualentry2024-10-03T00:00UTC; beta0=1.179081410345596 from currentavailabledailyfeature, NOT oldBTCepisodebeta. Baseline2024-07-04T23:00 through2024-10-02T23:00UTC,2160returns; mu=0.00000494056326353826, population sigma=0.005380192525406814.47completepostentryhour observations beforeoriginalexit. **MaxG=2.8797172072 at09:00UTC, below5; noalarmbeforeDD50 oranytimewithinhold.** Simpleprice comparator also noalarm. OriginalSOL1 laternetexfunding+2330.72; a fixedthresholdmiss cannot be called successfulprotection.

## All-cycle comparison

| Method | Alarms /26 | Original winners affected | Positive endpoint references | Median per-cut-notional reference | Priorbook linear sigma increases |
|---|---:|---:|---:|---:|---:|
| Frozen residualCUSUM |4|2|1/4|-0.4250%|1/4|
| Causally calibrated simpleSOLprice stop |8|4|2/8|-4.2655%|3/8|

Comparator distance is frozen at eachentry using ONLY preceding90nonoverlap24hblocks. CUSUM resets perblock with entryfrozenmu/sigma/beta; the price-distance threshold is linearquantile q=1-p of those blocks maximumadverseSOLlogreturn, wherep ispastCUSUMblockalarmfraction. Thresholdties use>= and are disclosed; none producedfrequencydifference here.0pastCUSUMalarms meansinfiniteprice distance. Actualfuturealarmcounts4versus8 were NOT forced tomatch. Calibration is in-samplehistorical atentry, not anARL/falsealarm guarantee; 24hcalibrationhorizon differs fromactualholdingduration.

| SOL interval | AlarmUTC | Original outcome | Endpoint per-cut-notional reference | Main counterexample |
|---|---|---|---:|---|
|18|2025-07-22T03:00:00+00:00|winner|-14.6889%|Lateroriginalwinner; favorable rebound14.97%;3lateradds notsimulated|
|19|2025-08-12T17:00:00+00:00|loser|4.0632%|Onlypositive reference; ideal2500cut exceeds1000displayedquote;2lateradds|
|21|2025-08-23T05:00:00+00:00|loser|-0.2005%|Usefulhedge removed; priorlinearbook sigma6251->7132 (+14.08%)|
|26|2026-08-28T17:00:00+00:00|winner|-0.6494%|Originalwinner recovers; favorable post-alarm excursion2.24%|

Immediatecut fee references sum451.09USDT forCUSUM and1421.83 forpricestop. The staticendpoint reference sum+3216.77USDT (price-stop -96098.98) is **NOT alternativePnL/equity/TOTAL/DD or GO evidence**. It multiplies originalheldqty bydifference tooriginalwholecycleexitVWAP, withadditionalcutfee andproportionallyavoidedexitfee. Lateradds, cancellationofpendingadds, changingrights, actualpartialIOC andfuturecapital are not simulated. Three of fourCUSUMreferences are negative and theonlypositiveusesunverified2500execution; do not infer economicedge.

## Pairrisk and execution limits

Originalheldquantity is reconstructed from621confirmedfills on originalpath; actualcandidateholdings/pendingordereligibility remainUNKNOWN. A firststrictlylater1mclosequote isonlya price reference, not an actualfill. SOL19idealcut2500>known1000displayedquote means oneIOCcannotbeassumedcomplete. Allactions require nativeownership/cancel/ACK beforeanyfutureimplementation.

AtSOL21, originalBTCpositive signednotional2.412m andSOLshort409360: cutting1000SOL reducesusefulhedge. Prior90dhourlinearbookstd rises6251.41->7131.52; beta-factorabsexposurealsoincreases. This is a fixedpast-return shock diagnostic, not futureloss/DDmodel orverifiednativeportfolioPnL.

## Provenance and resources

Exactscientificsource75ffc9c69e9d79c4da4cd0614634a3eeba48d716; domainSHAa60a7fe8...159ab5b9. Localdailyand1mfileSHA match savedS0original13inputpins. Deterministicbatch_features_for uses270completed dailylogreturns/covariance/variance, currentcompletedbarincluded. All26firstSOLADDsubmit==fill withserializedMARKETtype1. Latestavailabledailyfeaturejoins followpinnedrunner marks->dailysignals->quotes ordering andstale-addacceptedpairguard; nativeaccepted-sessionreceipt/decision_index itselfwasnotexported, so noindependentcacheattestation isclaimed. betaorigin/times/values in h2-precheck.beta-pins.json.

GenuinepublicBybitlinear1hAPI:6pages,2232rows eachBTC/SOL fromJune1throughSep1. Indicatorwarmuponly; originalexecutionfilesunchanged. Sep1overlap24hourcloses perasset matchesoriginalminuteaggregate exactly, maxdelta0. Timestampcontiguity/responseSHA/provenance in h2-precheck.warmup.json; compactwarmupCSV retained. Fullrawresponses stayscratch, not repeated incontext.

Two boundedminute-columnpasses: firstfinishedread but numpyint64JSONserialization failed beforestatisticsoutput; correctedserialization andidenticalsecondpass recovered. Recoverywall2.14s, recordedpeakRSS212434944bytes (~202.59MiB), below180s/350MiB. This was not a secondstrategy/native/modelrun. InitialsandboxDNSfailureHTTP000 thenapprovednetworkfetch succeeded; sixsuccessfulHTTPpages.

[NIST CUSUM ARL](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/cusumarl.htm) calls k=.5/h=5 common choices; [NIST handbook](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm) presents rulesofthumb. These are not calibratedARL/falsealarm probabilities fordependentcryptoreturns.

Final: modulefailsrequired earlyaddressability andhasrecovery/hedgeriskcounterexamples. FullcandidateTOTAL/settledDD remainUNKNOWN. RootclosedH2withoutnative; nofurthermethod/threshold/windowchanges or audits.
