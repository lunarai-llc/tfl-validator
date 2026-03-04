"""Lab statistics engine — mean/SD, shift tables, range checks."""
import pandas as pd
import numpy as np


def compute_lab_summary(adlb, adsl, group_var, audit, tfl_id,
                        paramcds=None, visit_baseline="Baseline", visit_post="Week 26",
                        pop_filter=None, flags=None):
    """Compute mean ± SD at baseline and post-baseline visit for selected lab parameters.

    Args:
        adlb: ADLB DataFrame (full)
        adsl: ADSL DataFrame
        group_var: Treatment group variable
        paramcds: list of PARAMCD values to compute; if None uses defaults
        visit_baseline: AVISIT value for baseline
        visit_post: AVISIT value for post-baseline comparison
        flags: dict from get_adam_flags(); uses safety_pop key

    Returns:
        dict: {paramcd: {visit: {trt: {mean, sd, n, N}}}}
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    if paramcds is None:
        paramcds = ["ALT", "AST", "CHOLES", "CREAT", "BUN"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()
    treatments = sorted(safe_n.index)

    result = {}
    for paramcd in paramcds:
        param_data = adlb[adlb["PARAMCD"] == paramcd]
        result[paramcd] = {}

        for visit_label, visit_name in [("baseline", visit_baseline), ("postbaseline", visit_post)]:
            visit_data = param_data[param_data["AVISIT"] == visit_name]
            # Use ABLFL for baseline, ANL01FL for post-baseline
            if visit_label == "baseline" and "ABLFL" in visit_data.columns:
                visit_data = visit_data[visit_data["ABLFL"] == "Y"]
            elif visit_label == "postbaseline" and "ANL01FL" in visit_data.columns:
                visit_data = visit_data[visit_data["ANL01FL"] == "Y"]

            result[paramcd][visit_label] = {}
            for trt in treatments:
                trt_data = visit_data[visit_data[group_var] == trt]["AVAL"].dropna()
                n = len(trt_data)
                mean_val = round(float(trt_data.mean()), 1) if n > 0 else None
                sd_val = round(float(trt_data.std(ddof=1)), 2) if n > 1 else None
                N = int(safe_n[trt])
                result[paramcd][visit_label][trt] = {
                    "n": n, "N": N, "mean": mean_val, "sd": sd_val
                }

            audit.log(tfl_id, f"LAB_{paramcd}_{visit_label}",
                      f"adlb[PARAMCD=='{paramcd}' & AVISIT=='{visit_name}'].mean/sd",
                      f"visit_rows={len(visit_data)}",
                      {trt: result[paramcd][visit_label].get(trt) for trt in treatments},
                      variable=paramcd, population_filter=pop_filter)

    return result


def compute_lab_shift(adlb, adsl, group_var, audit, tfl_id,
                      paramcds=None, pop_filter=None, flags=None):
    """Compute shift tables (Normal→Abnormal etc.) for selected lab parameters.

    Returns:
        dict: {paramcd: {trt: {shift_label: count}}}
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    if paramcds is None:
        paramcds = ["ALT", "AST", "CHOLES"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    result = {}
    for paramcd in paramcds:
        param_data = adlb[adlb["PARAMCD"] == paramcd]

        # Use SHIFT1 column if available (e.g., "Low", "Normal", "High")
        if "SHIFT1" not in param_data.columns or "BNRIND" not in param_data.columns:
            continue

        # Post-baseline with ANL01FL
        post = param_data[(param_data.get("ANL01FL", pd.Series(dtype=str)) == "Y")
                          if "ANL01FL" in param_data.columns
                          else param_data["AVISIT"] != "Baseline"]
        post = param_data[param_data.get("ABLFL", pd.Series(dtype=str)) != "Y"]

        result[paramcd] = {}
        for trt in treatments:
            trt_post = post[post[group_var] == trt]
            shifts = trt_post["SHIFT1"].value_counts().to_dict() if "SHIFT1" in trt_post.columns else {}
            result[paramcd][trt] = shifts

        audit.log(tfl_id, f"LAB_SHIFT_{paramcd}",
                  f"adlb[PARAMCD=='{paramcd}'].SHIFT1.value_counts()",
                  f"post_baseline_rows={len(post)}",
                  result[paramcd], variable=paramcd, population_filter=pop_filter)

    return result
