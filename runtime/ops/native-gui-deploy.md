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
the operator token, and the Linux runtime. `stage` verifies the archive digest,
creates a distinct `coinmaster-research` identity and root-only environment,
installs from the frozen runtime lockfile, and smoke-tests a temporary loopback
API using a copy of the control DB. Its receipt records the paper/trader PIDs.
`activate-api` backs up the previous runtime unit and release pointer, copies
the old control DB only on the first isolated activation, preserves that
research-owned DB on later releases, and starts only the runtime API from
the immutable release. It verifies authenticated API/SPA, disabled HL controls,
the absent paper command route, and unchanged peer PIDs. It restores the prior
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

## `cm.f-ai.studio` login and HTTPS gate (#109)

The single browser account is `operator`. Generate its random password in the
macOS Keychain and provision only the scrypt verifier in the root-owned VPS
environment before staging the new release:

```sh
PYTHONPATH=runtime runtime/.venv/bin/python runtime/scripts/provision_gui_operator.py --host root@46.225.163.123
```

The password can later be retrieved privately from the macOS Keychain item
`cm.f-ai.studio CoinMaster operator` (`operator` account). Do not paste it into
the repo, issue, service unit, screenshots, or shell history. The existing
Bearer token remains for loopback automation only; the browser uses a revocable
host-only session cookie. The root-only VPS file
`/etc/coinmaster-native-gui.env` contains the username, verifier and
automation token. Stage and activate the new commit-SHA API/SPA through the
wrapper above; its stage smoke still uses the loopback Bearer path and checks
that the unauthenticated shell opens the login page.

The checked-in `cm.f-ai.studio.http.nginx` handles only the ACME webroot and
redirect, and `cm.f-ai.studio.https.nginx` is the dedicated HTTPS proxy. Stage
them in `sites-available`; do not enable HTTPS until the certificate exists.
Before DNS changes, test the HTTP host with `curl --resolve
cm.f-ai.studio:80:127.0.0.1` on the VPS. Then the DNS owner adds exactly an A
record for `cm` to `46.225.163.123` with TTL 300. Add no AAAA until IPv6 is
verified. Certbot can then issue the exact-host certificate using webroot
`/var/www/letsencrypt`; only after that, enable HTTPS, run `nginx -t`, and
verify the exact Host with `curl --resolve` before testing external DNS/HTTPS.

Acceptance requires a real desktop/390px browser login and logout, expired
session and CSRF denial, 401 on unauthenticated APIs, no browser API token, no
public Bearer bypass, no static path escape or API-to-SPA fallback, disabled HL
controls, absent paper command route, and unchanged paper/trader PIDs. If DNS,
certificate, Host routing, or these gates are missing, leave public HTTPS
disabled; the current default Host reaches the unrelated Paperclip app.
