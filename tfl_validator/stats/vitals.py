"""Vital signs statistics engine — mean/SD by visit and treatment arm."""
import pandas as pd
import numpy as np


def compute_vitals_summary(advs, adsl, group_var, audit, tfl_id,
                           paramcds=None, visits=None,
                           pop_filter=None, flags=None):
    """Compute mean ± SD for vital signs parameters at specified visits.

    Args:
        advs: ADVS DataFrame
        adsl: ADSL DataFrame
        group_var: Treatment group variable
        paramcds: list of PARAMCD values; defaults to ['SYSBP', 'DIABP', 'PULSE']
        visits: list of AVISIT values to compute; defaults to ['Baseline', 'End of Treatment']
        flags: dict from get_adam_flags(); uses safety_pop key

    Returns:
        dict: {paramcd: {visit_label: {trt: {n, mean, sd, N}}}}
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    if paramcds is None:
        paramcds = ["SYSBP", "DIABP", "PULSE"]
    if visits is None:
        visits = ["Baseline", "End of Treatment"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()
    treatments = sorted(safe_n.index)

    result = {}
    for paramcd in paramcds:
        param_data = advs[advs["PARAMCD"] == paramcd]
        result[paramcd] = {}

        for visit_name in visits:
            visit_label = visit_name.lower().replace(" ", "_")
            visit_data = param_data[param_data["AVISIT"] == visit_name]

            # Use ABLFL for baseline, ANL01FL for others
            if visit_name.lower() == "baseline" and "ABLFL" in visit_data.columns:
                visit_data = visit_data[visit_data["ABLFL"] == "Y"]
            elif "ANL01FL" in visit_data.columns:
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

            audit.log(tfl_id, f"VS_{paramcd}_{visit_label}",
                      f"advs[PARAMCD=='{paramcd}' & AVISIT=='{visit_name}'].mean/sd",
                      f"visit_rows={len(visit_data)}",
                      {trt: result[paramcd][visit_label].get(trt) for trt in treatments},
                      variable=paramcd, population_filter=pop_filter)

    return result
