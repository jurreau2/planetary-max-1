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

MARKET_FORECAST_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("marketVector", "trendProjection"),
    "professional": ("marketVector", "trendProjection", "volatilityBand"),
    "enterprise": ("marketVector", "trendProjection", "volatilityBand", "collapseVectorRisk"),
}

IDENTITY_MIRROR_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("identitySignature",),
    "professional": ("identitySignature", "behavioralProjection", "structuralTruthMap"),
    "enterprise": ("identitySignature", "behavioralProjection", "structuralTruthMap", "quantumBranchPreview"),
}

CROSSWORLD_ACCESS_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("accessSignature", "reachableWorlds"),
    "professional": ("accessSignature", "reachableWorlds", "traversalMap"),
    "enterprise": ("accessSignature", "reachableWorlds", "traversalMap", "quantumBridge"),
}

STRUCTURAL_TRUTH_OUTPUTS: Mapping[str, Tuple[str, ...]] = {
    "basic": ("truthSignature", "coherence"),
    "professional": ("truthSignature", "coherence", "structuralTruthMap"),
    "enterprise": ("truthSignature", "coherence", "structuralTruthMap", "contradictionVectors"),
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


def export_market_forecast(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export deterministic market forecasts filtered by effective tier."""
    model_input = _model_input(payload)
    digest = _digest("umbrella-market-forecast", model_input)
    market_vector = _vector(digest, 0)
    baseline = int.from_bytes(digest[6:8], "big") / 65535
    trend = (digest[8] - 127.5) / 127.5
    trend_projection = [
        {
            "horizon": horizon,
            "index": round(max(0.0, min(1.0, baseline + trend * horizon / 24)), 6),
        }
        for horizon in (1, 3, 6)
    ]
    volatility = round(0.05 + int.from_bytes(digest[10:12], "big") / 72817, 6)
    volatility = min(volatility, 0.95)
    collapse_vector = _vector(digest, 16)
    collapse_risk = round(max(0.0, min(1.0, volatility * 0.7 + _magnitude(collapse_vector) * 0.3)), 6)
    outputs: Dict[str, Any] = {
        "marketVector": market_vector,
        "trendProjection": trend_projection,
        "volatilityBand": {
            "low": round(max(0.0, baseline - volatility / 2), 6),
            "mid": round(baseline, 6),
            "high": round(min(1.0, baseline + volatility / 2), 6),
        },
        "collapseVectorRisk": {
            "score": collapse_risk,
            "classification": "high" if collapse_risk >= 0.65 else "moderate" if collapse_risk >= 0.35 else "low",
            "vector": collapse_vector,
        },
    }
    return _licensed_payload(
        "umbrella-market-forecast",
        grant,
        MARKET_FORECAST_OUTPUTS[grant.effective],
        outputs,
        export_mode="market-forecast",
    )


def export_identity_mirror(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export a deterministic identity mirror filtered by effective tier."""
    model_input = _model_input(payload)
    digest = _digest("umbrella-identity-mirror", model_input)
    behavioral_projection = [
        {
            "phase": phase,
            "vector": _vector(digest, 3 + index * 3),
            "confidence": round(0.5 + digest[20 + index] / 510, 6),
        }
        for index, phase in enumerate(("near", "mid", "far"))
    ]
    outputs: Dict[str, Any] = {
        "identitySignature": f"mirror_v1_{digest.hex()[:32]}",
        "behavioralProjection": behavioral_projection,
        "structuralTruthMap": _structural_truth_map(model_input, digest),
        "quantumBranchPreview": _quantum_branches(digest),
    }
    return _licensed_payload(
        "umbrella-identity-mirror",
        grant,
        IDENTITY_MIRROR_OUTPUTS[grant.effective],
        outputs,
        export_mode="identity-mirror",
    )


def export_crossworld_access(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export deterministic cross-world access data filtered by effective tier."""
    model_input = _model_input(payload)
    digest = _digest("umbrella-crossworld-access", model_input)
    requested_worlds = model_input.get("worlds", ("origin", "adjacent", "frontier"))
    if not isinstance(requested_worlds, (list, tuple)) or not all(
        isinstance(world, str) and world.strip() for world in requested_worlds
    ):
        raise ValueError("crossworld worlds must be a list of non-empty strings")
    worlds = sorted(set(world.strip() for world in requested_worlds))
    if not worlds:
        raise ValueError("crossworld worlds cannot be empty")
    requested_origin = model_input.get("origin", "origin" if "origin" in worlds else worlds[0])
    if not isinstance(requested_origin, str) or requested_origin.strip() not in worlds:
        raise ValueError("crossworld origin must name a requested world")
    origin = requested_origin.strip()

    reachable_worlds = [
        {
            "world": world,
            "accessScore": round(0.5 + digest[index % len(digest)] / 510, 6),
        }
        for index, world in enumerate(worlds)
    ]
    outputs: Dict[str, Any] = {
        "accessSignature": f"crossworld_v1_{digest.hex()[:32]}",
        "reachableWorlds": reachable_worlds,
        "traversalMap": {
            "origin": origin,
            "routes": [
                {
                    "from": origin,
                    "to": world,
                    "stability": round(0.55 + digest[(8 + index) % len(digest)] / 567, 6),
                }
                for index, world in enumerate(worlds)
                if world != origin
            ],
        },
        "quantumBridge": {
            "vector": _vector(digest, 16),
            "coherence": round(0.5 + digest[22] / 510, 6),
            "branchPreview": _quantum_branches(digest),
        },
    }
    return _licensed_payload(
        "umbrella-crossworld-access",
        grant,
        CROSSWORLD_ACCESS_OUTPUTS[grant.effective],
        outputs,
        export_mode="crossworld-access",
    )


def export_structural_truth(payload: Mapping[str, Any], grant: LicenseGrant) -> Dict[str, Any]:
    """Export deterministic structural-truth evidence filtered by effective tier."""
    model_input = _model_input(payload)
    digest = _digest("structural-truth-license", model_input)
    truth_map = _structural_truth_map(model_input, digest)
    contradiction_vectors = {
        "identity": _vector(digest, 0),
        "behavior": _vector(digest, 8),
        "structure": _vector(digest, 16),
    }
    outputs: Dict[str, Any] = {
        "truthSignature": f"truth_v1_{digest.hex()[:32]}",
        "coherence": truth_map["coherence"],
        "structuralTruthMap": truth_map,
        "contradictionVectors": contradiction_vectors,
    }
    return _licensed_payload(
        "structural-truth",
        grant,
        STRUCTURAL_TRUTH_OUTPUTS[grant.effective],
        outputs,
        export_mode="structural-truth",
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


def _structural_truth_map(model_input: Mapping[str, Any], digest: bytes) -> Dict[str, Any]:
    requested_facets = model_input.get("facets", ("identity", "behavior", "structure"))
    if not isinstance(requested_facets, (list, tuple)) or not all(
        isinstance(facet, str) and facet.strip() for facet in requested_facets
    ):
        raise ValueError("identity facets must be a list of non-empty strings")
    facets = sorted(set(facet.strip() for facet in requested_facets))
    if not facets:
        raise ValueError("identity facets cannot be empty")
    return {
        "facets": [
            {
                "name": facet,
                "truthScore": round(0.5 + digest[(24 + index) % len(digest)] / 510, 6),
            }
            for index, facet in enumerate(facets)
        ],
        "coherence": round(0.5 + digest[27] / 510, 6),
    }


def _quantum_branches(digest: bytes) -> list[Dict[str, Any]]:
    weights = [digest[28] + 1, digest[29] + 1, digest[30] + 1]
    total = sum(weights)
    return [
        {
            "branch": f"q{index + 1}",
            "probability": round(weight / total, 6),
            "vector": _vector(digest, index * 5),
        }
        for index, weight in enumerate(weights)
    ]


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
