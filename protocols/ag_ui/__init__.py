"""AG-UI 1.0: a live view of an arm C investigation, as standard AG-UI events over SSE (spec G.5; RFC-0004).

Mounted in the console only when `FEATURE_AG_UI=true`; `uv run python -m protocols.ag_ui.server` starts the console
with it on. Events are built from stored rows, never from memory, so every viewer sees the same thing. The stream
shows what ran (tool names and an argument hash), not what the model thought, and approving stays on the console's
own form.
"""
