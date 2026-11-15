# Deploy remote MCP (Phase 3)

Goal: public **HTTPS** Streamable HTTP at `https://<host>/mcp/` with `/healthz` green.

**Production prototype (live):** https://megmis-api.onrender.com  
- Health: https://megmis-api.onrender.com/healthz  
- MCP: https://megmis-api.onrender.com/mcp/  
- Server card: https://megmis-api.onrender.com/.well-known/mcp.json  
- Dashboard: https://dashboard.render.com/web/srv-dbsvdhe7bikc73cjpqq0  
- Auth: copy `DEV_API_KEY` from Render → Environment (generated on first Blueprint deploy)

Prototype default: **`USE_PERSISTENCE=false`** (no Postgres/Redis). Full stack uses `docker-compose.prod.yml`.

---

## Option A — Render (fastest TLS)

1. Push this repo to GitHub (already: `walter-kudzai-kamanga/megmis`).
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** → select repo (`render.yaml`).
3. After first deploy, copy the service URL (e.g. `https://megmis-xxxx.onrender.com`).
4. Environment → set:
   - `PUBLIC_BASE_URL=https://megmis-xxxx.onrender.com`
   - note generated `DEV_API_KEY`
5. **Manual Deploy** → clear build cache optional → deploy.
6. Verify:

```bash
./scripts/verify_remote_mcp.sh https://megmis-xxxx.onrender.com
API_KEY='…' ./scripts/verify_remote_mcp.sh https://megmis-xxxx.onrender.com
```

Free tier spins down when idle; first request may be slow.

---

## Option B — Fly.io

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
fly apps create megmis-api   # rename in fly.toml if taken
fly secrets set \
  DEV_API_KEY="$(openssl rand -hex 24)" \
  PUBLIC_BASE_URL="https://megmis-api.fly.dev"
fly deploy
./scripts/verify_remote_mcp.sh https://megmis-api.fly.dev
```

Edit `app` / `PUBLIC_BASE_URL` in [`fly.toml`](../../fly.toml) to match the name Fly assigns.

---

## Option C — VPS + Caddy (full PostGIS stack)

```bash
cp .env.example .env.prod
# set PUBLIC_HOST=mcp.example.com
# set PUBLIC_BASE_URL=https://mcp.example.com
# set strong DEV_API_KEY, POSTGRES_PASSWORD, DATABASE_* URLs for compose network
# point DNS A/AAAA for PUBLIC_HOST at the VPS

docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
./scripts/verify_remote_mcp.sh https://mcp.example.com
```

Caddy terminates TLS; API stays on the internal network.

---

## Required env (hosted)

| Variable | Why |
|---|---|
| `PUBLIC_BASE_URL` | Merges hostname into MCP Host/Origin allowlists; fills server card URL |
| `DEV_API_KEY` | Tenant key for mutating tools + REST demos |
| `USE_PERSISTENCE` | `false` for free single-service; `true` with Postgres/Redis |
| `APP_ENV` | `production` |

Optional: tighten `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS` — `PUBLIC_BASE_URL` already appends the public host.

---

## Client config (HTTP)

```json
{
  "mcpServers": {
    "mamiriro-http": {
      "url": "https://YOURHOST/mcp/",
      "headers": {
        "X-API-Key": "meg_…"
      }
    }
  }
}
```

Discovery:

- `GET https://YOURHOST/.well-known/mcp.json`
- `GET https://YOURHOST/.well-known/ai-catalog.json`

---

## Staging vs production

- Use a separate Render/Fly app or hostname for staging.
- Only put the **production** URL in `server.json` `remotes` and public directories.
- After the URL is stable, update [`server.json`](../../server.json) `remotes` and re-run Phase 4 (`mcp-publisher publish`).

---

## Checklist

- [ ] `GET /healthz` → `status` ok or degraded-but-up
- [ ] `GET /.well-known/mcp.json` returns server card with `transports[].url`
- [ ] `https://HOST/mcp/` reachable (not TLS/DNS error)
- [ ] REST call with `X-API-Key` works
- [ ] `PUBLIC_BASE_URL` set to the same host clients use
- [ ] Staging URL not listed in directories
