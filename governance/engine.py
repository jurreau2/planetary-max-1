"""Default-deny governance for Portal-OS lane entry."""

from typing import Any, Mapping, Optional

from identity.registry import Identity


class GovernanceEngine:
    _OPERATOR_ACTIONS = {
        "cognitive.process", "orchestration.execute", "substrate.read",
        "substrate.write", "governance.inspect", "universe.read",
        "universe.tick", "universe.start", "autonomy.read",
        "identity.physics.license", "governance.engine.license",
        "apex.alignment.advisory", "umbrella.sim.pack",
        "umbrella.market.forecast", "umbrella.identity.mirror",
    }
    _OBSERVER_ACTIONS = {
        "cognitive.process", "substrate.read", "governance.inspect",
        "universe.read", "autonomy.read", "identity.physics.license",
        "governance.engine.license",
        "apex.alignment.advisory", "umbrella.sim.pack",
        "umbrella.market.forecast", "umbrella.identity.mirror",
    }

    def authorize(self, identity: Identity, action: str, context: Optional[Mapping[str, Any]] = None) -> bool:
        governance_context = context or {}
        if governance_context.get("deny") is True:
            return False
        requested_tenant = governance_context.get("tenant")
        identity_tenant = identity.attributes.get("tenant")
        if requested_tenant and identity_tenant not in (None, requested_tenant):
            return False
        roles = set(identity.roles)
        if "admin" in roles:
            return True
        if "operator" in roles:
            return action in self._OPERATOR_ACTIONS
        if "observer" in roles:
            return action in self._OBSERVER_ACTIONS
        return False
