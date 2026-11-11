"""A read-only MCP server for AI clients (spec G.3; ADR-0023; RFC-0004).

Start: `uv run python -m protocols.mcp.server` with `FEATURE_MCP=true`. Streamable HTTP on 127.0.0.1, MCP
2026-07-28 (older 2025-11-25 clients are served by the same SDK). Six tools, each reading one case the caller's
customer owns; nothing writes. When REST is enough: `docs/mcp.md`.
"""
