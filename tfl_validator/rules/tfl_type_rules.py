"""
TFL Type Rules Engine
=====================
Defines which TFLs require Protocol and/or SAP reference documents,
and auto-classifies TFLs into categories based on their ID and title.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional


class TFLCategory(Enum):
    """TFL classification categories."""
    DEMOGRAPHICS = "demographics"
    DISPOSITION = "disposition"
    SAFETY_AE = "safety_ae"
    SAFETY_AE_GRADE = "safety_ae_grade"
    EFFICACY = "efficacy"
    SURVIVAL = "survival"
    SUBGROUP = "subgroup"
    LAB = "lab"
    VITAL_SIGNS = "vital_signs"
    EXPOSURE = "exposure"
    CONMED = "conmed"
    MEDICAL_HISTORY = "medical_history"
    LISTING = "listing"
    UNKNOWN = "unknown"


@dataclass
class ReferenceRequirement:
    """Specifies which reference documents are needed for a TFL category."""
    category: TFLCategory
    requires_protocol: bool = False
    requires_sap: bool = False
    protocol_sections: List[str] = field(default_factory=list)
    sap_sections: List[str] = field(default_factory=list)
    protocol_metadata_needed: List[str] = field(default_factory=list)
    sap_metadata_needed: List[str] = field(default_factory=list)
    description: str = ""


# ── Reference Requirement Rules ──────────────────────────────────────────────

TFL_REFERENCE_RULES = {
    TFLCategory.DEMOGRAPHICS: ReferenceRequirement(
        category=TFLCategory.DEMOGRAPHICS,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms", "Study Population"],
        protocol_metadata_needed=["arms", "populations"],
        description="Demographics tables need Protocol arm and population definitions",
    ),

    TFLCategory.DISPOSITION: ReferenceRequirement(
        category=TFLCategory.DISPOSITION,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Population", "Study Design"],
        protocol_metadata_needed=["populations"],
        description="Disposition tables need Protocol population definitions",
    ),

    TFLCategory.SAFETY_AE: ReferenceRequirement(
        category=TFLCategory.SAFETY_AE,
        requires_protocol=True,
        requires_sap=True,
        protocol_sections=["Study Arms", "Safety Endpoints"],
        sap_sections=["Safety Analysis"],
        protocol_metadata_needed=["arms", "populations", "safety_endpoints"],
        sap_metadata_needed=["analysis_populations"],
        description="AE tables need Protocol arm/safety definitions + SAP safety analysis plan",
    ),

    TFLCategory.SAFETY_AE_GRADE: ReferenceRequirement(
        category=TFLCategory.SAFETY_AE_GRADE,
        requires_protocol=True,
        requires_sap=True,
        protocol_sections=["Study Arms", "Safety Endpoints"],
        sap_sections=["Safety Analysis"],
        protocol_metadata_needed=["arms", "populations"],
        sap_metadata_needed=["analysis_populations"],
        description="AE grade tables need same as AE summary",
    ),

    TFLCategory.EFFICACY: ReferenceRequirement(
        category=TFLCategory.EFFICACY,
        requires_protocol=True,
        requires_sap=True,
        protocol_sections=["Primary Endpoint", "Secondary Endpoint", "Estimands"],
        sap_sections=["Statistical Methods", "Primary Analysis", "Multiplicity"],
        protocol_metadata_needed=["arms", "populations", "primary_endpoints", "secondary_endpoints"],
        sap_metadata_needed=["statistical_methods", "primary_analyses", "multiplicity_adjustments"],
        description="Efficacy tables need Protocol endpoints + SAP statistical methodology",
    ),

    TFLCategory.SURVIVAL: ReferenceRequirement(
        category=TFLCategory.SURVIVAL,
        requires_protocol=True,
        requires_sap=True,
        protocol_sections=["Primary Endpoint", "Study Design"],
        sap_sections=["Statistical Methods", "Survival Analysis"],
        protocol_metadata_needed=["arms", "populations", "primary_endpoints"],
        sap_metadata_needed=["statistical_methods"],
        description="Survival tables need Protocol endpoints + SAP KM/Cox specifications",
    ),

    TFLCategory.SUBGROUP: ReferenceRequirement(
        category=TFLCategory.SUBGROUP,
        requires_protocol=True,
        requires_sap=True,
        protocol_sections=["Primary Endpoint"],
        sap_sections=["Subgroup Analyses", "Statistical Methods"],
        protocol_metadata_needed=["arms", "primary_endpoints"],
        sap_metadata_needed=["statistical_methods", "subgroup_analyses"],
        description="Subgroup tables need Protocol endpoints + SAP subgroup specs",
    ),

    TFLCategory.LAB: ReferenceRequirement(
        category=TFLCategory.LAB,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms"],
        protocol_metadata_needed=["arms", "populations"],
        description="Lab tables need Protocol arm definitions for grouping",
    ),

    TFLCategory.VITAL_SIGNS: ReferenceRequirement(
        category=TFLCategory.VITAL_SIGNS,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms"],
        protocol_metadata_needed=["arms", "populations"],
        description="Vital signs tables need Protocol arm definitions",
    ),

    TFLCategory.EXPOSURE: ReferenceRequirement(
        category=TFLCategory.EXPOSURE,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms", "Dosage and Administration"],
        protocol_metadata_needed=["arms"],
        description="Exposure tables need Protocol treatment/dosage definitions",
    ),

    TFLCategory.CONMED: ReferenceRequirement(
        category=TFLCategory.CONMED,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms"],
        protocol_metadata_needed=["arms", "populations"],
        description="Conmed tables need Protocol arm definitions",
    ),

    TFLCategory.MEDICAL_HISTORY: ReferenceRequirement(
        category=TFLCategory.MEDICAL_HISTORY,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms"],
        protocol_metadata_needed=["arms", "populations"],
        description="Medical history tables need Protocol arm definitions",
    ),

    TFLCategory.LISTING: ReferenceRequirement(
        category=TFLCategory.LISTING,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms", "Study Population"],
        protocol_metadata_needed=["arms", "populations"],
        description="Listings need Protocol arm and population definitions for context",
    ),

    TFLCategory.UNKNOWN: ReferenceRequirement(
        category=TFLCategory.UNKNOWN,
        requires_protocol=True,
        requires_sap=False,
        protocol_sections=["Study Arms"],
        protocol_metadata_needed=["arms"],
        description="Unknown TFL types get basic Protocol arm validation",
    ),
}


# ── Classification Functions ─────────────────────────────────────────────────

# Keywords for auto-classification (checked in order, first match wins)
_CLASSIFICATION_RULES = [
    # Listings first (L-prefix or "listing" in title)
    (TFLCategory.LISTING, lambda tid, t: tid.upper().startswith("L-") or "listing" in t.lower()),

    # Survival
    (TFLCategory.SURVIVAL, lambda tid, t: any(w in t.lower() for w in
     ["survival", "kaplan", "time-to-event", "time to event", "pfs", "os ", "efs", "dfs",
      "progression-free", "overall survival", "event-free"])),

    # Subgroup
    (TFLCategory.SUBGROUP, lambda tid, t: any(w in t.lower() for w in
     ["subgroup", "sub-group", "forest plot", "forest_plot"])),

    # Efficacy (must come after survival/subgroup)
    (TFLCategory.EFFICACY, lambda tid, t: any(w in t.lower() for w in
     ["efficacy", "primary endpoint", "secondary endpoint", "tumor response",
      "tumor change", "objective response", "orr", "best overall", "waterfall"])),

    # Safety AE grade
    (TFLCategory.SAFETY_AE_GRADE, lambda tid, t: any(w in t.lower() for w in
     ["ae by grade", "adverse event.*grade", "toxicity grade", "ctcae"])),

    # Safety AE (broader)
    (TFLCategory.SAFETY_AE, lambda tid, t: any(w in t.lower() for w in
     ["adverse event", "teae", "sae", "serious adverse", "treatment-emergent",
      "ae summary", "ae overview", "safety summary"])),

    # Lab
    (TFLCategory.LAB, lambda tid, t: any(w in t.lower() for w in
     ["laboratory", "lab shift", "lab summary", "hematology", "chemistry",
      "liver function", "renal function", "lab toxicity"])),

    # Vital signs
    (TFLCategory.VITAL_SIGNS, lambda tid, t: any(w in t.lower() for w in
     ["vital sign", "blood pressure", "pulse", "temperature", "weight", "bmi",
      "ecg", "electrocardiogram"])),

    # Exposure
    (TFLCategory.EXPOSURE, lambda tid, t: any(w in t.lower() for w in
     ["exposure", "drug exposure", "dose modification", "dose reduction",
      "dose intensity", "treatment duration", "cycle"])),

    # Conmed
    (TFLCategory.CONMED, lambda tid, t: any(w in t.lower() for w in
     ["concomitant", "conmed", "prior medication", "prior therapy",
      "subsequent therapy", "subsequent treatment"])),

    # Medical history
    (TFLCategory.MEDICAL_HISTORY, lambda tid, t: any(w in t.lower() for w in
     ["medical history", "past medical", "baseline disease"])),

    # Disposition
    (TFLCategory.DISPOSITION, lambda tid, t: any(w in t.lower() for w in
     ["disposition", "subject status", "patient flow", "completion",
      "discontinuation", "withdrawal"])),

    # Demographics (last among tables, as it's a common fallback)
    (TFLCategory.DEMOGRAPHICS, lambda tid, t: any(w in t.lower() for w in
     ["demographic", "baseline", "background", "characteristics"])),
]


def classify_tfl(tfl_id: str, tfl_title: str) -> TFLCategory:
    """
    Auto-classify a TFL into a category based on its ID and title.

    Args:
        tfl_id: TFL identifier (e.g., "T-01", "L-03")
        tfl_title: TFL display title

    Returns:
        TFLCategory enum value
    """
    for category, rule_fn in _CLASSIFICATION_RULES:
        try:
            if rule_fn(tfl_id, tfl_title):
                return category
        except Exception:
            continue

    return TFLCategory.UNKNOWN


def get_reference_requirements(category: TFLCategory) -> ReferenceRequirement:
    """
    Get the reference document requirements for a TFL category.

    Args:
        category: TFLCategory enum value

    Returns:
        ReferenceRequirement specifying what's needed
    """
    return TFL_REFERENCE_RULES.get(category, TFL_REFERENCE_RULES[TFLCategory.UNKNOWN])


def get_tfl_requirements(tfl_id: str, tfl_title: str) -> ReferenceRequirement:
    """
    Convenience function: classify TFL and return its requirements in one call.
    """
    category = classify_tfl(tfl_id, tfl_title)
    return get_reference_requirements(category)


def needs_protocol(tfl_id: str, tfl_title: str) -> bool:
    """Check if a TFL needs Protocol cross-validation."""
    return get_tfl_requirements(tfl_id, tfl_title).requires_protocol


def needs_sap(tfl_id: str, tfl_title: str) -> bool:
    """Check if a TFL needs SAP cross-validation."""
    return get_tfl_requirements(tfl_id, tfl_title).requires_sap


def get_classification_summary(tfl_configs: list) -> dict:
    """
    Classify all TFLs and return a summary.
    Useful for reporting/portal display.

    Args:
        tfl_configs: List of TFL config dicts

    Returns:
        Dict with classification counts and details
    """
    summary = {
        "total": len(tfl_configs),
        "needs_protocol": 0,
        "needs_sap": 0,
        "by_category": {},
        "details": [],
    }

    for cfg in tfl_configs:
        tfl_id = cfg.get("tfl_id", "")
        title = cfg.get("title", "")
        category = classify_tfl(tfl_id, title)
        reqs = get_reference_requirements(category)

        cat_name = category.value
        summary["by_category"][cat_name] = summary["by_category"].get(cat_name, 0) + 1

        if reqs.requires_protocol:
            summary["needs_protocol"] += 1
        if reqs.requires_sap:
            summary["needs_sap"] += 1

        summary["details"].append({
            "tfl_id": tfl_id,
            "title": title,
            "category": cat_name,
            "requires_protocol": reqs.requires_protocol,
            "requires_sap": reqs.requires_sap,
        })

    return summary
