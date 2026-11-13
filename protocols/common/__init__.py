"""What the protocol services share: checking access tokens as a resource server, and auditing calls.

Shared code, not a shared protocol: each protocol keeps its own messages, errors and lifecycle (spec G.2: no universal
adapter that hides protocol differences).
"""
