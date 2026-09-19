"""Unit coverage for deterministic Umbrella SIM licensing exports."""

import os
import unittest
from unittest.mock import patch

from cognitive.licensing import (
    export_apex_alignment,
    export_governance_engine,
    export_identity_mirror,
    export_identity_physics,
    export_market_forecast,
    export_sim_pack,
    resolve_license_tier,
)
from identity.registry import IdentityRegistry


class LicensingSIMTest(unittest.TestCase):
    def identity(self, tier: str):
        return {"id": "licensed-identity", "attributes": {"licenseTier": tier}}

    def identity_export(self, payload, tier: str):
        return export_identity_physics(payload, resolve_license_tier(self.identity(tier), payload))

    def governance_export(self, payload, tier: str):
        return export_governance_engine(payload, resolve_license_tier(self.identity(tier), payload))

    def apex_export(self, payload, tier: str):
        return export_apex_alignment(payload, resolve_license_tier(self.identity(tier), payload))

    def sim_pack_export(self, payload, tier: str):
        return export_sim_pack(payload, resolve_license_tier(self.identity(tier), payload))

    def market_forecast_export(self, payload, tier: str):
        return export_market_forecast(payload, resolve_license_tier(self.identity(tier), payload))

    def identity_mirror_export(self, payload, tier: str):
        return export_identity_mirror(payload, resolve_license_tier(self.identity(tier), payload))

    def test_identity_physics_export_is_deterministic_and_tier_filtered(self) -> None:
        payload = {"tier": "enterprise", "input": {"subject": "alpha", "coordinates": [1, 2, 3]}}
        first = self.identity_export(payload, "enterprise")
        second = self.identity_export(payload, "enterprise")

        self.assertEqual(first, second)
        self.assertEqual(first["exportMode"], "sim")
        self.assertTrue(first["identitySignature"].startswith("idp_v1_"))
        self.assertEqual(set(first["curvatureVectors"]), {"identity", "relational", "temporal"})
        self.assertGreaterEqual(first["stabilityMetrics"]["score"], 0)
        self.assertLessEqual(first["stabilityMetrics"]["score"], 1)

        basic = self.identity_export({"tier": "basic", "input": payload["input"]}, "enterprise")
        self.assertEqual(basic["allowedOutputs"], ["identitySignature"])
        self.assertEqual(basic["tier"], "basic")
        self.assertFalse(basic["tierCapped"])
        self.assertNotIn("stabilityMetrics", basic)
        self.assertNotIn("curvatureVectors", basic)

    def test_governance_export_models_structure_and_apex_alignment(self) -> None:
        payload = {
            "tier": "enterprise",
            "input": {"mode": "federated", "nodes": ["execution", "apex", "policy", "policy"]},
        }
        export = self.governance_export(payload, "enterprise")

        self.assertEqual(export["mode"], "federated")
        self.assertEqual(export["structure"]["nodes"], ["apex", "execution", "policy"])
        self.assertEqual(export["structure"]["apex"], "apex")
        self.assertGreaterEqual(export["apexAlignment"]["score"], 0.5)
        self.assertLessEqual(export["apexAlignment"]["score"], 1)
        self.assertEqual(set(export["collapseVectors"]), {"authority", "coordination", "resilience"})

    def test_requested_tier_is_capped_and_invalid_inputs_are_rejected(self) -> None:
        capped = self.identity_export({"tier": "enterprise"}, "professional")
        self.assertEqual(capped["tier"], "professional")
        self.assertEqual(capped["requestedTier"], "enterprise")
        self.assertEqual(capped["authorizedTier"], "professional")
        self.assertTrue(capped["tierCapped"])
        self.assertNotIn("curvatureVectors", capped)
        with self.assertRaises(PermissionError):
            resolve_license_tier({"attributes": {}}, {"tier": "basic"})
        with self.assertRaises(ValueError):
            resolve_license_tier(self.identity("enterprise"), {"tier": "unknown"})
        with self.assertRaises(ValueError):
            resolve_license_tier(self.identity("enterprise"), {})
        with self.assertRaises(ValueError):
            self.governance_export({"tier": "basic", "input": []}, "enterprise")

    def test_apex_advisory_is_deterministic_and_tier_filtered(self) -> None:
        payload = {"tier": "enterprise", "input": {"nodes": ["apex", "policy", "execution"]}}
        first = self.apex_export(payload, "enterprise")
        second = self.apex_export(payload, "enterprise")
        self.assertEqual(first, second)
        self.assertEqual(len(first["apexVector"]), 3)
        self.assertGreaterEqual(first["alignmentScore"], 0.5)
        self.assertLessEqual(first["alignmentScore"], 1)
        self.assertIn("structuralAlignmentMap", first)
        self.assertIn("collapseVectorRisk", first)

        capped = self.apex_export(payload, "basic")
        self.assertEqual(capped["tier"], "basic")
        self.assertTrue(capped["tierCapped"])
        self.assertNotIn("structuralAlignmentMap", capped)
        self.assertNotIn("collapseVectorRisk", capped)

    def test_sim_pack_composition_and_metadata_follow_effective_tier(self) -> None:
        model_input = {"scenario": "baseline", "nodes": ["apex", "policy", "execution"]}
        basic = self.sim_pack_export({"tier": "basic", "input": model_input}, "enterprise")
        professional = self.sim_pack_export({"tier": "enterprise", "input": model_input}, "professional")
        enterprise = self.sim_pack_export({"tier": "enterprise", "input": model_input}, "enterprise")
        repeated = self.sim_pack_export({"tier": "enterprise", "input": model_input}, "enterprise")

        self.assertEqual(basic["composition"], ["identitySim"])
        self.assertEqual(professional["composition"], ["identitySim", "governanceSim", "apexSim"])
        self.assertTrue(professional["tierCapped"])
        self.assertNotIn("marketSim", professional["simulations"])
        self.assertEqual(enterprise["composition"], ["identitySim", "governanceSim", "apexSim", "marketSim"])
        self.assertEqual(enterprise, repeated)
        self.assertEqual(enterprise["version"], "sim-pack-v1")
        self.assertTrue(enterprise["deterministicSeed"].startswith("pack_v1_"))
        self.assertGreaterEqual(enterprise["stability"]["score"], 0)
        self.assertLessEqual(enterprise["stability"]["score"], 1)

    def test_market_forecast_is_deterministic_and_tier_filtered(self) -> None:
        payload = {"tier": "enterprise", "input": {"market": "umbrella", "epoch": 12}}
        first = self.market_forecast_export(payload, "enterprise")
        second = self.market_forecast_export(payload, "enterprise")
        self.assertEqual(first, second)
        self.assertEqual(first["exportMode"], "market-forecast")
        self.assertEqual(len(first["marketVector"]), 3)
        self.assertEqual([point["horizon"] for point in first["trendProjection"]], [1, 3, 6])
        self.assertIn("volatilityBand", first)
        self.assertIn("collapseVectorRisk", first)

        capped = self.market_forecast_export(payload, "basic")
        self.assertEqual(capped["tier"], "basic")
        self.assertTrue(capped["tierCapped"])
        self.assertNotIn("volatilityBand", capped)
        self.assertNotIn("collapseVectorRisk", capped)

    def test_identity_mirror_is_deterministic_and_tier_filtered(self) -> None:
        payload = {"tier": "enterprise", "input": {"facets": ["structure", "identity", "behavior"]}}
        enterprise = self.identity_mirror_export(payload, "enterprise")
        repeated = self.identity_mirror_export(payload, "enterprise")
        self.assertEqual(enterprise, repeated)
        self.assertEqual(enterprise["exportMode"], "identity-mirror")
        self.assertTrue(enterprise["identitySignature"].startswith("mirror_v1_"))
        self.assertEqual(len(enterprise["behavioralProjection"]), 3)
        self.assertIn("structuralTruthMap", enterprise)
        self.assertEqual(len(enterprise["quantumBranchPreview"]), 3)

        professional = self.identity_mirror_export(payload, "professional")
        self.assertEqual(professional["tier"], "professional")
        self.assertTrue(professional["tierCapped"])
        self.assertIn("behavioralProjection", professional)
        self.assertIn("structuralTruthMap", professional)
        self.assertNotIn("quantumBranchPreview", professional)

        basic = self.identity_mirror_export({"tier": "basic", "input": payload["input"]}, "enterprise")
        self.assertEqual(basic["allowedOutputs"], ["identitySignature"])

    def test_environment_backed_identity_requires_explicit_tier_configuration(self) -> None:
        with patch.dict(os.environ, {"PORTAL_SERVICE_TOKEN": "service-token"}, clear=True):
            identity = IdentityRegistry().validate("service-token")
            self.assertNotIn("licenseTier", identity.attributes)

        with patch.dict(os.environ, {
            "PORTAL_SERVICE_TOKEN": "service-token",
            "PORTAL_SERVICE_LICENSE_TIER": "professional",
        }, clear=True):
            identity = IdentityRegistry().validate("service-token")
            self.assertEqual(identity.attributes["licenseTier"], "professional")


if __name__ == "__main__":
    unittest.main()
