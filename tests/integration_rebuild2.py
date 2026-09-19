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
SYSTEM_TOKEN = "integration-system-token"
UNLICENSED_TOKEN = "integration-unlicensed-token"


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
        registry.register(SERVICE_TOKEN, "integration-service", ("operator",), {"licenseTier": "professional"})
        registry.register(OBSERVER_TOKEN, "integration-observer", ("observer",), {"licenseTier": "basic"})
        registry.register(SYSTEM_TOKEN, "integration-system", ("admin",), {"licenseTier": "enterprise"})
        registry.register(UNLICENSED_TOKEN, "integration-unlicensed", ("operator",))
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

    def test_identity_physics_license_tiers_filter_deterministic_sim_exports(self) -> None:
        request = {"tier": "professional", "input": {"subject": "planetary-operator", "epoch": 7}}
        first = self.kernel.handle_message(envelope("identity-license-1", "identity.physics.license", request))
        second = self.kernel.handle_message(envelope("identity-license-2", "identity.physics.license", request))
        self.assertTrue(first["ok"], first)
        first_data = first["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        second_data = second["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(first_data, second_data)
        self.assertEqual(first_data["tier"], "professional")
        self.assertFalse(first_data["tierCapped"])
        self.assertIn("identitySignature", first_data)
        self.assertIn("stabilityMetrics", first_data)
        self.assertNotIn("curvatureVectors", first_data)

        enterprise = self.kernel.handle_message(envelope(
            "identity-license-3",
            "identity.physics.license",
            {"tier": "enterprise", "input": {"subject": "planetary-admin"}},
            SYSTEM_TOKEN,
        ))
        enterprise_data = enterprise["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertIn("curvatureVectors", enterprise_data)

    def test_governance_engine_license_tiers_and_capping(self) -> None:
        basic = self.kernel.handle_message(envelope(
            "governance-license-1",
            "governance.engine.license",
            {"tier": "basic", "input": {"mode": "federated", "nodes": ["policy", "apex"]}},
            OBSERVER_TOKEN,
        ))
        self.assertTrue(basic["ok"], basic)
        data = basic["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(data["mode"], "federated")
        self.assertIn("structure", data)
        self.assertNotIn("apexAlignment", data)
        self.assertNotIn("collapseVectors", data)

        capped = self.kernel.handle_message(envelope(
            "governance-license-2",
            "governance.engine.license",
            {"tier": "enterprise", "input": {}},
            OBSERVER_TOKEN,
        ))
        self.assertTrue(capped["ok"], capped)
        capped_data = capped["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(capped_data["tier"], "basic")
        self.assertEqual(capped_data["requestedTier"], "enterprise")
        self.assertTrue(capped_data["tierCapped"])
        self.assertNotIn("apexAlignment", capped_data)
        self.assertNotIn("collapseVectors", capped_data)

        unlicensed = self.kernel.handle_message(envelope(
            "governance-license-3",
            "governance.engine.license",
            {"tier": "basic", "input": {}},
            UNLICENSED_TOKEN,
        ))
        self.assertFalse(unlicensed["ok"])
        self.assertEqual(unlicensed["error"]["code"], "FORBIDDEN")

        missing_tier = self.kernel.handle_message(envelope(
            "governance-license-4",
            "governance.engine.license",
            {"input": {}},
            SYSTEM_TOKEN,
        ))
        self.assertFalse(missing_tier["ok"])
        self.assertEqual(missing_tier["error"]["code"], "INVALID_MESSAGE")

    def test_apex_advisory_and_sim_pack_are_tier_capped(self) -> None:
        apex = self.kernel.handle_message(envelope(
            "apex-advisory-1",
            "apex.alignment.advisory",
            {"tier": "enterprise", "input": {"nodes": ["apex", "policy"]}},
            OBSERVER_TOKEN,
        ))
        self.assertTrue(apex["ok"], apex)
        apex_data = apex["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(apex_data["tier"], "basic")
        self.assertTrue(apex_data["tierCapped"])
        self.assertIn("apexVector", apex_data)
        self.assertIn("alignmentScore", apex_data)
        self.assertNotIn("structuralAlignmentMap", apex_data)
        self.assertNotIn("collapseVectorRisk", apex_data)

        pack_request = {"tier": "enterprise", "input": {"scenario": "revenue-baseline"}}
        first_pack = self.kernel.handle_message(envelope(
            "sim-pack-1", "umbrella.sim.pack", pack_request, SERVICE_TOKEN,
        ))
        second_pack = self.kernel.handle_message(envelope(
            "sim-pack-2", "umbrella.sim.pack", pack_request, SERVICE_TOKEN,
        ))
        self.assertTrue(first_pack["ok"], first_pack)
        first_data = first_pack["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        second_data = second_pack["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(first_data, second_data)
        self.assertEqual(first_data["tier"], "professional")
        self.assertTrue(first_data["tierCapped"])
        self.assertEqual(first_data["composition"], ["identitySim", "governanceSim", "apexSim"])
        self.assertNotIn("marketSim", first_data["simulations"])

        enterprise_pack = self.kernel.handle_message(envelope(
            "sim-pack-3", "umbrella.sim.pack", pack_request, SYSTEM_TOKEN,
        ))
        enterprise_data = enterprise_pack["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertIn("marketSim", enterprise_data["simulations"])

        unlicensed_pack = self.kernel.handle_message(envelope(
            "sim-pack-4", "umbrella.sim.pack", {"tier": "basic"}, UNLICENSED_TOKEN,
        ))
        self.assertFalse(unlicensed_pack["ok"])
        self.assertEqual(unlicensed_pack["error"]["code"], "FORBIDDEN")

    def test_market_forecast_and_identity_mirror_are_tier_capped(self) -> None:
        forecast_request = {"tier": "enterprise", "input": {"market": "umbrella", "epoch": 12}}
        basic_forecast = self.kernel.handle_message(envelope(
            "market-forecast-1", "umbrella.market.forecast", forecast_request, OBSERVER_TOKEN,
        ))
        self.assertTrue(basic_forecast["ok"], basic_forecast)
        forecast_data = basic_forecast["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(forecast_data["tier"], "basic")
        self.assertTrue(forecast_data["tierCapped"])
        self.assertIn("marketVector", forecast_data)
        self.assertIn("trendProjection", forecast_data)
        self.assertNotIn("volatilityBand", forecast_data)
        self.assertNotIn("collapseVectorRisk", forecast_data)

        enterprise_forecast = self.kernel.handle_message(envelope(
            "market-forecast-2", "umbrella.market.forecast", forecast_request, SYSTEM_TOKEN,
        ))
        enterprise_forecast_data = enterprise_forecast["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertIn("volatilityBand", enterprise_forecast_data)
        self.assertIn("collapseVectorRisk", enterprise_forecast_data)

        mirror_request = {"tier": "enterprise", "input": {"facets": ["identity", "behavior", "structure"]}}
        first_mirror = self.kernel.handle_message(envelope(
            "identity-mirror-1", "umbrella.identity.mirror", mirror_request, SERVICE_TOKEN,
        ))
        second_mirror = self.kernel.handle_message(envelope(
            "identity-mirror-2", "umbrella.identity.mirror", mirror_request, SERVICE_TOKEN,
        ))
        self.assertTrue(first_mirror["ok"], first_mirror)
        first_data = first_mirror["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        second_data = second_mirror["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(first_data, second_data)
        self.assertEqual(first_data["tier"], "professional")
        self.assertTrue(first_data["tierCapped"])
        self.assertIn("behavioralProjection", first_data)
        self.assertIn("structuralTruthMap", first_data)
        self.assertNotIn("quantumBranchPreview", first_data)

        enterprise_mirror = self.kernel.handle_message(envelope(
            "identity-mirror-3", "umbrella.identity.mirror", mirror_request, SYSTEM_TOKEN,
        ))
        enterprise_mirror_data = enterprise_mirror["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertIn("quantumBranchPreview", enterprise_mirror_data)

    def test_crossworld_access_and_structural_truth_are_kernel_authorized(self) -> None:
        crossworld_request = {"tier": "enterprise", "input": {"worlds": ["origin", "adjacent"]}}
        crossworld = self.kernel.handle_message(envelope(
            "crossworld-1", "umbrella.crossworld.access", crossworld_request, SERVICE_TOKEN,
        ))
        self.assertTrue(crossworld["ok"], crossworld)
        crossworld_data = crossworld["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(crossworld_data["tier"], "professional")
        self.assertTrue(crossworld_data["tierCapped"])
        self.assertIn("traversalMap", crossworld_data)
        self.assertNotIn("quantumBridge", crossworld_data)

        truth_request = {"tier": "enterprise", "input": {"facets": ["identity", "structure"]}}
        truth = self.kernel.handle_message(envelope(
            "structural-truth-1", "structural.truth.license", truth_request, OBSERVER_TOKEN,
        ))
        self.assertTrue(truth["ok"], truth)
        truth_data = truth["result"]["lanes"][0]["result"]["results"][0]["result"]["data"]
        self.assertEqual(truth_data["tier"], "basic")
        self.assertIn("truthSignature", truth_data)
        self.assertNotIn("structuralTruthMap", truth_data)

        unlicensed = self.kernel.handle_message(envelope(
            "crossworld-2", "umbrella.crossworld.access", {"tier": "basic"}, UNLICENSED_TOKEN,
        ))
        self.assertFalse(unlicensed["ok"])
        self.assertEqual(unlicensed["error"]["code"], "FORBIDDEN")

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
