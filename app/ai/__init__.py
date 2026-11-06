"""The AI layer of arm C: context, tools, the bounded loop, validation and the harness around them (RFC-0002).

The model can read through narrow tools and write text. It can't decide: identity, eligibility, the amount,
permissions, approval and execution stay in deterministic Python, exactly where arm B has them.
"""
