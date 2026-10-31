# CM2 fixed seven-parameter design

`FROZEN64.json` is the authoritative immutable configuration file for BOTH hosts. Generated once on VPS from seed20261031 without reading any run results. No native engine, API probe, monetary output or data feed participates in generation. All64 configurations have `mode=joint`, `version=cm2-v1`; parameter dimensions, defaults, units, transformations and frozen constants are in `SPACE.json`.

Actual sampler is **SEEDED_UNIFORM_NOT_SOBOL**: SciPy/QMC is unavailable in the existing research environment; no dependency was installed. The explicitly authorized fallback uses stdlib `random.Random(20261031)` and64 successive rows of7 uniform coordinates. NumPy2.5.3 is installed but unused by this fallback. Python3.12.3, actual dependency versions, exact generator/source/schema hashes and original policy-validator source hash are embedded in the frozen file. `MANIFEST.json` pins the frozen JSON and generation inputs.

Each coordinate uses its documented linear/log transform. Trend hours use `floor(x+0.5)`; other six dimensions use Python `round(x,6)` before actual `Config` validation. Coordinates retain full binary64 JSON precision. Canonical policy hash uses sorted compact JSON UTF8. Any post-rounding duplicate stops generation without drawing replacements or expanding the design. All64 current hashes are distinct.

IDs `CM2_BROAD_V1_000`–`031` are the initial32 design block, pending separate root GO and allocation. IDs032–063 remain conditional HOLD. No design point is itself an attempt or dispatch authorization. Root global cap116 and stage caps remain unchanged. Future host path mapping must preserve these exact policy objects/hashes; root allocates disjoint Mac30/VPS2 only after stage gates. No per-host regeneration, selection based on previous results, automatic second block, per-trial LLM or off/categorical dimension.

The generator's `--freeze` uses exclusive create and refuses an existing file. Read-only `--verify` reproduces exact bytes under this pinned environment; it never rewrites frozen data. Later source integration may change the overall policy file hash while preserving the Config ABI; that requires source review and does not justify regenerating these64 points. Use the original frozen JSON on Mac even when platform math/library fingerprints differ.

Constructor-free verification:

```sh
PYTHONPATH=runtime PYTHONDONTWRITEBYTECODE=1 /ABS/research-python -B \
  reports/cm2-clean-hedge-20261031/search/generate.py --verify
PYTHONPATH=runtime PYTHONDONTWRITEBYTECODE=1 /ABS/research-python -B -m unittest discover \
  -s reports/cm2-clean-hedge-20261031/search -p test_frozen.py -v
```

Actual focused proof:3 tests PASS (0.030s), covering64 unique hashes/IDs, ranges/fixed policy/block counts, exact deterministic byte reproduction, transform endpoints and integer channel. Zero engines/probes/economic attempts. Files are private preparation; no push or deployment.
