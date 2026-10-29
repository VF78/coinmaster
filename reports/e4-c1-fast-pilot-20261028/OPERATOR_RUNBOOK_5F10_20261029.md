# Prepared inactive installation and one proposed installed reference

Preparation only, source5f10ce870b18fd8181b57c23f0d9d36d3e867d67. Owner VERSION is required before /srv copy, Sandbox stop or ONE installed-reference comparison. Prior24/24native budget remains CLOSED; nothing was run under a new budget. START/orders remain separate.

Prepared source/environment: /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/release
Future new destination: /srv/coinmaster/hl-live/releases/5f10ce870b18fd8181b57c23f0d9d36d3e867d67-e4-c1-dp55-inactive-native1.231.0
No overwrite, current-pointer selection, service operation, account binding, approval or credential loading occurs in preparation.

The 261-file account-free payload matches selected-loader11pins; archive3747840bytes; identity943575d1d32c7f5ee1cbef75bde34cec1ecea8aa1610064d330cdf2dacd6a339; payloadb86a85a46685afe0b39103aee200d45e0faf08c83250d7b1fbc7cd3a719b1513.
wave_overlay startup SHA f6bb3e26f384a96b064ff44656d6901f67f9f7f79b7e2da8c7a388ff20073328; separate live_recovery SHA3cf08a3288d553244e7cb1edf6eb8d067772d9062f4bdfb36df2dd1d3a727fc2.
Old packet5f10/stale DRAFTs remain immutable. This runbook supplies current instructions, not a new product installer.

## Frozen environment proof

Old immutable livevenv was rejected:111native.so hashes differ despite same1.231.0 label.
Exact accepted A23 primaryruntime/.venv was independently copied into private/tmp with copy2, then preserved by same-filesystem rename in this NEW ignored durable preparation directory; regular files have distinct inodes from development source; no development-venv symlink/hardlinks. Copied files/directories are read-only.
Full distribution/native trees match accepted A23; native SHA5cafce5799849398276175066a61ac1ad6151a9c593daa5ae26a6f523b696644.
Base Python binary SHAe50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f and stdlib SHA c06738c584d55c9843b575c618bb170ee25979d729d0e4fe0d8ec42443b81716 match. System Python/stdlib remain external dependencies and must retain these identities before qualification.
Relocated bin/python sys.prefix points to snapshot/.venv; actual selected loader passed; every loaded coinmaster module plus live_recovery/native_baseline spec resolves in NEWpayload.
Accepted editable.pth still contains primaryrepo/runtime as exact preserved bytes; explicit cwd+PYTHONPATH takes precedence and actual origins were checked. Do not use console scripts retaining old shebangs.
Proof: /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/frozen-environment-proof.json.
Full copy manifest: /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/frozen-copy-tree.json; SHAff61f21bec4d66d1036edebede202452977865357d5c27a9121e3830b378f529. It covers7615regularfiles and4symlinks, separately from the261-file payload identity.

## Standard future copy/hash/origin recipe — NOT RUN

After VERSION only. Stop on any failure; preserve partial destination and never rerun over it.
    set -eu
    SRC='/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/release'
    DEST='/srv/coinmaster/hl-live/releases/5f10ce870b18fd8181b57c23f0d9d36d3e867d67-e4-c1-dp55-inactive-native1.231.0'
    test -d "$SRC" && test ! -L "$SRC"
    test ! -e "$DEST" && test ! -L "$DEST"
    mkdir -m 0700 "$DEST"
    cp -a "$SRC/." "$DEST/"
    chown -hR root:coinmaster-hl-live "$DEST"
    chmod -R g+rX "$DEST"
    python3 - "$DEST" <<'VERIFY'
    from pathlib import Path
    import json,hashlib,os,sys
    root=Path(sys.argv[1]);expected=json.loads(Path("/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/frozen-copy-tree.json").read_text())
    files={};links={}
    for f in root.rglob("*"):
     name=f.relative_to(root).as_posix()
     if f.is_symlink():links[name]=os.readlink(f)
     elif f.is_file():files[name]=hashlib.sha256(f.read_bytes()).hexdigest()
    dirs=sorted(f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_dir() and not f.is_symlink())
    assert files==expected["files"] and links==expected["symlinks"] and dirs==expected["directories"]
    print("EXACT_FROZEN_TREE_COPY_PASS")
    VERIFY
    cd "$DEST"
    env PYTHONPATH="$DEST" PYTHONDONTWRITEBYTECODE=1 "$DEST/.venv/bin/python" -B - <<'ORIGINS'
    from pathlib import Path
    import sys,importlib.util
    from importlib.metadata import version
    from coinmaster.ops.stage_g_config import load_candidate
    from coinmaster.ops.hl_live_profile import load_live_profile
    root=Path.cwd()
    assert Path(sys.prefix)==root/".venv" and version("nautilus_trader")=="1.231.0"
    candidate=load_candidate(root/"configs/hl-live-v3-dp50.candidate.json")
    assert load_live_profile(root,candidate.candidate)["profile_sha256"]=="719609d2d200a927b66d086469092183d89a148f262560708b83106500bc6ddb"
    for name,module in sys.modules.copy().items():
     if (name=="coinmaster" or name.startswith("coinmaster.")) and getattr(module,"__file__",None):assert Path(module.__file__).resolve().is_relative_to(root)
    for name in ("coinmaster.strategy.live_recovery","coinmaster.research.native_baseline"):assert Path(importlib.util.find_spec(name).origin).is_relative_to(root)
    print("INSTALLED_PREFIX_SELECTED_LOADER_ORIGIN_PASS_NO_ENGINE")
    ORIGINS
