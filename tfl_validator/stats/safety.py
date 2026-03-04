"""Safety statistics engine — AE incidence, SOC/PT counts, lab shift tables."""
import pandas as pd
import numpy as np


def compute_ae_overview(adae, adsl, group_var, audit, tfl_id, pop_filter=None, flags=None):
    """Overall AE summary: subjects with any AE, any SAE, any related AE per treatment.

    Args:
        adae: ADAE DataFrame (already filtered to TEAE if needed)
        adsl: ADSL DataFrame (full)
        group_var: Treatment group variable name
        audit: AuditLogger instance
        tfl_id: TFL identifier
        pop_filter: Population filter string for logging
        flags: dict from get_adam_flags() with ADaM variable overrides
    """
    if flags is None:
        flags = {
            "safety_pop":   {"var": "SAFFL", "value": "Y"},
            "serious_ae":   {"var": "AESER", "value": "Y"},
            "related_ae":   {"var": "AEREL", "value": ["RELATED", "POSSIBLY RELATED"]},
        }

    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]
    ser_var = flags["serious_ae"]["var"]
    ser_val = flags["serious_ae"]["value"]
    rel_var = flags["related_ae"]["var"]
    rel_val = flags["related_ae"]["value"]

    safe_n = adsl[adsl[saf_var] == saf_val].groupby(group_var)["USUBJID"].nunique()
    te_ae = adae  # caller should pass pre-filtered TEAE

    result = {}
    # Any TEAE
    any_ae = te_ae.groupby(group_var)["USUBJID"].nunique()
    result["any_teae"] = {}
    for trt in safe_n.index:
        n = int(any_ae.get(trt, 0))
        denom = int(safe_n[trt])
        pct = round(100 * n / denom, 1) if denom > 0 else 0.0
        result["any_teae"][trt] = {"n": n, "N": denom, "pct": pct}
    audit.log(tfl_id, "AE_overview(Any TEAE)",
              "te_ae.groupby(group_var)['USUBJID'].nunique() / safe_n",
              f"total_AE_records={len(te_ae)}", result["any_teae"],
              variable="Any TEAE", population_filter=pop_filter)

    # Any SAE
    sae = te_ae[te_ae[ser_var] == ser_val]
    any_sae = sae.groupby(group_var)["USUBJID"].nunique()
    result["any_sae"] = {}
    for trt in safe_n.index:
        n = int(any_sae.get(trt, 0))
        denom = int(safe_n[trt])
        pct = round(100 * n / denom, 1) if denom > 0 else 0.0
        result["any_sae"][trt] = {"n": n, "N": denom, "pct": pct}
    audit.log(tfl_id, "AE_overview(Any SAE)",
              "sae_ae.groupby(group_var)['USUBJID'].nunique() / safe_n",
              f"total_SAE_records={len(sae)}", result["any_sae"],
              variable="Any SAE", population_filter=pop_filter)

    # Any related AE
    if isinstance(rel_val, list):
        rel = te_ae[te_ae[rel_var].isin(rel_val)]
    else:
        rel = te_ae[te_ae[rel_var] == rel_val]
    any_rel = rel.groupby(group_var)["USUBJID"].nunique()
    result["any_related"] = {}
    for trt in safe_n.index:
        n = int(any_rel.get(trt, 0))
        denom = int(safe_n[trt])
        pct = round(100 * n / denom, 1) if denom > 0 else 0.0
        result["any_related"][trt] = {"n": n, "N": denom, "pct": pct}
    audit.log(tfl_id, "AE_overview(Any Related)",
              "related_ae.groupby(group_var)['USUBJID'].nunique() / safe_n",
              f"total_related_records={len(rel)}", result["any_related"],
              variable="Any Drug-related AE", population_filter=pop_filter)

    return result


def compute_ae_by_soc_pt(adae, adsl, group_var, audit, tfl_id, pop_filter=None,
                          soc_var="AEBODSYS", pt_var="AEDECOD"):
    """AE incidence by SOC and PT: n (%) subjects per treatment arm.

    Args:
        soc_var: SOC variable name (default: AEBODSYS)
        pt_var: PT variable name (default: AEDECOD)
    """
    safe_n = adsl[adsl["SAFFL"] == "Y"].groupby(group_var)["USUBJID"].nunique()
    te_ae = adae  # caller passes pre-filtered TEAE

    result = {}
    socs = sorted(te_ae[soc_var].unique())

    for soc in socs:
        soc_data = te_ae[te_ae[soc_var] == soc]
        # SOC level
        soc_counts = soc_data.groupby(group_var)["USUBJID"].nunique()
        soc_result = {}
        for trt in safe_n.index:
            n = int(soc_counts.get(trt, 0))
            denom = int(safe_n[trt])
            pct = round(100 * n / denom, 1) if denom > 0 else 0.0
            soc_result[trt] = {"n": n, "N": denom, "pct": pct}

        audit.log(tfl_id, f"AE_SOC({soc[:30]})",
                  f"ae[ae.{soc_var}=='{soc}'].groupby('{group_var}')['USUBJID'].nunique()",
                  f"soc_records={len(soc_data)}", soc_result,
                  variable=soc, population_filter=pop_filter)

        # PT level under this SOC
        pts = sorted(soc_data[pt_var].unique())
        pt_results = {}
        for pt in pts:
            pt_data = soc_data[soc_data[pt_var] == pt]
            pt_counts = pt_data.groupby(group_var)["USUBJID"].nunique()
            pt_result = {}
            for trt in safe_n.index:
                n = int(pt_counts.get(trt, 0))
                denom = int(safe_n[trt])
                pct = round(100 * n / denom, 1) if denom > 0 else 0.0
                pt_result[trt] = {"n": n, "N": denom, "pct": pct}
            pt_results[pt] = pt_result

            audit.log(tfl_id, f"AE_PT({pt})",
                      f"ae[ae.{pt_var}=='{pt}'].groupby('{group_var}')['USUBJID'].nunique()",
                      f"pt_records={len(pt_data)}", pt_result,
                      variable=pt, population_filter=pop_filter)

        result[soc] = {"soc_total": soc_result, "pts": pt_results}

    return result
