"""Bounded TEC task pipeline and MAX-OS-1 surface wiring."""

import time
from typing import Any, Callable, Dict, Mapping, Optional

from cognitive.licensing import (
    export_apex_alignment,
    export_governance_engine,
    export_identity_physics,
    export_identity_mirror,
    export_market_forecast,
    export_sim_pack,
    resolve_license_tier,
)
from maxos_bridge import get_umbrella_status, get_universe_state, start_universe, tick_universe
from tec.surfaces import SubstrateSurface


class TECPipeline:
    def __init__(
        self,
        substrate_surface: SubstrateSurface,
        timeout_ms: int = 100,
        max_steps: int = 16,
        autonomy_provider: Optional[Callable[[], Mapping[str, Any]]] = None,
    ) -> None:
        self.substrate_surface = substrate_surface
        self.timeout_ms = timeout_ms
        self.max_steps = max_steps
        self.autonomy_provider = autonomy_provider

    def execute(self, task: Mapping[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        actions = task.get("actions")
        if actions is None:
            actions = [task]
        if not isinstance(actions, list) or len(actions) > self.max_steps:
            raise RuntimeError("TEC Execution Bounded invariant violated")
        results = []
        for index, action in enumerate(actions):
            if not isinstance(action, Mapping):
                raise ValueError("TEC action must be an object")
            if (time.monotonic() - started) * 1000 > self.timeout_ms:
                raise TimeoutError("TEC execution exceeded its time budget")
            results.append({"step": index, "result": self._execute_one(action)})
            if (time.monotonic() - started) * 1000 > self.timeout_ms:
                raise TimeoutError("TEC execution exceeded its time budget")
        return {
            "status": "complete",
            "steps": len(results),
            "durationMs": round((time.monotonic() - started) * 1000, 3),
            "results": results,
        }

    def _execute_one(self, task: Mapping[str, Any]) -> Any:
        operation = str(task.get("operation") or task.get("type") or "noop")
        if operation == "autonomy.state":
            if self.autonomy_provider is None:
                raise RuntimeError("autonomy telemetry provider is unavailable")
            return {
                "ok": True,
                "operation": "autonomy.state",
                "backend": "kernel",
                "data": dict(self.autonomy_provider()),
            }
        umbrella_exports = {
            "identity.physics.license": export_identity_physics,
            "governance.engine.license": export_governance_engine,
            "apex.alignment.advisory": export_apex_alignment,
            "umbrella.sim.pack": export_sim_pack,
            "umbrella.market.forecast": export_market_forecast,
            "umbrella.identity.mirror": export_identity_mirror,
        }
        if operation in umbrella_exports:
            payload = task.get("payload")
            identity = task.get("identity")
            if not isinstance(payload, Mapping):
                raise ValueError("Umbrella payload must be an object")
            if not isinstance(identity, Mapping):
                raise PermissionError("Umbrella exports require a validated identity")
            grant = resolve_license_tier(identity, payload)
            return {
                "ok": True,
                "operation": operation,
                "backend": "kernel-sim",
                "data": umbrella_exports[operation](payload, grant),
            }
        if operation == "universe.start":
            return start_universe()
        if operation == "universe.tick":
            return tick_universe(task.get("payload") if isinstance(task.get("payload"), Mapping) else task)
        if operation == "universe.state":
            return get_universe_state()
        if operation == "universe.umbrella":
            return get_umbrella_status()
        if operation.startswith("substrate."):
            normalized = dict(task)
            normalized["operation"] = operation
            return self.substrate_surface.execute(normalized)
        return {"operation": operation, "accepted": True, "payload": task.get("payload", {})}
