# Account connection broker (#114)

The Settings connection broker is **source-only** until a separate guarded rollout.
It has no order, transfer, generic signature, or credential export route. Selection
changes only the account displayed by the GUI. The current Stage-G worker is
unchanged and cannot read this store.

## Contract

All routes are under /api/v1/connections. GET lists sanitized records and the
display_connection_id. POST on the collection accepts either
{venue:"hyperliquid",master_address,agent_private_key?} or
{venue:"bybit",api_key,api_secret}. POST /{id}/test runs the fixed venue check;
PUT /{id}/agent-key accepts {agent_private_key:string} only for an existing
Hyperliquid connection and replaces its saved key without changing its master
address. DELETE /{id} removes one record; PUT /display accepts
{connection_id:string|null}. IDs are opaque random values, and the collection
allows multiple accounts per venue. No response contains an API key, API secret,
or agent private key. All requests require the existing browser session cookie.
Writes also require exact Origin https://coinmaster24.com and X-CSRF-Token
from GET /api/v1/auth/session. Bearer automation cannot use these routes.

Hyperliquid testing uses only official POST /info clearinghouseState for the
saved master address and POST /info userRole for the address derived locally
from the saved agent key. It reports VERIFIED only for role=agent and a
case-insensitive exact data.user match to the saved master. Wrong role or master
is MISMATCH; transport or malformed responses are ERROR. An absent key is
NOT_PROVIDED. A newly saved key is checked immediately; POST /{id}/test repeats
both checks. The key is never sent to Info or echoed by any API response. This
proves a current public authorization relation, not a live trading connection.
The pinned Nautilus native address resolver derives the wallet; the broker
has no generic signing or exchange route. Official role contract:
https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint#query-a-users-role

Bybit testing signs only official GET /v5/user/query-api and returns VERIFIED only when readOnly is integer 1.
The response's echoed apiKey and all other raw fields are discarded.

## Activation gate

Build and stage the exact committed runtime release through the existing
native GUI wrapper. Before changing the public route, provision a dedicated
system user/group coinmaster-credentials with no membership in
coinmaster-research or coinmaster-hl. Install coinmaster-connections.service
and ensure /var/lib/coinmaster-connections is owned by that UID and mode 0700;
record files and lock are 0600. The service must use its own root-owned 0600
/etc/coinmaster-connections.env with a fresh random
COINMASTER_CONNECTION_VERIFY_TOKEN. Add the same token to the existing
root-owned GUI EnvironmentFile, without giving the broker that GUI file or
giving research/trader access to the broker file. Never put the token in Git,
shell history, an issue, or a diagnostic receipt. Start only the GUI and broker
units during the eventual guarded rollout; do not restart Stage-G.

Install the updated exact-host Nginx template only after the broker is healthy.
It routes /api/v1/connections directly to 127.0.0.1:18184 and denies public
/internal/. Check nginx -t before reload. Browser smoke must cover absent
cookie 401, bearer-only 401, wrong Origin/CSRF 403, sentinel secret not echoed
by POST/list/test, read-only Bybit metadata and display selection. Confirm
research and coinmaster-hl UIDs cannot read the credential directory, and
Stage-G PID/order capability is unchanged. Roll back Nginx, GUI and broker
units together if the broker verifier is unavailable; existing credentials
remain in the isolated store for a retry.

The current GUI and research jobs share coinmaster-research. A compromised
GUI process can observe browser session traffic and may impersonate that
session at the broker. The dedicated broker UID prevents direct secret-file
reads by research and coinmaster-hl, but does not eliminate this frontend and
auth-compromise risk. This source change does not establish full isolation.
