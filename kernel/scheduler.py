"""Bounded, deterministic multi-domain Portal-OS scheduler."""

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional

from cognitive.core import SIMCore
from cognitive.state import SIMState
from cognitive.trajectory import SIMTrajectory
from substrate.state_model import SubstrateState
from tec.pipelines import TECPipeline
from tec.surfaces import SubstrateSurface

LOGGER = logging.getLogger("portal.scheduler")


class SchedulerLane(Enum):
    COGNITIVE = "cognitive"
    ORCHESTRATION = "orchestration"
    SUBSTRATE = "substrate"
    GOVERNANCE = "governance"


@dataclass
class ScheduledMessage:
    id: str
    lane: SchedulerLane
    priority: int
    payload: Dict[str, Any]
    timestamp: float
    max_age_ms: int = 30000

    def is_stale(self) -> bool:
        return self.timestamp > 0 and (time.time() - self.timestamp) * 1000 > self.max_age_ms


class DomainLane:
    def __init__(self, name: SchedulerLane, max_queue_size: int = 10000) -> None:
        self.name = name
        self.queue: Deque[ScheduledMessage] = deque()
        self.max_queue_size = max_queue_size
        self.processed_count = 0
        self.dropped_count = 0

    def enqueue(self, message: ScheduledMessage) -> bool:
        if len(self.queue) >= self.max_queue_size:
            self.dropped_count += 1
            LOGGER.error("lane full lane=%s message=%s", self.name.value, message.id)
            return False
        self.queue.append(message)
        return True

    def dequeue(self) -> Optional[ScheduledMessage]:
        while self.queue:
            message = self.queue.popleft()
            if not message.is_stale():
                return message
            self.dropped_count += 1
            LOGGER.warning("stale message rejected lane=%s message=%s", self.name.value, message.id)
        return None

    def size(self) -> int:
        return len(self.queue)

    def stats(self) -> Dict[str, Any]:
        return {"name": self.name.value, "queue_size": self.size(), "processed": self.processed_count, "dropped": self.dropped_count}


