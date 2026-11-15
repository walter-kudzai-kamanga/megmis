"""MCP stdio entrypoint for local hosts (Cursor, Claude Desktop, mcp dev)."""

from __future__ import annotations

from megmis.common.auth import seed_dev_key
from megmis.config import get_settings
from megmis.mcp.server import mcp


def main() -> None:
    seed_dev_key(get_settings())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
