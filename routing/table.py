"""Deterministic message type to scheduler lane mappings."""

ROUTES = {
    "sim": ("cognitive",),
    "cognitive": ("cognitive",),
    "tec": ("orchestration",),
    "task": ("orchestration",),
    "substrate": ("substrate",),
    "governance": ("governance",),
    "autonomy.state": ("orchestration",),
    "identity.physics.license": ("orchestration",),
    "governance.engine.license": ("orchestration",),
    "apex.alignment.advisory": ("orchestration",),
    "umbrella.sim.pack": ("orchestration",),
    "umbrella.market.forecast": ("orchestration",),
    "umbrella.identity.mirror": ("orchestration",),
    "umbrella.crossworld.access": ("orchestration",),
    "structural.truth.license": ("orchestration",),
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
    "identity.physics.license": "identity.physics.license",
    "governance.engine.license": "governance.engine.license",
    "apex.alignment.advisory": "apex.alignment.advisory",
    "umbrella.sim.pack": "umbrella.sim.pack",
    "umbrella.market.forecast": "umbrella.market.forecast",
    "umbrella.identity.mirror": "umbrella.identity.mirror",
    "umbrella.crossworld.access": "umbrella.crossworld.access",
    "structural.truth.license": "structural.truth.license",
    "universe.start": "universe.start",
    "universe.tick": "universe.tick",
    "universe.state": "universe.read",
    "universe.umbrella": "universe.read",
}
