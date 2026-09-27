# Pinned Nautilus 1.231 Hyperliquid connection epoch

`nautilus-1.231.0-hl-connection-epoch.patch` changes only the Hyperliquid Rust client and its PyO3 binding. The shared transport already advances its writer `connection_epoch` before reconnect returns to `Active`; the patch exposes that atomic value to Python. CoinMaster captures it when configuring the live report boundary and permanently revokes recovery if it changes. The stock wheel lacks the getter and fails configuration closed.

Build in an isolated Linux CPython 3.12 builder, never in the running trader environment. Use the official sdist pinned by `runtime/uv.lock` (SHA-256 `142dde40e77339745aa5fe6bcbb3de5624cee087f526879da00f127df077530f`) and its checked-in `Cargo.lock`. The sdist declares Rust 1.97.1 as its minimum; record the exact builder image, `rustc +stable --version`, `cargo +stable --version`, Python, compiler, and resulting wheel hash. Its official `build.py` accepts the `stable` or `nightly` rustup alias.

```sh
curl -fL -o nautilus_trader-1.231.0.tar.gz https://files.pythonhosted.org/packages/22/b7/a899df9daa2d84b9bb546a982b951f9336c814014c8545466d3eb138993b/nautilus_trader-1.231.0.tar.gz
printf %s %sn 142dde40e77339745aa5fe6bcbb3de5624cee087f526879da00f127df077530f nautilus_trader-1.231.0.tar.gz | sha256sum -c -
tar -xzf nautilus_trader-1.231.0.tar.gz
cd nautilus_trader-1.231.0
patch --dry-run -p1 < /absolute/path/to/coinmaster/runtime/patches/nautilus-1.231.0-hl-connection-epoch.patch
patch -p1 < /absolute/path/to/coinmaster/runtime/patches/nautilus-1.231.0-hl-connection-epoch.patch
RUSTUP_TOOLCHAIN=stable python3.12 -m build --wheel
sha256sum dist/*.whl
```

Do not substitute this wheel into `runtime/.venv`, edit `uv.lock`, or remove the live pre-build guard on source tests alone. A disposable wheel install must prove the getter increments through a forced loopback disconnect/reconnect, with current socket state green again, then run the CoinMaster hidden-gap regression and connected native lifecycle tests. Recheck all submit, cancel, modify, and forced-close gates. Wheel build and wheel-level tests remain unverified until an isolated builder with the pinned toolchain and sufficient disk is available.
