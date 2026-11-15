"""MCP stdio entrypoint for local hosts (Cursor, Claude Desktop, mcp dev)."""

from __future__ import annotations

from megmis.common.auth import seed_dev_key
from megmis.common.tenant_ctx import set_tenant_context
from megmis.config import get_settings
from megmis.mcp.server import mcp


def main() -> None:
    settings = get_settings()
    # Bind demo tenant for the process so mutating tools work without X-API-Key.
    set_tenant_context(seed_dev_key(settings))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
