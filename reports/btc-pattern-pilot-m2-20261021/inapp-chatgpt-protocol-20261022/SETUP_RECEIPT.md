# In-app setup receipt

Status: READY_REQUIRES_ROOT_LAUNCH_GO. No forecaster invoked by preparation; no current query truth joined or scored. Original data/model/source files unchanged. No training, API, data fetch, CHECK, VPS or deployment.

Freeze: `frozen/freeze.json`, SHA256 `7ea0cd8c624ef72cab364dbc337f4d7d4895fa0c2c33baadce67cd82ee435755`. New source SHA256 `bbbdded5e9bdd04c2434769e87d7f6963ee75f6717ba475c4919a758a9703248`. Original prepared manifest verified against approved hash. Source/artifact hashes checked before preparation.

Selection: full 699-day DEVELOPMENT universe; original 8,496 OOF IDs verified; 24 evaluation origins, eight per fold, equal calendar centres, entire future within fold and nonoverlapping selected future intervals. Prefix dependency uses earliest of stored support and 336h plus closed-4h age. Eligible filtering precedes fitting means/std and context cosine retrieval; original-ID tie break and greedy72h spacing. Priors use whole eligible prefixes, unsmoothed D, linear empirical Q and unconditional adverse-touch frequencies. No arbitrary crop.

Debug: July1 ID720 has312 eligible origins; mandated greedy selection yields IDs308,56,188, hence LOW_SUPPORT. Root directed protocol-defined skip/no replacement. Five supported debug origins yield10responses; evaluation48; plan58 <=60. Original firstfour debug slots remain July/Aug/Sep/Oct, with skippedJuly; optional one format revision occurs only after those slots; finalNov/Dec confirm.

QA PASS: all29 supported pairs have identical contexts, four example IDs/order and outcome fields; C contains no query/exemplar windows. All58 packet hashes checked. P charts1600x1000 rendered solely from rounded packet numbers, first image visually inspected. Maximum P JSON43676bytes (<250KB; slightly above preferred40KB). Standalone opaque packet directories contain only packet.json and P chart.png before response storage. Date/absoluteprice/entrygap/prior/result/repository paths absent from packet payloads. Mature earlier selected IDs may legitimately belong to later query fit prefixes; current query future is never an input.

Focused verification: three focused tests PASS through direct standard-library test runner (pytest absent); validation/order/finiteness, ties and NO_TRADE, exact inclusive adverse touch and stop-minute lower/upper convention, pinball/Brier, paired fold-stratified calendar-block bootstrap and constant-difference inconclusive rule. Bundled Python with NumPy+Pillow used; no dependency installation.

Collector: each fresh forecaster reads only its exact packet and P chart paths and writes its raw JSON exactly once to that directory's `response.json`. Final compact receipt may contain path/hash. No repair/retry. Structural validation reads no query paths/truth. `seal` checks all required responses, packet/source hashes, preserves invalid responses as failures, and writes an immutable receipt; evaluation seal requires48responses/24pairs. Post-seal score verifies receipt/raw-answer hashes before query paths, scores all issued IDs with frozen-prior fallback, reports covered-only, all six Q/SL rows, ambiguity upper sensitivity, calibration, atom-aware quantile coverage, TP attained bounds/positive denominators, derived display NO_TRADE and full-horizon adverse touch; no economics.

Run from worktree root with `PYTHONPATH=runtime` and `/Users/vf/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m coinmaster.research.btc_pattern_inapp`:

- `validate-structure --freeze reports/btc-pattern-pilot-m2-20261021/inapp-chatgpt-protocol-20261022/frozen/freeze.json --phase debug` (10 expected).
- `seal --freeze reports/btc-pattern-pilot-m2-20261021/inapp-chatgpt-protocol-20261022/frozen/freeze.json --phase debug`.
- Same commands with `--phase evaluation` (48 expected), after all evaluation answers.
- `score-after-seal --freeze reports/btc-pattern-pilot-m2-20261021/inapp-chatgpt-protocol-20261022/frozen/freeze.json` only after evaluation seal and root release.

No submit/repair step is needed: the original model-written response.json is the submission. Missing outputs block sealing until root records a failed-attempt response (ABSTAIN) without another model call. Source/schema/prompt revision after debug requires explicit re-freeze before evaluation; no evaluation launch with changed pins. Original secondary numeric/context/CNN controls are not joined by this module; their variable-SL predictions are never invented.
