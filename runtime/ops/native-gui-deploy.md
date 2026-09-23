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
the control DB into research-owned state, and starts only the runtime API from
the immutable release. It verifies authenticated API/SPA, disabled HL controls,
the absent paper command route, and unchanged peer PIDs. It restores the prior
runtime unit automatically if activation checks fail, waiting up to 30 seconds
for the API to answer its expected unauthenticated `401` before smoke-testing.
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
