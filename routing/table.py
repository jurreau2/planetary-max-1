"""Deterministic message type to scheduler lane mappings."""

ROUTES = {
    "sim": ("cognitive",),
    "cognitive": ("cognitive",),
    "tec": ("orchestration",),
    "task": ("orchestration",),
    "substrate": ("substrate",),
    "governance": ("governance",),
    "autonomy.state": ("orchestration",),
    "universe.start": ("orchestration",),
    "universe.tick": ("orchestration",),
    "universe.state": ("orchestration",),
    "universe.umbrella": ("orchestration",),
    "ecosystem.step": ("cognitive", "orchestration", "substrate"),
}

LANE_ACTIONS = {
    "cognitive": "cognitive.process",
    "orchestration": "orchestration.execute",
    "substrate": "substrate.write",
    "governance": "governance.inspect",
}

MESSAGE_ACTIONS = {
    "autonomy.state": "autonomy.read",
    "universe.start": "universe.start",
    "universe.tick": "universe.tick",
    "universe.state": "universe.read",
    "universe.umbrella": "universe.read",
}
