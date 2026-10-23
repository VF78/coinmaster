# Independent saved-native-output audit

Status: FINAL_SAVED_OUTPUT_AUDIT_8_CORE_PLUS_X_PASS. No new native/model runs.

|Recipe|TOTAL|observed settled DD%|Unavailable receipts|Fees|BTC/SOL fills|Funding rows|50/90|Validation|
|---|---:|---:|---:|---:|---|---:|---|---|
|C0|306.48185220|97.53441776076043948608313353|0|136.67759173|6/0|33|FAIL|SAVED_OUTPUT_VALIDATED|
|H4_4H_E34_G050|437.07391017|96.48383203633569295829914875|32|271.18878063|6/6|43|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|
|B|4622034.27336437|57.58541045962226379114466259|0|592090.31669918|322/162|1157|FAIL|SAVED_OUTPUT_VALIDATED|
|H4_4H_E13_G050|316.84518776|97.09949333268982022336289428|32|424.43565716|6/18|49|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|
|H4_4H_E89_G050|447.07510136|96.40337455021605260945614721|32|319.36161798|6/8|37|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|
|H4_4H_E34_G100|455.91575064|96.33225338042525607496275649|32|312.93340608|6/4|38|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|
|H4_4H_E13_G100|483.07378823|95.96060656929091799869884291|28|583.33084449|6/16|43|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|
|H4_4H_E89_G100|540.33349549|95.65313032343266042172502489|32|409.65761278|6/6|35|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|
|X_H4_4H_E89_G100_B05|540.33349549|95.65313032343266042172502489|32|409.65761278|6/6|35|FAIL|SAVED_OUTPUT_VALIDATED_WITH_SETTLED_GAPS|

Every completed result is read from native account/raw/fill/funding artifacts. Settled DD is independently recomputed once from each complete saved receipt stream with Decimal arithmetic and original10000 seed; no portfolio peak reset. Coverage, report/raw hashes, frozen source/config/policy/data metadata and13input pins are checked. Turnover=sum actual native fillqty×fillprice; fees=sum actual native commissions and independently native-fill CSV commissions.

Unavailable receipts make settled DD an observed lower bound; DD already>50 is unambiguous failure, while an apparent pass with gaps requires qualification. Every gap is counted per recipe. Funding timestamps matching gaps identify real native-account mutation, not mere signal metadata; no funding cash delta is invented. Signed funding stays UNKNOWN. Zero observed partialfills in a particular recipe do not prove large-target capacity; focused fixtures separately validate partial/cancel/late-fill behavior. Synthetic quote capacity remains1000SOL.

All8core and the single authorizedX completed and independently validated. No candidate passes50/90; R is ineligible. Physical runs10includingP0; reviewer new engine runs0. Root retains immutableS0 and owns aggregate report/budget/decisions.
Coverage H4_4H_E34_G050: 1051167 observed receipts +32 unavailable; 32 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.
H4E34G050 native first funding gap: cash9982.99821179→9981.05779616 with BTCqty0.791 unchanged. The32gaps are real account funding mutations; source observer refuses stale-source cash/inventory mixing, not a signal-only metadata event.
Coverage H4_4H_E13_G050: 1051167 observed receipts +32 unavailable; 32 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.
Coverage H4_4H_E89_G050: 1051167 observed receipts +32 unavailable; 32 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.
Coverage H4_4H_E34_G100: 1051167 observed receipts +32 unavailable; 32 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.
Coverage H4_4H_E13_G100: 1051171 observed receipts +28 unavailable; 28 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.
Coverage H4_4H_E89_G100: 1051167 observed receipts +32 unavailable; 32 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.
Coverage X_H4_4H_E89_G100_B05: 1051167 observed receipts +32 unavailable; 32 missing receipt times match native funding events; 0 match new fills. DD is an observed lower bound.


X versus selected H4E89/G1: **exact economic identity** confirmed for ordered fill audit (timestamps/quantities/prices/fees), native fills/orders CSV, native cash series, all risk curves/coverage, funding rows, entry sizing and parent lots after existing identity/path normalization. No new tolerance or exclusion. X has0B latch/allowevents before liquidation.

**Result: NO50/90WINNER.** B has highest candidate TOTAL4622034.27336437 but only76.0170224751% net-profit retention and57.5854104596% settledDD with complete receipt coverage. All H4/X observed DD values already exceed50%; their28–32missing funding-boundary receipts cannot rescue that failure. S0 remains immutable control; no native rerun/promotion follows from this audit.
