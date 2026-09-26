# Isolated native GUI/API release

Run from a clean, committed CoinMaster checkout. The wrapper archives the exact
HEAD runtime plus one locally built SPA, then stages a SHA-named release on the
VPS. It never updates the old shared checkout, `/opt/coinmaster`, the paper unit,
or the Stage-G trader unit. The only service it may stop/start is
`coinmaster-runtime.service`.

```sh
export GUI_DEPLOY_HOST=root@46.225.163.123
runtime/scripts/deploy_native_gui.sh plan
runtime/scripts/deploy_native_gui.sh stage
runtime/scripts/deploy_native_gui.sh activate-api
```

`plan` checks active services, the existing control DB for active research work,
the operator token, and the Linux runtime. `stage` embeds and verifies a generated
`runtime/release-manifest.json` before dependency installation. The `gui`
component records the source commit and dirty status, a deterministic tree
digest of the complete staged `runtime/` and `web/` payload, every
`runtime/coinmaster` source hash, and the pinned `uv.lock` and `pyproject.toml`
hashes. It attests to the GUI release contents without changing the separate
Stage-G approval identity. The default `trader` component retains exact
candidate/strategy/execution-policy seal validation for trader staging. Both
components verify the complete staged payload and source identity. `stage` then
verifies the archive digest, creates a distinct
`coinmaster-research` identity and root-only environment,
installs from the frozen runtime lockfile, and smoke-tests a temporary loopback
API using a copy of the control DB. Its receipt records the paper/trader PIDs.
`activate-api` backs up the previous runtime unit and release pointer, copies
the old control DB only on the first isolated activation, preserves that
research-owned DB on later releases, and starts only the runtime API from
the immutable release. It verifies authenticated API/SPA, the read-only HL control
contract, the absent paper command route, a fresh READY raw-worker strategy hash
matched by the staged and active API, and unchanged peer PIDs. It sends no
pause/resume commands during GUI activation.
It restores the prior
runtime unit automatically if activation checks fail, waiting up to 30 seconds
for `/api/v1/health` to answer its expected unauthenticated `401` before
smoke-testing. The service invokes Uvicorn through the venv Python module so
release renames do not leave an entrypoint shebang pointing at `.incoming`.
After an automatic rollback, retry the same staged release with its SHA:

```sh
GUI_DEPLOY_RELEASE_SHA=<staged-40-character-commit> runtime/scripts/deploy_native_gui.sh activate-api
```

To revert the active API release, from the same commit:

```sh
runtime/scripts/deploy_native_gui.sh rollback
```

Rollback checks for active research work before stopping only the runtime API,
restores the prior unit and release pointer, and verifies paper/trader PIDs. It
does not erase the staged release or research data. If any guard fails, stop and
inspect the service and receipts under `/var/lib/coinmaster-native-gui-deploy`;
do not manually modify the paper/trader services as part of this rollout.

The Stage-G status GET listener is a separate change. Until it is installed,
the GUI must report `UNAVAILABLE` and keep all controls disabled. No trader
restart, real credential, wallet, or order path is part of this procedure.

## `coinmaster24.com` login and HTTPS gate (#109)

The single browser account is `operator`. The existing random password and its
root-owned VPS scrypt verifier remain valid across this host change, so the
cutover does not rotate them. The Keychain item remains
`cm.f-ai.studio CoinMaster operator` until the provisioning helper is run; it
will reuse that secret under `coinmaster24.com CoinMaster operator` if future
provisioning is needed:

```sh
PYTHONPATH=runtime runtime/.venv/bin/python runtime/scripts/provision_gui_operator.py --host root@46.225.163.123
```

The password can be retrieved privately from the existing macOS Keychain item
(`operator` account). Do not paste it into
the repo, issue, service unit, screenshots, or shell history. The existing
Bearer token remains for loopback automation only; the browser uses a revocable
host-only session cookie. The root-only VPS file
`/etc/coinmaster-native-gui.env` contains the username, verifier and
automation token. Stage and activate the new commit-SHA API/SPA through the
wrapper above; its stage smoke still uses the loopback Bearer path and checks
that the unauthenticated shell opens the login page.

The checked-in `coinmaster24.com.http.nginx` handles only the ACME webroot and
redirect, and `coinmaster24.com.https.nginx` is the dedicated HTTPS proxy.
GoDaddy's `@` A record points to `46.225.163.123` (TTL 600); verify both
authoritative nameservers and public resolvers, plus the absence of an AAAA,
before issuance. Stage the HTTP host in `sites-available`, enable it, run
`nginx -t`, and test with `curl --resolve coinmaster24.com:80:127.0.0.1` on
the VPS. Issue only the apex certificate with Certbot webroot
`/var/www/letsencrypt`. Enable HTTPS only after the certificate exists, then
run `nginx -t` and verify exact Host routing and the certificate before
external browser acceptance. After the new host passes, replace the old
`cm.f-ai.studio` HTTP redirect with `cm.f-ai.studio.retired.nginx` and run
`nginx -t` before reloading. It returns 421 on HTTP and rejects the old TLS
handshake, keeping that Host away from both the GUI and the default app.

Acceptance requires a real desktop/390px browser login and logout, expired
session and CSRF denial, 401 on unauthenticated APIs, no browser API token, no
public Bearer bypass, no static path escape or API-to-SPA fallback, disabled HL
controls, absent paper command route, and unchanged paper/trader PIDs. If DNS,
certificate, Host routing, or these gates are missing, leave public HTTPS
disabled; the current default Host reaches the unrelated Paperclip app.
