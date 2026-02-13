# Public link (localhost.run)

## Goal
Get a stable preview URL for CoinMaster dashboard.

## One-time setup (for longer-lived/fixed link)
1. SSH key created locally:
   - `~/.ssh/id_ed25519`
   - `~/.ssh/id_ed25519.pub`
2. Add public key content from `~/.ssh/id_ed25519.pub` to:
   - https://admin.localhost.run
3. For requested subdomain (`coinmaster-vf`) use `plan@localhost.run`.

## Run
```bash
cd /Users/vf/.openclaw/workspace/coinmaster
npm run build
npm run start
# in second terminal
npm run tunnel:fixed
```

If fixed subdomain is not yet linked in admin panel, use temporary tunnel:
```bash
npm run tunnel
```

## Health checks
- Local API: `curl -sS http://127.0.0.1:8787/api/dashboard | head`
- Local web: `curl -I http://127.0.0.1:8787/`

## Notes
- Free anonymous tunnels rotate domain names and are not permanent.
- Keepalive is enabled (`ServerAliveInterval=60`) to reduce random disconnects.
