# D4 process-isolation installation contract

This is an installation-time template only. Do not apply it from the checkout
and do not edit `/opt/coinmaster` manually. Deployment must create a read-only
release at `/srv/coinmaster/runtime`, readable by both service identities, and
place the two unit files under the system service manager.

Create two non-login identities: `coinmaster-hl:coinmaster-hl` for the trader
and `coinmaster-research:coinmaster-research` for the runtime API/research
children. They must not share a group. The service manager creates
`/var/lib/coinmaster-hl-stageg-testnet` and `/var/lib/coinmaster-runtime` at
mode `0700`, owned by their respective identities. The trader state DB is only
`/var/lib/coinmaster-hl-stageg-testnet/hl-stageg-testnet.sqlite`.

The runtime StateDirectory owns `/var/lib/coinmaster-runtime/data` and this is
the required `COINMASTER_RESEARCH_DATA_ROOT`; it must be writable by
`coinmaster-research` before the API can create `runs/jobs/<id>`. Provision
historical public inputs separately at `/srv/coinmaster/research-inputs` and
expose only read-only bind mounts or symlinks beneath that data root (for
example `normalized` and `bybit-1m`). Do not copy, mount, or link a trader,
paper, or control SQLite DB into this directory.

Install `/etc/coinmaster-hl-stageg-testnet.env` as `root:root`, mode `0600`.
It contains only the non-secret sandbox/public-data guard values; it must not
contain a Hyperliquid private key or account address.
Install `/etc/coinmaster-runtime.env` as `root:root`, mode `0600`; it may hold
runtime relay tokens but must never contain Hyperliquid or Bybit credentials.
Install the non-secret instance config as
`/etc/coinmaster/hl-stageg-testnet.instance.json`, root-owned and readable by
the trader. It references only `/srv/coinmaster/runtime/configs/stage-g-v1.json`
and the trader StateDirectory.

Before enabling either unit, run the read-only source contract doctor from the
release and the explicit host metadata check, substituting the numeric owners:

```sh
.venv/bin/python scripts/process_isolation_doctor.py \
  --trader-env /etc/coinmaster-hl-stageg-testnet.env \
  --runtime-env /etc/coinmaster-runtime.env \
  --trader-state /var/lib/coinmaster-hl-stageg-testnet \
  --research-state /var/lib/coinmaster-runtime \
  --root-uid 0 --trader-uid "$(id -u coinmaster-hl)" \
  --research-uid "$(id -u coinmaster-research)"
```

Do not start a wallet, submit an order, or deploy as part of that check.
