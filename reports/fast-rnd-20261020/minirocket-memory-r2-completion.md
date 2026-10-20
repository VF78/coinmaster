# MiniRocket corrected validation: completed

Same5959train/3432validation IDhashes as controls/STUMPY, full features/labels/recipe unchanged. Actual features1932 perTF, requested2000; total3x1932+20context=5816.

|Metric|BTC|SOL|Mean|
|---|---:|---:|---:|
|Validation logloss|7.125161290|7.300339389|7.212750340|

Versus prior, mean logloss difference +6.112164127 (+555.3553%). Negative difference means lower loss. No significance or trading profitability claim.

Fit72.437770s; inference4.584336s; elapsed77.510205s; process maxRSS807915520bytes. Observed cgroup peak805306368bytes (effective768MiB cap), swap0, final unit SUCCESS/noOOM. Exact fullmetrics/calibration/monthlyblocks in outputmetrics.json.

Output /var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/minirocket-memory-r2
Sourcecommit c1d0c69303635d2c433d29875c7271110b85017f; numericSHA c9312d7eab1642f330c20a5d3fc452c1d020653c86e4ad4ad36536a7412d6db7.

Chunked normalization/C-float64 diskmap is the only memory correction; fixed C1/lbfgs1000 and allsampleIDs remain. Earlier bothOOM attempts preserved. No auto repeat/RDST/CNN. Mandatory remaining recognizers gate selection; U outcomes not opened.
Pilot unchanged: True. JSON carries exact argv/pins/proofreferences.
