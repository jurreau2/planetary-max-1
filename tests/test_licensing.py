"""Unit coverage for deterministic Umbrella SIM licensing exports."""

import os
import unittest
from unittest.mock import patch

from cognitive.licensing import export_governance_engine, export_identity_physics
from identity.registry import IdentityRegistry


class LicensingSIMTest(unittest.TestCase):
    def identity(self, tier: str):
        return {"id": "licensed-identity", "attributes": {"licenseTier": tier}}

    def test_identity_physics_export_is_deterministic_and_tier_filtered(self) -> None:
        payload = {"licenseTier": "enterprise", "input": {"subject": "alpha", "coordinates": [1, 2, 3]}}
        first = export_identity_physics(payload, self.identity("enterprise"))
        second = export_identity_physics(payload, self.identity("enterprise"))

        self.assertEqual(first, second)
        self.assertEqual(first["exportMode"], "sim")
        self.assertTrue(first["identitySignature"].startswith("idp_v1_"))
        self.assertEqual(set(first["curvatureVectors"]), {"identity", "relational", "temporal"})
        self.assertGreaterEqual(first["stabilityMetrics"]["score"], 0)
        self.assertLessEqual(first["stabilityMetrics"]["score"], 1)

        basic = export_identity_physics({"licenseTier": "basic", "input": payload["input"]}, self.identity("enterprise"))
        self.assertEqual(basic["allowedOutputs"], ["identitySignature"])
        self.assertNotIn("stabilityMetrics", basic)
        self.assertNotIn("curvatureVectors", basic)

    def test_governance_export_models_structure_and_apex_alignment(self) -> None:
        payload = {
            "licenseTier": "enterprise",
            "input": {"mode": "federated", "nodes": ["execution", "apex", "policy", "policy"]},
        }
        export = export_governance_engine(payload, self.identity("enterprise"))

        self.assertEqual(export["mode"], "federated")
        self.assertEqual(export["structure"]["nodes"], ["apex", "execution", "policy"])
        self.assertEqual(export["structure"]["apex"], "apex")
        self.assertGreaterEqual(export["apexAlignment"]["score"], 0.5)
        self.assertLessEqual(export["apexAlignment"]["score"], 1)
        self.assertEqual(set(export["collapseVectors"]), {"authority", "coordination", "resilience"})

    def test_tier_escalation_and_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            export_identity_physics({"licenseTier": "enterprise"}, self.identity("professional"))
        with self.assertRaises(PermissionError):
            export_governance_engine({"licenseTier": "basic"}, {"attributes": {}})
        with self.assertRaises(ValueError):
            export_governance_engine({"licenseTier": "unknown"}, self.identity("enterprise"))
        with self.assertRaises(ValueError):
            export_governance_engine({"licenseTier": "basic", "input": []}, self.identity("enterprise"))

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
