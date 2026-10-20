# Failed R2: actual observed churn diagnostic

**Actual native order/fill counts are UNKNOWN:** the307-byte run log and journal contain no order/fill records; final native exports were lost. The30,000 figure was a synthetic fixture and is not used.

One corrected bounded prefix decode counted392240 stored samples at130747 observation/source timestamps, including130746 post-SOL observations. The first pass had a serializer error; its100000-row interim output is preserved, and root explicitly authorized one corrected read-only repeat. No economic engine or control scan occurred.

| Observed quantity transition | BTC | SOL |
|---|---:|---:|
| Total |50|22700|
| Open |13|14|
| Add |13|11444|
| Reduce |11|11228|
| Close |13|14|

These are native-cache **inventory observations, not fills, orders or standalone round trips**. Observed signed-inventory spells:13 BTC and14 SOL, closed within this prefix.

SOL changes show:

- 22613/22700 (99.6167%) have absolute delta<=1SOL;17446 (76.8546%) are exactly one0.1SOL native step.
- 7835 adjacent opposite-delta changes occur within60s while the SOL position keeps its side and no BTC quantity change is observed.
- 13019 successive SOL changes are separated by1–60s; two share an observation timestamp.
- The two shared-timestamp opposite-delta cases may reflect hook/settlement updates; **they do not prove same-quote double executions**.
- 31570 intervals change stored equity with qty/basis/cash unchanged: compatible with repricing/deferred valuation, not fills or realized-PnL attribution.71 cash-only changes cannot be assigned to fees/funding/settlement.

**Most probable mechanism:** repeated small target corrections at a tight risk boundary under changing marks/lot rounding. This matches the source owner's review of boundary-target selection and one-lot reconciliation. Actual small-lot ping-pong is strongly supported; exact decision reasons, ownership and fee/PnL dominance remain unproven.

The archival control621 native fill-report rows covers24months. That differs in both metric and duration; no22700/621 churn ratio is claimed. Partial trace finality remains uncertified, and full candidate economics remain UNKNOWN.

Files: churn-diagnostic-statistics.json, churn-diagnostic-interim-first-pass.json, churn-diagnostic-prefix.py and churn-diagnostic-manifest.json. Failed input SHA25651da0e4405e7031960e0668395a78a4dfe902c37bfca8f843bfdd29728b1f052 remains unchanged.
