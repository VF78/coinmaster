# VPS cleanup inventory — 2026-10-22

Status: completed after coordinator GO for exactly this 20-path allowlist. See `vps-cleanup-result.md` and `.json`; no service or process action taken.

Proposed: 20 exact paths; 1,846,198,272 allocated bytes. Free disk: 2,011,017,216 bytes.

## Exact proposed deletion allowlist

| Resolved path | Logical bytes | Allocated bytes |
| --- | ---: | ---: |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-cnn-validation-20261020T180922Z/result/cnn-validation/seed-42.pt` | 3606494 | 3608576 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-cnn-validation-20261020T180922Z/result/cnn-validation/seed-7.pt` | 3605825 | 3608576 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/minirocket-memory-r2/model.pkl` | 453398 | 454656 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/minirocket-resource-r1/train-transform.npy` | 138630304 | 138637312 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/minirocket/train-transform.npy` | 138630304 | 138637312 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/prior/model.pkl` | 177 | 4096 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/rdst/model.pkl` | 2169138 | 2170880 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/simple/model.pkl` | 4104 | 8192 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result/stumpy/model.pkl` | 2146055 | 2146304 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-fit-control-20261021T111115Z/result/train/calibrator.pkl` | 332 | 4096 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-fit-control-20261021T111115Z/result/train/final-seed7/model.pkl` | 9574 | 12288 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-fit-minirocket-20261021T111927Z/result/train/calibrator.pkl` | 332 | 4096 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-fit-minirocket-20261021T111927Z/result/train/final-seed7/model.pkl` | 149664 | 151552 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-fit-stumpy-20261021T111145Z/result/train/calibrator.pkl` | 332 | 4096 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-fit-stumpy-20261021T111145Z/result/train/final-seed7/model.pkl` | 4174780 | 4177920 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-profile-rdst-20261021T100234Z/result/profile/cache/transformed.npy` | 1185920 | 8192 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-profile-rdst-20261021T104128Z/result/profile/cache/transformed.npy` | 1185920 | 1187840 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-profile-rdst-20261021T110201Z/result/profile/cache/head.pkl` | 53578 | 57344 |
| `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-profile-rdst-20261021T110201Z/result/profile/cache/transformer.pkl` | 171406 | 172032 |
| `/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/research-envs/fast-rnd-20261020` | 1551142912 | 1551142912 |

## Preserve

Native runtime `.venv` is the archived S0 interpreter (S0 preflight and launch receipt). The dedicated fast-rnd environment has NumPy/aeon/STUMPY/CPUtorch and no Nautilus package. No dependency surgery or environment installation is proposed. Its deletion is conditional on coordinator confirmation that current S0 optimization uses the native environment.

All CoinMaster source/config/seals/source locks/reports are retained, including tiny Kronos/TS2Vec upstream provenance. All real price/funding datasets, D1 numerical features and historical-path infrastructure remain. Archived forecasts, probabilities, labels, metrics, CSV, money/trade/backtest evidence, S0 results, journals and state databases remain. Hermes/shared caches, secrets, installed releases and all /srv /opt /etc content remain.

No candidate has a running process dependency in `/proc` cwd/exe/root/maps/cmdline/fd/mountinfo checks. No running container mount overlaps a candidate. Full protected service and container snapshots are in the JSON inventory. Only exact regular files plus one resolved environment directory are proposed; symlink ancestors will be rejected and recursive environment deletion will not follow symlinks.
