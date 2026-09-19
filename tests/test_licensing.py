"""Unit coverage for deterministic Umbrella SIM licensing exports."""

import os
import unittest
from unittest.mock import patch

from cognitive.licensing import export_governance_engine, export_identity_physics, resolve_license_tier
from identity.registry import IdentityRegistry


class LicensingSIMTest(unittest.TestCase):
    def identity(self, tier: str):
        return {"id": "licensed-identity", "attributes": {"licenseTier": tier}}

    def identity_export(self, payload, tier: str):
        return export_identity_physics(payload, resolve_license_tier(self.identity(tier), payload))

    def governance_export(self, payload, tier: str):
        return export_governance_engine(payload, resolve_license_tier(self.identity(tier), payload))

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
