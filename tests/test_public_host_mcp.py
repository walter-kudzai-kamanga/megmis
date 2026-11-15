from __future__ import annotations


def test_public_base_url_extends_mcp_allowlists(monkeypatch):
    from megmis.config import get_settings

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://megmis-demo.onrender.com")
    get_settings.cache_clear()
    s = get_settings()
    assert s.public_host == "megmis-demo.onrender.com"
    hosts = s.effective_mcp_allowed_hosts()
    assert "megmis-demo.onrender.com" in hosts
    assert "megmis-demo.onrender.com:*" in hosts
    origins = s.effective_mcp_allowed_origins()
    assert "https://megmis-demo.onrender.com" in origins
    get_settings.cache_clear()


def test_server_card_includes_public_mcp_url(monkeypatch):
    from megmis.config import get_settings
    from megmis.mcp.runtime import server_card

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://mcp.example.com")
    get_settings.cache_clear()
    card = server_card()
    http = next(t for t in card["transports"] if t["type"] == "streamable-http")
    assert http["url"] == "https://mcp.example.com/mcp/"
    get_settings.cache_clear()
