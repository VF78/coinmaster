#!/bin/sh
set -eu
cd /Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 VECLIB_MAXIMUM_THREADS=4
export PYTHONPATH=runtime
exec /Users/vf/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m coinmaster.research.btc_fullwave_stage_a catalogue \
 --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared \
 --old reports/btc-pattern-pilot-m2-20261021/event-e1-20261022/catalogue.json \
 --results reports/btc-pattern-pilot-m2-20261021/event-e1-20261022/RESULTS.json \
 --protocol reports/btc-pattern-pilot-m2-20261021/fullwave-stage-a-20261022/PROTOCOL.md \
 --output reports/btc-pattern-pilot-m2-20261021/fullwave-stage-a-20261022/run \
 --go reports/btc-pattern-pilot-m2-20261021/fullwave-stage-a-20261022/coordinator-go.json
