"""Medical history statistics engine — incidence by body system."""
import pandas as pd
import numpy as np


def compute_medhist_summary(admh, adsl, group_var, audit, tfl_id,
                            soc_var="MHBODSYS", cat_var=None,
                            pop_filter=None, flags=None):
    """Compute % subjects with medical history conditions by body system.

    Args:
        admh: ADMH DataFrame
        adsl: ADSL DataFrame
        group_var: Treatment group variable
        soc_var: Body system variable in ADMH (default: MHBODSYS)
        cat_var: Optional category filter variable (e.g., MHCAT)
        flags: dict from get_adam_flags(); uses safety_pop key

    Returns:
        dict: {
            'any_mh': {trt: {n, pct, N}},
            'by_soc': {soc_name: {trt: {n, pct, N}}}
        }
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()
    treatments = sorted(safe_n.index)

    # Merge ADMH with safety population
    # Use treatment arm from ADMH if present, otherwise merge from ADSL
    if group_var in admh.columns:
        mh_merged = admh[admh["USUBJID"].isin(safe_pop["USUBJID"])]
    else:
        mh_merged = admh.merge(
            safe_pop[["USUBJID", group_var]].drop_duplicates(),
            on="USUBJID", how="inner"
        )

    # Optional category filter
    if cat_var and cat_var in mh_merged.columns:
        # Use all categories unless filtered by caller
        pass

    result = {"any_mh": {}, "by_soc": {}}

    # Any medical history condition
    any_mh = mh_merged.groupby(group_var)["USUBJID"].nunique()
    for trt in treatments:
        n = int(any_mh.get(trt, 0))
        N = int(safe_n.get(trt, 1))
        pct = round(100 * n / N, 1) if N > 0 else 0.0
        result["any_mh"][trt] = {"n": n, "N": N, "pct": pct}

    audit.log(tfl_id, "MH_any",
              f"admh.groupby('{group_var}')['USUBJID'].nunique() / safe_n",
              f"mh_records={len(mh_merged)}",
              result["any_mh"], variable="Any MH", population_filter=pop_filter)

    # By body system (SOC)
    if soc_var in mh_merged.columns:
        socs = sorted(mh_merged[soc_var].dropna().unique())
        for soc in socs:
            soc_data = mh_merged[mh_merged[soc_var] == soc]
            soc_counts = soc_data.groupby(group_var)["USUBJID"].nunique()
            result["by_soc"][soc] = {}
            for trt in treatments:
                n = int(soc_counts.get(trt, 0))
                N = int(safe_n.get(trt, 1))
                pct = round(100 * n / N, 1) if N > 0 else 0.0
                result["by_soc"][soc][trt] = {"n": n, "N": N, "pct": pct}

            audit.log(tfl_id, f"MH_SOC({soc[:30]})",
                      f"admh[{soc_var}=='{soc}'].groupby('{group_var}')['USUBJID'].nunique()",
                      f"soc_records={len(soc_data)}",
                      result["by_soc"][soc], variable=soc, population_filter=pop_filter)

    return result
