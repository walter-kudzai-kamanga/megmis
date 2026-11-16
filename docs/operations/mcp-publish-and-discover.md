# MCP Publish & Worldwide Discovery Playbook

**Trigger:** Run this checklist only after MCP + REST Gen‑1 is built, tests are green, and the team is ready to ship. This is the **final project gate** before Mamiriro is treated as publicly usable.

**Server profile (this repo):**
- **Language:** Python 3.12 (`megmis` on PyPI path)
- **Local / stdio:** `python -m megmis.mcp_stdio` / `megmis-mcp`
- **Remote / HTTP:** Streamable HTTP at `/mcp` (same FastAPI process as REST)
- **Package name:** `megmis` (align `mcpName` / registry name with product: Mamiriro)

Do not start publishing while mocks-only prototypes are still the only story for production users unless the listing clearly says **prototype / mock providers**.

---

## Phase 0 — Pre-flight (must pass)

- [x] `pytest -q` green; MCP contract tests green *(2026-11-15: 54 non-integration + MCP contract/functional green)*
- [x] `ruff` clean (`src` / `tests` / `scripts`; UP042/UP046 ignored as unsafe schema refactors)
- [x] README has copy-paste configs for **stdio** and **HTTP** (Cursor, Claude Desktop, VS Code, Windsurf)
- [x] Tools have clear names, descriptions, and read vs write annotations (`ToolAnnotations` `_READ` / `_WRITE`)
- [x] Auth story documented (`X-API-Key` / future OAuth); `.env` gitignored; no live secrets committed
- [x] Version set in `pyproject.toml` (`0.1.0` — first public ship; bump on each release)
- [x] Canonical remote: `https://github.com/walter-kudzai-kamanga/megmis.git` (confirm **public** before registry submit)
- [x] `server.json` (PyPI stdio) + README `<!-- mcp-name: io.github.walter-kudzai-kamanga/megmis -->` + `/.well-known/mcp.json`

**Exit:** “Ready to publish” — not “still building features.” ✅ Phase 0 complete.  
**Public prototype posture:** MIT license; PyPI/registry listings must say **prototype / mock providers** until hosted HTTPS + live adapters are the default story.

---

## Phase 1 — Choose distribution (do both for Mamiriro)

| Channel | What users get | Artifact |
|---|---|---|
| **Local / stdio** | Install package, run CLI, wire `mcp.json` | PyPI wheel + console script `megmis-mcp` |
| **Remote / HTTP** | HTTPS URL to Streamable HTTP `/mcp` | Deployed container / PaaS |
| **Directories** | Discovery in Claude, Cursor, ChatGPT, Glama, etc. | Registry + listings |

---

## Phase 2 — Package for local users (PyPI)

1. Ensure `pyproject.toml` metadata is complete (`name`, `version`, `description`, `readme`, scripts).
2. Build and upload (prefer **Trusted Publishing / OIDC** from CI — no long-lived tokens):

```bash
python -m build
# Prefer GitHub Actions OIDC → PyPI; manual only if needed:
# twine upload dist/*
```

3. Verify install from a clean env:

```bash
pip install megmis
megmis-mcp --help   # or: python -m megmis.mcp_stdio
```

4. Publish matching **stdio** install snippets in README (absolute command path not required for published package).

**Status (2026-11-16):** ✅ **Live on PyPI** — https://pypi.org/project/megmis/ (`0.1.0`).  
Trusted Publisher + `release.yml` tag/`workflow_dispatch` path verified (`v0.1.1` publish green).

---

## Phase 3 — Deploy remote HTTP (if offering hosted MCP)

1. Deploy API image (Docker Compose / Render / Fly / Azure / etc.) with TLS.
2. Confirm health: `GET /healthz`
3. Confirm MCP: Streamable HTTP endpoint `https://<host>/mcp/`
4. Document required headers (e.g. API key) and CORS for browser clients if any.
5. Keep staging and production URLs distinct; only list **production** in public directories.

**Status (2026-11-15):** ✅ **Live on Render** — https://megmis-api.onrender.com  
(`/healthz` ok, `/.well-known/mcp.json` ok, `/mcp/` Streamable HTTP responding).  
`server.json` `remotes` points at `https://megmis-api.onrender.com/mcp/`.  
API key: Render Environment → `DEV_API_KEY` (generated; not the local demo key).

---

## Phase 4 — Official MCP Registry (`server.json` + publisher)

1. Add / maintain `server.json` at repo root (or path expected by `mcp-publisher`):
   - ownership / namespace (GitHub org or domain)
   - version (must match package)
   - packages (PyPI) and/or remote URL
   - transport: `stdio` and/or `streamable-http`
2. Validate the manifest (per current MCP publisher docs).
3. Install CLI, authenticate, publish:

```bash
# Install mcp-publisher per current official docs (Homebrew or release binary)
mcp-publisher login github
# Until PyPI package megmis is live, publish remotes-only:
mcp-publisher publish server.remote.json
# After PyPI: mcp-publisher publish server.json
```