This standard recipe was dry-proven in/tmp and its same-byte durable preparation tree; /srv ownership/readability and installed runtime qualification remain pending. Preserve old current pointer6c208fde... and old release. No approval/fingerprint/private file is synthesized. No legacy staging installer is used.

## Required historical inputs are now prepared

/root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-inputs/data
Coordinator verified all10files,83478409bytes. Transfer manifest /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-inputs/transfer-manifest.json SHA b04ee354c51994622c9127afdea8cdb3d2bf7208ff4260d300bdd09d80f95245. Four execution/mark files match historical7abmanifest; four daily/funding files match exact Mac input-transfer SHA; control report unchanged. No dataset recrawl/refetch/substitution/control regeneration.
Original execution JSON: /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/original-reference-execution.json.
Only Python/PYTHONPATH/cwd/data-root/control-report/artifact-dir change; ALL original native_baseline non-path flags and values remain exactly unchanged.
Machine-readable proposal: /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/installed-reference-proposal.json; SHA 07ec67951d62b645dbb7976be12c0dd54d1c4a9f182e4c1751650c5f0de5db6a.

ONE future installed-reference comparison after VERSION explicitly authorizes one new comparison, after exact copied-tree/environment/data checks:
    cd /srv/coinmaster/hl-live/releases/5f10ce870b18fd8181b57c23f0d9d36d3e867d67-e4-c1-dp55-inactive-native1.231.0 && timeout --signal=TERM --kill-after=30s 1800s env PYTHONPATH=/srv/coinmaster/hl-live/releases/5f10ce870b18fd8181b57c23f0d9d36d3e867d67-e4-c1-dp55-inactive-native1.231.0 PYTHONDONTWRITEBYTECODE=1 /srv/coinmaster/hl-live/releases/5f10ce870b18fd8181b57c23f0d9d36d3e867d67-e4-c1-dp55-inactive-native1.231.0/.venv/bin/python -m coinmaster.research.native_baseline --data-root /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-inputs/data --research-v0-execution-repairs --research-v0-deferred-selective-zero-tp --research-v0-selective-lifecycle-repairs --observe-minute-risk --research-btc-direction-sizing --research-btc-split50 --research-btc-split-discount 0.0025 --research-btc-split-planref-v1 --research-btc-split-tp-ioc --control-report /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-inputs/data/runs/tp-fee-floor-113/v0/v0.json --artifact-dir /tmp/cm-e4-c1-installed-reference-5f10-once/result --research-regime-reentry-band 0.5 --research-wait-4h --research-residual-recovery --research-c1-btc-cut-divisor 4 --research-c1-restore-dd 0.40 --research-c1-first-fresh-h4 --research-c1-btc-postcut-d1
Do not precreate/reuse its result directory for another attempt. Capture actual child exit/result/input/config/native/resource evidence and compare complete native outcome/accounting with original reference. Expected original contract: configa2c7d88b5aff67399c0db849585bc5ad3625ce4e82068b3e29254d355c119253; data7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc; [2024-09-01,2026-09-01); seed10000USDT/reserve0; TOTAL5499360.14984003; nativeDDabout51.2686%; native1.231.0. No seed/period flags were added. These are reference targets, not a new measured result. Prior original size184MiB/time650s informs capacity only, not an ETA or new run permission.
No optimizer/new control/reserve/economic-rule experiment follows this single comparison.

## Separate START

Installed-copy/reference approval is not START or order approval. Worker pre-start refresh/preflight and worker.main are START paths, not inactive checks.
Currency GUI/APIc5cfcf97f54d2a2a80e89df81ff44feef082b393 is separate and required before eventual START. Current exact private account/approval/recovery gates, DP55/retained0.45/H, ownership and cashflow quarantine remain required; no historical binding/Sandbox approval/reset/adoption shortcut.
Preparation ran0engines/HTTP/account/credential/service/installed-path actions. SourceHEAD5f10, oldlivevenv and immutable packets remain unchanged. Installed qualification is the ONE proposed comparison after VERSION, not a claim already achieved.

Durable result preservation: same-filesystem os.rename from the prior private/tmp release; no bytes changed. Full7615-file/4link/directory manifest matched after relocation; actual relocated bin/python prefix, selected loader and all coinmaster source origins were rechecked at durable root, no engine. Durable receipt: /root/.openclaw/workspace/coinmaster/coinmaster/runtime/var/release-preparation-20261029-5f10-ready/durable-ready-receipt.json

One comparison attempt only, wall-time ceiling1800s with30s TERM-to-KILL grace; no automatic retry/resume/reserve. Timeout is a failed/uncertain attempt requiring evidence preservation, not permission to start another.
