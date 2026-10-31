# Saved report aggregation (report only)

Run from this standalone directory with standard Python:

```sh
python3 -B -s merge_saved.py --manifest /absolute/merge-manifest.json --out /absolute/new-output-directory
python3 -B -s -m unittest discover -s . -p test_merge_saved.py -v
```

No product/native imports, engine, feed scan, PnL construction, or financial qualification occurs. Use only already-completed analyzer outputs. A supplied financial PASS is preserved, never created. Pareto scope is numeric and NOT_WINNER; MODEL_LIMITED and structural UNKNOWN do not exclude a financially qualified row. Both final-close DD objectives must be finite. Missing pins/parameters/objectives or duplicate case/run/raw-report identities yield null Pareto/group plus reasons. Equal objectives are co-Pareto; different exact groups never dominate each other.

Manifest schema (one entry per SUMMARY; COMPARISON may be shared across entries):

```json
{
  "schema_version": 1,
  "cases": [{
    "host": "host-label",
    "summary": {"path": "/absolute/case/SUMMARY.json", "sha256": "<64 lowercase hex>"},
    "comparison": {"path": "/absolute/COMPARISON.json", "sha256": "<64 lowercase hex>"},
    "request": {"path": "/absolute/request.json", "sha256": "<64 lowercase hex>"},
    "pins": {
      "source_commit": "<40 lowercase hex>",
      "python_sha256": "<actual executable hash>",
      "native_engine_sha256": "<actual engine extension hash>",
      "native_binary_hashes": {"objects": "<hash>", "risk": "<hash>", "instrument": "<hash>"},
      "source_hashes": {"<exact existing summary provenance source path>": "<hash>"},
      "data_hash": "<existing summary provenance data_hash>",
      "execution_policy_hash": "<existing summary provenance policy_hash>",
      "seed": "10000",
      "run_interval": {"start": "<exact UTC start>", "end_exclusive": "<exact UTC end>"},
      "fees": {"<qualified fee config key>": "<exact value>"},
      "currency": "USDC"
    },
    "runtime_seconds": null,
    "peak_rss_bytes": null
  }]
}
```

Host/source/binary/interval/fee/currency pins are explicit producer attestations in this hash-recorded manifest, not independently rediscovered executable facts. Populate them from the completed host's pinned execution receipt, not current interpreter discovery or assumed equivalence. Enumerate all economically relevant native extensions in native_binary_hashes consistently. Missing pins never inherit another host's values. Source/data/execution/seed values are checked against the hash-bound SUMMARY; request hash must equal summary provenance, optional request source_commit must agree. SUMMARY identity, TOTAL, financial status, report hash and analyzer group must equal its unique COMPARISON member. Both finite final-close DD values must numerically match member settled_DD_including_final_close/coherent_DD_including_final_close; missing/nonfinite/mismatch yields null group/Pareto plus reason. Raw identity uses original_report_sha256 when recovery provenance supplies it. Existing qualification provenance is retained; physical FAILED is not relabeled.

Group identity includes every supplied pin, the existing analyzer comparison group (retaining its source/interval/fee/currency restrictions), and existing measurement provenance. No cross-source, cross-binary, or semantic-equivalence override exists. Two equivalent hosts with different executable bytes remain separate groups. The helper verifies supplied file hashes and consistency; it cannot attest that an upstream PASS or a caller's host pin is true. No VALID_IMPLEMENTATION, robustness, persistence or winner conclusion is produced.

Outputs: COMPARISON.json, COMPARISON.csv, PARETO.csv in an exclusively new output directory. JSON includes input-file SHA hashes, canonical manifest digest, manifest-file hash, helper hash, preserved statuses/parameters/metrics/provenance, null unknown runtime/RSS, and per-row group/Pareto/reasons. CSV encodes nested values as JSON. Input files are never modified. SHA mismatch or inconsistent bound records fails before output creation.

Synthetic tests use small fabricated saved summaries only; no actual per-trial outcomes or Mac financial files are inputs.
