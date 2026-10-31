# CM2 foreground static block dispatcher

`coinmaster.research.cm2_batch` adds no engine, policy, money model, daemon or network coordinator. It imports existing `cm2_runner` admission/worker functions. Root must reserve the complete block in its authoritative global budget BEFORE issuing this manifest; a reference alone is not proof that root performed that accounting. Each host receives the SAME immutable manifest, distinct host subledger and a strict budget containing ONLY its local block quota. Host-independent unique IDs and policy hashes plus exact host request digests are frozen before the first case. This harness cannot independently inspect a remote ledger; the root reservation and disjoint allocation are the global authority.

Initial broad: root reserves32, Mac30/VPS2. Second broad requires a new root reservation/manifest and explicit `second_broad_block_GO`; no automatic continuation. Stage caps remain116 aggregate and4/4/64/32/12. This dispatcher caps each broad block at32. Anchor failure remains spent; current remaining anchor allocation is at most2. Nothing in this tool grants a physical attempt.

Manifest schema (illustration ONLY, not an executable GO):

```json
{
  "schema":"cm2-static-block-v1", "root_GO":true,
  "block_id":"CM2_BROAD_INITIAL_20261031",
  "global_reservation_ref":"ROOT_ALLOCATION.json#reservation-1",
  "stage":"broad", "broad_block":"initial", "reserved_attempts":32,
  "hosts":{
    "mac":{
      "quota":30,"max_workers":10,"min_available_memory_bytes":2147483648,
      "budget_path":"/ABS/mac/block-budget.json", "attempt_ledger":"/ABS/mac/block-trials.jsonl",
      "shared_lock_path":"/ABS/runtime/var/research-jobs/mac-native-research.lock",
      "api_probe_root":"/ABS/mac/block-probes",
      "cases":[{"run_id":"CM2_B001","policy_sha256":"CANONICAL_POLICY_SHA256",
        "request_path":"/ABS/mac/requests/B001.json","request_sha256":"EXACT_REQUEST_BYTES_SHA256"}]
    },
    "vps":{
      "quota":2,"max_workers":2,"min_available_memory_bytes":1073741824,
      "budget_path":"/ABS/vps/block-budget.json", "attempt_ledger":"/ABS/vps/block-trials.jsonl",
      "shared_lock_path":"/ABS/vps-native-research.lock","api_probe_root":"/ABS/vps/block-probes",
      "cases":[{"run_id":"CM2_B031","policy_sha256":"OTHER_CANONICAL_POLICY_SHA256",
        "request_path":"/ABS/vps/requests/B031.json","request_sha256":"EXACT_REQUEST_BYTES_SHA256"}]
    }
  }
}
```

The example abbreviates cases; actual lengths must exactly equal quotas30/2 and sum32. Host paths are explicit inside the shared manifest. Policy digest is SHA256 of `json.dumps(policy,sort_keys=True,separators=(",",":"))` UTF8. Request digest hashes exact bytes. No duplicate policy or case ID anywhere in a block; root additionally deduplicates against previous blocks. Mac worker ceiling10, VPS2; finite fresh available-memory floor is mandatory before EACH new launch. Linux uses MemAvailable; Mac uses free+inactive+speculative pages. Memory HOLD stops admission when no child can free capacity; no running worker is killed. Root selects thresholds from measured RSS and reserves finite headroom; example thresholds are not measurement claims.

Each host budget is created AFTER hashing the manifest (request files need not contain a budget content hash, which would create a circular freeze). Example Mac budget:

```json
{"scope_version":"CM2_BROAD_INITIAL_20261031","root_allocation_sha256":"MANIFEST_SHA256",
 "total_physical_cap":30,"stages":{"broad":{"cap":30,"initial_block":30}}}
```

Receipt contains existing `R2_RELEASED`, matching `stage`, all existing five true admission flags and `root_allocation_sha256`. Existing local/qualification conditional flags still apply. A source/config/data/binary freeze must include this final module and the exact host Native1.231 binary. Public profile and qualified coverage helper must be explicitly authorized, pinned and available on VPS before its preflight. Financial Mac outputs are not inputs. All account/cache/journal/output paths are fresh per case; market data/source are read-only.

CLI (check performs constructor-free request/config/file checks only):

```sh
PYTHONPATH=/ABS/frozen-source/runtime /ABS/pinned-python -B -s -m coinmaster.research.cm2_batch \
  --manifest /ABS/root-allocation.json --manifest-sha256 EXACT_SHA256 --host mac \
  --resource-receipt /ABS/root-stage-receipt.json
```

Only explicit `--run` performs existing zero-engine public API boundary probes, then acquires host resource lease once and launches children. This is never authorized by a successful check. A busy host lease consumes0 attempts; do not run competing public `cm2_runner --run` workers. Dispatcher passes its same open FD to every existing `--worker --lease-fd --request-sha256` child. No LOCK_UN appears; parent failure closes only its descriptor and surviving children retain admission. Root must wait for the current nominal R1 to finish naturally before batch lease acquisition.

Every claim is registered/fsynced by existing `register_attempt` before worker preparation/Popen. Spawn failures count. STARTED/unknown cases are never retried. A nonempty block ledger is refused on a new dispatcher invocation; root must reconcile/reserve a new manifest for any continuation, never reassign an unknown slot. Existing STARTED rows retain block `scope_version`; output ATTEMPT_STARTED and terminal rows add manifest/request digests. Root imports local rows append-only with host, block, original-ledger SHA and row provenance; never rewrites old attempts. Unused reservations remain reserved/closed until root explicitly reconciles them, with no automatic borrowing.

Worker exits are collected by exact PID using wait4, with per-child peak RSS. Two failures sharing spawn exception type or worker exit code conservatively stop NEW claims; existing children finish. Exit-code grouping can stop on distinct causes and is intentionally conservative. Economic infeasibility in a completed valid report is not a software error; no per-trial LLM, median pruning or automatic restart. Dispatcher exit0 requires all claimed workers exit0 and no admission stop; result reports failures and reservation non-reusability. Interruptions preserve unknown ledger entries, do not kill workers and may leave them finishing without a dispatcher; root reconciles native artifacts/PIDs before any future allocation.

Focused proof command (standard-Python child processes only, zero native constructors):

```sh
PYTHONPATH=runtime PYTHONDONTWRITEBYTECODE=1 /ABS/pinned-python -B -m unittest discover \
  -s runtime/tests -p test_cm2_batch.py -v
```
