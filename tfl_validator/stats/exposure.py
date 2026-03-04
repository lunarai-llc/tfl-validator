"""Exposure statistics engine — treatment duration, dose, compliance."""
import pandas as pd
import numpy as np


def compute_exposure_summary(adsl, group_var, audit, tfl_id,
                             dur_var="TRTDURD", pop_filter=None, flags=None):
    """Compute treatment duration summary (mean, SD, median, min, max) per treatment arm.

    Uses ADSL.TRTDURD (treatment duration in days) as primary source.

    Args:
        adsl: ADSL DataFrame
        group_var: Treatment group variable
        dur_var: Variable name for treatment duration (default: TRTDURD)
        flags: dict from get_adam_flags(); uses safety_pop key

    Returns:
        dict: {trt: {n, mean, sd, median, min, max}}
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    result = {}
    for trt in treatments:
        trt_data = safe_pop[safe_pop[group_var] == trt][dur_var].dropna()
        n = len(trt_data)
        N = len(safe_pop[safe_pop[group_var] == trt])
        result[trt] = {
            "n": n, "N": N,
            "mean": round(float(trt_data.mean()), 1) if n > 0 else None,
            "sd": round(float(trt_data.std(ddof=1)), 2) if n > 1 else None,
            "median": round(float(trt_data.median()), 1) if n > 0 else None,
            "min": int(trt_data.min()) if n > 0 else None,
            "max": int(trt_data.max()) if n > 0 else None,
        }

    audit.log(tfl_id, "EXPOSURE_DURATION",
              f"adsl[{saf_var}=='{saf_val}'].groupby('{group_var}')['{dur_var}'].describe()",
              f"safety_subjects={len(safe_pop)}",
              result, variable=dur_var, population_filter=pop_filter)

    return result


def compute_exposure_categories(adsl, group_var, audit, tfl_id,
                                dur_var="TRTDURD",
                                categories=None, pop_filter=None, flags=None):
    """Compute % subjects in each exposure duration category per treatment arm.

    Args:
        categories: list of (label, min_days, max_days) tuples
                    e.g., [('< 12 weeks', 0, 83), ('12 to <24 weeks', 84, 167), ('>= 24 weeks', 168, 9999)]
    Returns:
        dict: {category_label: {trt: {n, pct}}}
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    if categories is None:
        categories = [
            ("< 12 weeks", 0, 83),
            ("12 to <24 weeks", 84, 167),
            (">= 24 weeks", 168, 9999),
        ]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()
    treatments = sorted(safe_n.index)

    result = {}
    for label, lo, hi in categories:
        cat_pop = safe_pop[(safe_pop[dur_var] >= lo) & (safe_pop[dur_var] <= hi)]
        result[label] = {}
        for trt in treatments:
            n = len(cat_pop[cat_pop[group_var] == trt])
            N = int(safe_n.get(trt, 1))
            pct = round(100 * n / N, 1) if N > 0 else 0.0
            result[label][trt] = {"n": n, "N": N, "pct": pct}

        audit.log(tfl_id, f"EXP_CAT({label})",
                  f"adsl[{dur_var} BETWEEN {lo} AND {hi}].groupby('{group_var}').count()",
                  f"cat_subjects={len(cat_pop)}",
                  result[label], variable=dur_var, population_filter=pop_filter)

    return result
