# MCP directory listing pack (Phase 6)

Reuse this copy everywhere. Status: **prototype / mock providers by default**.

## Identity

| Field | Value |
|---|---|
| Product | Mamiriro (MEGMIS) |
| Package | `megmis` (PyPI) |
| Registry name | `io.github.walter-kudzai-kamanga/megmis` |
| One-liner | PROTOTYPE: Zimbabwe weather, geo, safe routing & journey risk via REST+MCP (stdio/HTTP). |
| Stdio | `uvx --from megmis megmis-mcp` or `pip install megmis && megmis-mcp` |
| Remote MCP | `https://megmis-api.onrender.com/mcp/` |
| Health | `https://megmis-api.onrender.com/healthz` |
| Server card | `https://megmis-api.onrender.com/.well-known/mcp.json` |
| Auth | `X-API-Key` for mutating tools / HTTP; optional for read-only local demos |
| Repo | https://github.com/walter-kudzai-kamanga/megmis |

## Transports

- **stdio** — local clients (Cursor, Claude Desktop, VS Code, Windsurf)
- **streamable-http** — hosted `/mcp/` on Render

## Read vs write (summary)

- **Read:** weather, geocode, optimize_route, corridor/traffic, journey risk assessment
- **Write (auth):** `report_road_condition`, `create_journey`, `reroute`

## Example prompts

- Plan the safest Harare → Bulawayo drive and explain the cost breakdown.
- Assess weather risk for outdoor work in Mutare tomorrow.
- List road incidents on the Harare–Bulawayo corridor.
- Assess journey risk from Harare to Bulawayo for a light truck.

## Submission checklist

| Target | How | Status |
|---|---|---|
| Official MCP Registry | CI `mcp-registry` / `mcp-publisher publish server.json` | ✅ Live |
| Smithery | Proxy/new flow deprecated (Arcade); keep `smithery.yaml` for crawlers | N/A / optional |
| Glama | Add GitHub repo + claim via root `glama.json` | Ready (needs GitHub sign-in) |
| mcp.so | https://mcp.so/submit — free review or $39 instant | Ready (needs Sign In / pay) |
| PulseMCP | Indexes official registry | Should auto-follow registry |
| Awesome MCP Servers | PR with one-line entry + Glama badge | After Glama |
| Claude / Anthropic | Connector with remote URL | Manual portal |
| Cursor directory | Listing + stdio/HTTP configs | Manual |
| ChatGPT connectors | Remote URL + auth notes | Manual |

## Hosted URL submission (Smithery / Glama / etc.)

```text
Name: Mamiriro (MEGMIS)
URL: https://megmis-api.onrender.com/mcp/
Health: https://megmis-api.onrender.com/healthz
Category: Weather / Geospatial / Travel
Tags: zimbabwe, weather, routing, mcp, prototype
```
