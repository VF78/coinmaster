HISTORICAL PRE-READ CHECKPOINT. Superseded by stats-report.md and completed corrected pass.

# Carry existing pair: native census precheck

Analysis only. No market minute data read, no new portfolio/economic engine. Canonical HEAD91ec919d40ac71ff699885068599687ecfe5d9ba; old winning result and fills are sources.

There are48 actual BTC REGIME residual closes (25calibration,23later). Every residual BTC is below its actual weighted native entrybasis. Only6 have an existing opposite SOL net position (5calibration,1later). Creating hedge for other42 is a separate admission hypothesis. Every regime close is followed by the original opposite BTC entry exactly1minute later, so carrying any event explicitly delays or skips actual original entryrights.

Inventory snapshots use existing native domain fill_audit actions; no trade matching or realizedPnL generated. Exported fills provide side via instrument/timestamp/quantity join; audited price agrees within1e-7 export rounding. Adds update weightedentrybasis and allocatedentryfee/qty; actualreductions remove quantity at samebasis. Remaininginventory is snapshotted before actual REGIMEclose. OriginalfilledSOL REGIMEclose at sameinstant supplies its referenceprice for6pairs. Whole-pair instantaneous marks are price diagnostics, not profits or ROI.

Original6pairs have SOL/BTC currentnotional ratios2.5834,.0307,.0867,.2741,.1700,1.8132. Their inherited pair marks before allocatedentry/estimatedtakerexitfees are+3.5954%,-6.2448%,-4.2837%,-.0530%,-1.6546%,+14.6669% ofcurrentBTCnotional. Fees are.3729%,.1094%,.1053%,.1412%,.1113%,.3190%. Thus4pairs carry an inherited deficit even before fees; adding a fresh factor-neutralhedge does not retrospectively compensate originalBTCbasis. Native originalSOLrights and fixed betahedge also generally prescribe different inventory, so cannot both be preserved underoneNETTINGSOLposition.

Pending: daily causalCHOP flags at opposed timestamp. Entry-timeCHOP is intentionally not substituted. stats-daily-context.py prepared but not executed awaitingrootGO. Minute pass requires separateGO.

For original user3TP with proportional loser cuts, equalfractionf of BOTH remaininglegs at mark realizes exactlyf times inherited whole-pair gross (minusfractionallocatedentryfees and newexitfees), leaving(1-f) of both originalbasis/exposure. A profitable winningleg alone is insufficient. UnequalfractionsfB,fS alter hedge ratio: residual NS/NB scales by(1-fS)/(1-fB), so no frozen factor-neutralpromise survives unless resizingrights are explicitly spent. Three sequential reductions cannot be called profitable based on selectedslices while unmarked residual, nohits, incurredentryfees, funding and finalexit remain unaccounted.
