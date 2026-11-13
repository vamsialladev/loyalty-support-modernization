"""Optional protocol interfaces over the same services as REST: MCP, A2A and AG-UI (spec Part G; RFC-0004).

Each protocol has its own folder, flag and start command. None of them can approve, execute or change a case, and the
app works the same with every one of them off (`tests/test_protocols_off.py`). Domain code never imports from here.
"""