4. Verify listing via the official registry API / website.
5. Automate: on every **semver git tag**, CI republishes `server.json` so versions never go stale (extend [cicd-pipeline.md](cicd-pipeline.md)).

**Status (2026-11-16):** ✅ manifests validate (description ≤100); PyPI live → CI publishes **`server.json`**.  
`release.yml` `mcp-registry` job uses GitHub OIDC + soft-fail.  
**Verify:** `curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=megmis'` should return the server after a green `mcp-registry` job.

---

## Phase 5 — Domain discovery (hosted / branded domain)

When a public domain exists (e.g. `mamiriro.<tld>` or org domain):

- [x] Serve a **Server Card** under `/.well-known/` with CORS allowing client inspection
- [x] Serve `/.well-known/ai-catalog.json` pointing at the server card / MCP endpoint
- [ ] If OAuth-protected: publish protected-resource metadata so clients can discover auth *(N/A until OAuth)*

These let clients that only know the domain locate MCP without a directory browse.

**Status (2026-11-16):** ✅ on Render host `megmis-api.onrender.com`  
(`/.well-known/mcp.json`, `/.well-known/ai-catalog.json`, `Access-Control-Allow-Origin` reflects request Origin).  
Custom `mamiriro.<tld>` optional later; OAuth PRM deferred.

---

## Phase 6 — Client marketplaces & AI directories

Submit (or open PRs) with the **same** name, description, and install snippets everywhere:

| Target | What to submit |
|---|---|
| Claude / Anthropic developer portal | MCP connector (remote URL) and/or plugin bundle |
| ChatGPT Apps / Connectors | Connector listing + remote URL |
| Cursor directory | Listing + stdio/HTTP config |
| Microsoft MCP / Copilot (if pursuing enterprise) | Certification path when available |
| Glama, MCP.so, PulseMCP, Awesome MCP Servers | PR or form listing + health URL |
| Official MCP Registry | Already Phase 4 — keep in sync |
| Smithery | Root `smithery.yaml` + URL/repo submit |

**Listing copy checklist (reuse everywhere):**
- One-line value prop (Zimbabwe / regional weather + geospatial + safe routing)
- Transports supported (stdio + HTTP)
- Auth required
- “Read-only vs mutating tools” summary
- Link to docs + example prompts
- Status: prototype vs production providers

**Status (2026-11-16):** ✅ listing pack + `smithery.yaml` in repo — see [mcp-directory-listings.md](mcp-directory-listings.md).  
**Manual remaining:** submit the pack to ≥3 hubs (Smithery, Glama/mcp.so, Awesome MCP PR, plus Claude/Cursor/ChatGPT portals).

---

## Phase 7 — Docs that drive adoption (GEO)

Directory pages are often poorly indexed. Own docs matter most:

- [x] Landing page or README section: **copy-paste configs** for Claude Code, Cursor, VS Code, Windsurf, ChatGPT
- [x] Example prompts that match real tools (`optimize_route` Harare→Bulawayo, weather risk, etc.)
- [x] Clear tool annotations (read vs write) for enterprise scanners
- [x] Consistent naming: **Mamiriro** / **MEGMIS** / package `megmis` explained once

**Status (2026-11-16):** ✅ README public URLs + Claude Code / ChatGPT / remote production snippets.

---

## Phase 8 — Release automation (keep recognition fresh)

On every tagged release (`vX.Y.Z`):

1. Build + test
2. Publish PyPI (OIDC)
3. Build + push container image
4. Deploy staging → smoke → production (if hosted)
5. `mcp-publisher publish` (or equivalent Action)
6. Sync version strings in README / `server.json` / directory listings if not auto-synced

See also [cicd-pipeline.md](cicd-pipeline.md) — publishing is an extension of stages 7–9, not a one-off.

**Status (2026-11-16):** ✅ `release.yml` — build, PyPI (`skip-existing`), MCP registry (OIDC, soft-fail), GHCR image push.  
Render production deploy remains **out-of-band** (Blueprint/auto-deploy from `main`), not duplicated in Actions.

---

## Phase 9 — Community proof (ongoing)

- Short demo (Harare→Bulawayo explained route + weather risk) on X, YouTube, Reddit (`r/mcp`, etc.)
- Respond to directory health-check failures quickly (badges drive trust)
- Re-run this playbook on major version bumps

**Status:** ongoing / human — not started as an agent gate.

---

## Agent / human “done” definition

Mamiriro MCP is **recognized for worldwide use** when **all** are true:

1. Installable from PyPI (stdio) **or** reachable via public HTTPS MCP URL  
2. Listed on the **official MCP Registry** with a valid `server.json`  
3. At least **three** major directories/clients submitted (Claude, Cursor, one community hub minimum)  
4. README install snippets work on a clean machine  
5. CI republishes registry metadata on release tags  

Until then, treat “publish” as incomplete — finish the remaining phases rather than inventing new product scope.

---

## Related docs

- [mcp-tool-contracts.md](../api/mcp-tool-contracts.md)
- [cicd-pipeline.md](cicd-pipeline.md)
- [roadmap-and-milestones.md](../planning/roadmap-and-milestones.md)
- Root [README.md](../../README.md)