class MultiDomainScheduler:
    """Compatibility queue scheduler plus the Rebuild 2 synchronous API."""

    def __init__(self, cycle_ms: int = 100, max_steps: int = 16) -> None:
        self.cycle_ms = cycle_ms
        self.max_steps = max_steps
        self.lanes = {lane: DomainLane(lane) for lane in SchedulerLane}
        self.handlers: Dict[SchedulerLane, Callable[[ScheduledMessage], Any]] = {}
        self.running = False
        self.last_sequence = {lane.value: 0 for lane in SchedulerLane}
        self.sim_core = SIMCore()
        self.sim_trajectory = SIMTrajectory()
        self.sim_trajectory.append(SIMState({"observations": 0}))
        self.substrate = SubstrateState()
        self.tec = TECPipeline(
            SubstrateSurface(self.substrate),
            timeout_ms=cycle_ms,
            max_steps=max_steps,
            autonomy_provider=self._autonomy_state,
        )

    def _autonomy_state(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "scheduler": {
                "running": self.running,
                "cycleMs": self.cycle_ms,
                "maxSteps": self.max_steps,
            },
            "lastSequence": dict(self.last_sequence),
            "lanes": {lane.value: self.lanes[lane].stats() for lane in SchedulerLane},
        }

    def register_handler(self, lane: SchedulerLane, handler: Callable[[ScheduledMessage], Any]) -> None:
        self.handlers[lane] = handler

    def submit(self, lane: SchedulerLane, message: ScheduledMessage) -> bool:
        if lane not in self.lanes:
            raise ValueError(f"unknown lane: {lane}")
        return self.lanes[lane].enqueue(message)

    def cycle(self) -> int:
        started = time.monotonic()
        processed = 0
        for lane in SchedulerLane:
            message = self.lanes[lane].dequeue()
            if message is None:
                continue
            handler = self.handlers.get(lane)
            if handler is None:
                self.lanes[lane].dropped_count += 1
                LOGGER.error("no handler lane=%s message=%s", lane.value, message.id)
                continue
            try:
                handler(message)
                self.lanes[lane].processed_count += 1
                processed += 1
            except Exception:
                self.lanes[lane].dropped_count += 1
                LOGGER.exception("handler failed lane=%s message=%s", lane.value, message.id)
            if (time.monotonic() - started) * 1000 > self.cycle_ms:
                LOGGER.error("scheduler cycle exceeded budgetMs=%d", self.cycle_ms)
                break
        return processed

    def schedule(self, envelope: Mapping[str, Any]) -> Dict[str, Any]:
        self._validate_envelope(envelope)
        lane_names = envelope.get("_route")
        if not isinstance(lane_names, (list, tuple)):
            raise PermissionError("message must be authorized and routed before scheduling")
        if len(lane_names) > self.max_steps:
            raise RuntimeError("scheduler max steps exceeded")
        started = time.monotonic()
        sequence = envelope.get("_sequence")
        if not isinstance(sequence, int) or sequence < 1:
            raise ValueError("invalid routing sequence")

        working = dict(envelope)
        working["_laneResults"] = {}
        results: List[Dict[str, Any]] = []
        for lane_name in lane_names:
            if lane_name not in {lane.value for lane in SchedulerLane}:
                raise ValueError(f"unknown scheduled lane: {lane_name}")
            if sequence <= self.last_sequence[lane_name]:
                raise RuntimeError(f"message ordering violation in {lane_name} lane")
            if (time.monotonic() - started) * 1000 > self.cycle_ms:
                raise TimeoutError("scheduler cycle time exceeded")
            lane_result = self._execute_lane(lane_name, working)
            working["_laneResults"][lane_name] = lane_result
            results.append({"lane": lane_name, "result": lane_result})
            self.last_sequence[lane_name] = sequence
            LOGGER.info("lane complete message=%s sequence=%d lane=%s", envelope["id"], sequence, lane_name)

        duration_ms = (time.monotonic() - started) * 1000
        if duration_ms > self.cycle_ms:
            raise TimeoutError("scheduler cycle time exceeded")
        return {"sequence": sequence, "steps": len(results), "durationMs": round(duration_ms, 3), "lanes": results}

    def _validate_envelope(self, envelope: Mapping[str, Any]) -> None:
        for field in ("id", "type", "payload", "identity", "governanceContext"):
            if field not in envelope:
                raise ValueError(f"message envelope missing {field}")
        if not isinstance(envelope["payload"], Mapping):
            raise ValueError("message payload must be an object")

    def _execute_lane(self, lane: str, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if lane == SchedulerLane.COGNITIVE.value:
            next_state = self.sim_core.step(self.sim_trajectory.current, envelope)
            self.sim_trajectory.append(next_state)
            if not self.sim_trajectory.is_valid():
                raise RuntimeError("SIM Trajectory Valid invariant violated")
            return {"stateVersion": next_state.version, "stateDigest": next_state.digest, "observations": next_state.data["observations"]}
        if lane == SchedulerLane.ORCHESTRATION.value:
            payload = dict(envelope["payload"])
            message_type = str(envelope["type"])
            if (
                message_type == "autonomy.state"
                or message_type.startswith("universe.")
                or message_type in {
                    "identity.physics.license",
                    "governance.engine.license",
                    "apex.alignment.advisory",
                    "umbrella.sim.pack",
                    "umbrella.market.forecast",
                    "umbrella.identity.mirror",
                }
            ):
                task: Dict[str, Any] = {
                    "operation": message_type,
                    "payload": payload,
                    "identity": dict(envelope.get("_identity", {})),
                }
            elif message_type == "ecosystem.step":
                task = dict(payload.get("task") or {"operation": "universe.tick", "payload": payload.get("universe", {})})
            else:
                task = payload
            return self.tec.execute(task)
        if lane == SchedulerLane.SUBSTRATE.value:
            payload = dict(envelope["payload"])
            if envelope["type"] == "substrate" and payload.get("operation") == "read":
                return {"key": payload.get("key"), "value": self.substrate.read(str(payload.get("key", "")), str(payload.get("source", "do")))}
            key = str(payload.get("key") or f"message/{envelope['id']}")
            value = payload.get("value", {"payload": payload, "laneResults": dict(envelope["_laneResults"])})
            return self.substrate.write(key, value)
        if lane == SchedulerLane.GOVERNANCE.value:
            return {"authorized": True, "identity": envelope.get("_identity", {})}
        raise ValueError(f"unsupported lane: {lane}")

    def run(self) -> None:
        self.running = True
        while self.running:
            self.cycle()
            time.sleep(self.cycle_ms / 1000.0)

    def stop(self) -> None:
        self.running = False


_DEFAULT_SCHEDULER = MultiDomainScheduler()


def schedule(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    """Schedule an already authorized/routed envelope."""
    return _DEFAULT_SCHEDULER.schedule(envelope)


class SchedulerCoordinator:
    def __init__(self) -> None:
        self.schedulers: List[MultiDomainScheduler] = []

    def add_scheduler(self, scheduler: MultiDomainScheduler) -> None:
        self.schedulers.append(scheduler)

    def check_deadlock(self) -> bool:
        return any(scheduler.running and all(lane.size() > scheduler.max_steps for lane in scheduler.lanes.values()) for scheduler in self.schedulers)
