"""Deterministic SIM export products for Umbrella licensing lanes."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple


LICENSE_TIERS: Tuple[str, ...] = ("basic", "professional", "enterprise")

IDENTITY_PHYSICS_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("identitySignature",),
    "professional": ("identitySignature", "stabilityMetrics"),
    "enterprise": ("identitySignature", "stabilityMetrics", "curvatureVectors"),
}

GOVERNANCE_ENGINE_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("mode", "structure"),
    "professional": ("mode", "structure", "apexAlignment"),
    "enterprise": ("mode", "structure", "apexAlignment", "collapseVectors"),
}

APEX_ADVISORY_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("apexVector", "alignmentScore"),
    "professional": ("apexVector", "alignmentScore", "structuralAlignmentMap"),
    "enterprise": ("apexVector", "alignmentScore", "structuralAlignmentMap", "collapseVectorRisk"),
}

SIM_PACK_COMPOSITION: Mapping[str, Tuple[str, ...]] = {
    "basic": ("identitySim",),
    "professional": ("identitySim", "governanceSim", "apexSim"),
    "enterprise": ("identitySim", "governanceSim", "apexSim", "marketSim"),
}


@dataclass(frozen=True)
class LicenseGrant:
    requested: str
    authorized: str
    effective: str

    @property
    def capped(self) -> bool:
        return self.requested != self.effective


def resolve_license_tier(identity: Mapping[str, Any], payload: Mapping[str, Any]) -> LicenseGrant:
    """Cap the requested tier to the bearer identity's explicit entitlement."""
    attributes = identity.get("attributes")
    assigned = attributes.get("licenseTier") if isinstance(attributes, Mapping) else None
    if not isinstance(assigned, str) or assigned not in LICENSE_TIERS:
        raise PermissionError("bearer identity has no valid license tier")

    requested = payload.get("tier")
    if not isinstance(requested, str) or requested not in LICENSE_TIERS:
        raise ValueError(f"tier must be one of: {', '.join(LICENSE_TIERS)}")
    effective = LICENSE_TIERS[min(LICENSE_TIERS.index(requested), LICENSE_TIERS.index(assigned))]
    return LicenseGrant(requested=requested, authorized=assigned, effective=effective)


