"""Single-script integration coverage for Portal-OS Rebuild 2."""

import json
import subprocess
import os
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.boot import Kernel, KernelPhase
from identity.registry import IdentityRegistry

SERVICE_TOKEN = "integration-service-token"
OBSERVER_TOKEN = "integration-observer-token"


def envelope(message_id: str, message_type: str, payload: Dict[str, Any], identity: str = SERVICE_TOKEN) -> Dict[str, Any]:
    return {
        "id": message_id,
        "type": message_type,
        "payload": payload,
        "identity": identity,
        "governanceContext": {"test": True},
    }


class Rebuild2IntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        registry = IdentityRegistry()
        registry.register(SERVICE_TOKEN, "integration-service", ("operator",))
        registry.register(OBSERVER_TOKEN, "integration-observer", ("observer",))
        self.kernel = Kernel(registry)
        self.assertEqual(self.kernel.boot().phase, KernelPhase.READY)

    def test_cli_worker_bridge_processes_one_json_message(self) -> None:
        process_environment = dict(os.environ)
        process_environment["PORTAL_SERVICE_TOKEN"] = SERVICE_TOKEN
        completed = subprocess.run(
            [sys.executable, "kernel/boot.py", "--message"],
            cwd=str(ROOT),
            input=json.dumps(envelope("bridge-1", "sim", {"observation": "rain"})),
            text=True,
            capture_output=True,
            timeout=2,
            check=True,
            env=process_environment,
        )
        response = json.loads(completed.stdout)
        self.assertTrue(response["ok"])
        self.assertEqual(response["route"], ["cognitive"])

    def test_identity_and_governance_reject_explicitly(self) -> None:
        missing = envelope("identity-1", "sim", {})
        missing["identity"] = ""
        response = self.kernel.handle_message(missing)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "UNAUTHENTICATED")

        invalid = self.kernel.handle_message(envelope("identity-2", "universe.state", {}, "not-registered"))
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["error"]["code"], "UNAUTHENTICATED")

        denied = self.kernel.handle_message(envelope("governance-1", "universe.tick", {}, OBSERVER_TOKEN))
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "FORBIDDEN")

    def test_autonomy_state_returns_scheduler_telemetry(self) -> None:
        response = self.kernel.handle_message(envelope("autonomy-1", "autonomy.state", {}, OBSERVER_TOKEN))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["route"], ["orchestration"])
        data = response["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["scheduler"]["maxSteps"], 16)
        self.assertIn("orchestration", data["lanes"])

    def test_sim_tec_substrate_flow_and_invariants(self) -> None:
        started = time.monotonic()
        response = self.kernel.handle_message(envelope(
            "ecosystem-1",
            "ecosystem.step",
            {"universe": {"changes": {"population": 2}}, "key": "planet/latest"},
        ))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["route"], ["cognitive", "orchestration", "substrate"])
        self.assertEqual(response["result"]["steps"], 3)
        self.assertLess((time.monotonic() - started) * 1000, 500)
        self.assertTrue(self.kernel.scheduler.sim_trajectory.is_valid())
        self.assertTrue(self.kernel.scheduler.substrate.is_consistent())
        self.assertTrue(self.kernel.scheduler.substrate.kv_eventually_consistent())
        self.assertIsNotNone(self.kernel.scheduler.substrate.read("planet/latest"))

    def test_universe_state_tick_and_umbrella(self) -> None:
        tick = self.kernel.handle_message(envelope("universe-1", "universe.tick", {"changes": {"resources": -1}}))
        self.assertTrue(tick["ok"], tick)
        state = self.kernel.handle_message(envelope("universe-2", "universe.state", {}, OBSERVER_TOKEN))
        umbrella = self.kernel.handle_message(envelope("universe-3", "universe.umbrella", {}, OBSERVER_TOKEN))
        self.assertTrue(state["ok"], state)
        self.assertTrue(umbrella["ok"], umbrella)
        state_data = state["result"]["lanes"][0]["result"]["results"][0]["result"]
        self.assertGreaterEqual(state_data["data"]["tick"], 1)
        umbrella_data = umbrella["result"]["lanes"][0]["result"]["results"][0]["result"]
        self.assertEqual(umbrella_data["data"]["governance"], "umbrella")

    def test_tec_execution_is_bounded(self) -> None:
        actions = [{"operation": "noop"} for _ in range(17)]
        response = self.kernel.handle_message(envelope("bounded-1", "tec", {"actions": actions}))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVARIANT_VIOLATION")
        self.assertIn("bounded", response["error"]["message"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