def export_identity_physics(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export identity-physics SIM outputs allowed by the resolved license tier."""
    model_input = _model_input(payload)
    digest = _digest("identity-physics", model_input)
    curvature = {
        "identity": _vector(digest, 0),
        "relational": _vector(digest, 6),
        "temporal": _vector(digest, 12),
    }
    flattened = [component for vector in curvature.values() for component in vector]
    mean = sum(flattened) / len(flattened)
    variance = sum((component - mean) ** 2 for component in flattened) / len(flattened)
    stability_score = round(max(0.0, min(1.0, 1.0 - variance * 0.7 - abs(mean) * 0.15)), 6)
    classification = "stable" if stability_score >= 0.8 else "balanced" if stability_score >= 0.6 else "volatile"
    outputs: Dict[str, Any] = {
        "identitySignature": f"idp_v1_{digest.hex()[:32]}",
        "stabilityMetrics": {
            "score": stability_score,
            "classification": classification,
            "curvatureVariance": round(variance, 6),
        },
        "curvatureVectors": curvature,
    }
    return _licensed_payload(
        "identity-physics",
        grant,
        IDENTITY_PHYSICS_OUTPUTS[grant.effective],
        outputs,
    )


def export_governance_engine(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export governance-structure SIM outputs allowed by the resolved license tier."""
    model_input = _model_input(payload)
    digest = _digest("governance-engine", model_input)
    mode = model_input.get("mode", "umbrella")
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("governance mode must be a non-empty string")
    structure = _governance_structure(model_input)
    apex_score = round(0.5 + int.from_bytes(digest[:2], "big") / 131070, 6)
    outputs: Dict[str, Any] = {
        "mode": mode.strip(),
        "structure": structure,
        "apexAlignment": {
            "score": apex_score,
            "classification": "aligned" if apex_score >= 0.75 else "partial",
        },
        "collapseVectors": {
            "authority": _vector(digest, 2),
            "coordination": _vector(digest, 8),
            "resilience": _vector(digest, 14),
        },
    }
    return _licensed_payload(
        "governance-engine",
        grant,
        GOVERNANCE_ENGINE_OUTPUTS[grant.effective],
        outputs,
    )


def export_apex_alignment(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export deterministic apex-alignment advice filtered by effective tier."""
    model_input = _model_input(payload)
    digest = _digest("apex-alignment", model_input)
    apex_vector = _vector(digest, 0)
    alignment_score = round(0.5 + int.from_bytes(digest[3:5], "big") / 131070, 6)
    structure = _governance_structure(model_input)
    structural_map = {
        "apex": structure["apex"],
        "nodes": [
            {
                "id": node,
                "alignment": round(0.4 + digest[(8 + index) % len(digest)] / 425, 6),
            }
            for index, node in enumerate(structure["nodes"])
        ],
    }
    collapse_vector = _vector(digest, 16)
    collapse_risk = round(max(0.0, min(1.0, 1.0 - alignment_score * 0.75 + _magnitude(collapse_vector) * 0.25)), 6)
    outputs: Dict[str, Any] = {
        "apexVector": apex_vector,
        "alignmentScore": alignment_score,
        "structuralAlignmentMap": structural_map,
        "collapseVectorRisk": {
            "score": collapse_risk,
            "classification": "high" if collapse_risk >= 0.65 else "moderate" if collapse_risk >= 0.35 else "low",
            "vector": collapse_vector,
        },
    }
    return _licensed_payload(
        "apex-alignment-advisory",
        grant,
        APEX_ADVISORY_OUTPUTS[grant.effective],
        outputs,
    )


def export_sim_pack(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Bundle deterministic SIM products according to the effective license tier."""
    model_input = _model_input(payload)
    digest = _digest(f"umbrella-sim-pack:{grant.effective}", model_input)
    composition = SIM_PACK_COMPOSITION[grant.effective]
    simulations: Dict[str, Any] = {}
    if "identitySim" in composition:
        simulations["identitySim"] = export_identity_physics(payload, grant)
    if "governanceSim" in composition:
        simulations["governanceSim"] = export_governance_engine(payload, grant)
    if "apexSim" in composition:
        simulations["apexSim"] = export_apex_alignment(payload, grant)
    if "marketSim" in composition:
        simulations["marketSim"] = _market_sim(model_input)

    stability_score = round(0.55 + int.from_bytes(digest[:2], "big") / 145634, 6)
    outputs: Dict[str, Any] = {
        "version": "sim-pack-v1",
        "composition": list(composition),
        "stability": {
            "score": stability_score,
            "classification": "stable" if stability_score >= 0.8 else "balanced",
        },
        "deterministicSeed": f"pack_v1_{digest.hex()[:32]}",
        "simulations": simulations,
    }
    return _licensed_payload(
        "umbrella-sim-pack",
        grant,
        ("version", "composition", "stability", "deterministicSeed", "simulations"),
        outputs,
        export_mode="sim-pack",
    )


def _licensed_payload(
    product: str,
    grant: LicenseGrant,
    allowed_outputs: Sequence[str],
    outputs: Mapping[str, Any],
    export_mode: str = "sim",
) -> Dict[str, Any]:
    response = {
        "product": product,
        "exportMode": export_mode,
        "tier": grant.effective,
        "requestedTier": grant.requested,
        "authorizedTier": grant.authorized,
        "tierCapped": grant.capped,
        "allowedOutputs": list(allowed_outputs),
    }
    response.update({name: outputs[name] for name in allowed_outputs})
    return response


def _model_input(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if "input" in payload:
        model_input = payload["input"]
        if not isinstance(model_input, Mapping):
            raise ValueError("license input must be an object")
        return dict(model_input)
    return {str(key): value for key, value in payload.items() if key != "tier"}


def _digest(product: str, model_input: Mapping[str, Any]) -> bytes:
    encoded = json.dumps(
        {"product": product, "input": model_input},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).digest()


def _vector(digest: bytes, offset: int) -> list[float]:
    return [round((digest[(offset + index) % len(digest)] - 127.5) / 127.5, 6) for index in range(3)]


def _magnitude(vector: Sequence[float]) -> float:
    return sum(abs(component) for component in vector) / len(vector)


def _market_sim(model_input: Mapping[str, Any]) -> Dict[str, Any]:
    digest = _digest("market-sim", model_input)
    return {
        "marketVector": _vector(digest, 0),
        "demandIndex": round(int.from_bytes(digest[6:8], "big") / 65535, 6),
        "resilienceScore": round(int.from_bytes(digest[10:12], "big") / 65535, 6),
    }


def _governance_structure(model_input: Mapping[str, Any]) -> Dict[str, Any]:
    requested_nodes = model_input.get("nodes", ("apex", "policy", "execution"))
    if not isinstance(requested_nodes, (list, tuple)) or not all(
        isinstance(node, str) and node.strip() for node in requested_nodes
    ):
        raise ValueError("governance nodes must be a list of non-empty strings")
    nodes = sorted(set(node.strip() for node in requested_nodes))
    if not nodes:
        raise ValueError("governance nodes cannot be empty")
    return {
        "nodes": nodes,
        "layers": len(nodes),
        "apex": "apex" if "apex" in nodes else nodes[0],
    }
