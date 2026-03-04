"""Concomitant medications statistics engine — incidence by ATC class."""
import pandas as pd
import numpy as np


def compute_conmeds_summary(adcm, adsl, group_var, audit, tfl_id,
                            class_var="CMCLAS", ontrt_flag="ONTRTFL",
                            pop_filter=None, flags=None):
    """Compute % subjects taking concomitant medications, overall and by ATC class.

    Args:
        adcm: ADCM DataFrame
        adsl: ADSL DataFrame
        group_var: Treatment group variable
        class_var: ATC class variable in ADCM (default: CMCLAS)
        ontrt_flag: On-treatment flag in ADCM (default: ONTRTFL)
        flags: dict from get_adam_flags(); uses safety_pop key

    Returns:
        dict: {
            'any_conmed': {trt: {n, pct, N}},
            'by_class': {class_name: {trt: {n, pct, N}}}
        }
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()
    treatments = sorted(safe_n.index)

    # Filter to on-treatment conmeds (if flag present)
    if ontrt_flag in adcm.columns:
        cm_ontrt = adcm[adcm[ontrt_flag] == "Y"]
    else:
        cm_ontrt = adcm

    # Use treatment arm from ADCM if present, otherwise merge from ADSL
    if group_var in cm_ontrt.columns:
        cm_merged = cm_ontrt[cm_ontrt["USUBJID"].isin(safe_pop["USUBJID"])]
    else:
        cm_merged = cm_ontrt.merge(
            safe_pop[["USUBJID", group_var]].drop_duplicates(),
            on="USUBJID", how="inner"
        )

    result = {"any_conmed": {}, "by_class": {}}

    # Any conmed
    any_cm = cm_merged.groupby(group_var)["USUBJID"].nunique()
    for trt in treatments:
        n = int(any_cm.get(trt, 0))
        N = int(safe_n.get(trt, 1))
        pct = round(100 * n / N, 1) if N > 0 else 0.0
        result["any_conmed"][trt] = {"n": n, "N": N, "pct": pct}

    audit.log(tfl_id, "CM_any",
              f"adcm[{ontrt_flag}=='Y'].groupby('{group_var}')['USUBJID'].nunique() / safe_n",
              f"cm_records={len(cm_merged)}",
              result["any_conmed"], variable="Any ConMed", population_filter=pop_filter)

    # By ATC class
    if class_var in cm_merged.columns:
        classes = sorted(cm_merged[class_var].dropna().unique())
        # Exclude "UNCODED" if present
        classes = [c for c in classes if str(c).upper() != "UNCODED"]

        for cls in classes:
            cls_data = cm_merged[cm_merged[class_var] == cls]
            cls_counts = cls_data.groupby(group_var)["USUBJID"].nunique()
            result["by_class"][cls] = {}
            for trt in treatments:
                n = int(cls_counts.get(trt, 0))
                N = int(safe_n.get(trt, 1))
                pct = round(100 * n / N, 1) if N > 0 else 0.0
                result["by_class"][cls][trt] = {"n": n, "N": N, "pct": pct}

            audit.log(tfl_id, f"CM_class({cls[:30]})",
                      f"adcm[{class_var}=='{cls}'].groupby('{group_var}')['USUBJID'].nunique()",
                      f"class_records={len(cls_data)}",
                      result["by_class"][cls], variable=cls, population_filter=pop_filter)

    return result


def compute_conmeds_by_drug(adcm, adsl, group_var, audit, tfl_id,
                            drug_var="CMDECOD", ontrt_flag="ONTRTFL",
                            min_pct=5.0, pop_filter=None, flags=None):
    """Compute % subjects taking specific drugs (those with >= min_pct overall).

    Returns:
        dict: {drug_name: {trt: {n, pct, N}}}
    """
    if flags is None:
        flags = {"safety_pop": {"var": "SAFFL", "value": "Y"}}
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    safe_pop = adsl[adsl[saf_var] == saf_val]
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()
    total_n = len(safe_pop)
    treatments = sorted(safe_n.index)

    if ontrt_flag in adcm.columns:
        cm_ontrt = adcm[adcm[ontrt_flag] == "Y"]
    else:
        cm_ontrt = adcm

    if group_var in cm_ontrt.columns:
        cm_merged = cm_ontrt[cm_ontrt["USUBJID"].isin(safe_pop["USUBJID"])]
    else:
        cm_merged = cm_ontrt.merge(
            safe_pop[["USUBJID", group_var]].drop_duplicates(),
            on="USUBJID", how="inner"
        )

    # Find drugs meeting minimum threshold
    drug_counts = cm_merged.groupby(drug_var)["USUBJID"].nunique()
    common_drugs = drug_counts[drug_counts / total_n * 100 >= min_pct].index.tolist()

    result = {}
    for drug in sorted(common_drugs):
        if str(drug).upper() == "UNCODED":
            continue
        drug_data = cm_merged[cm_merged[drug_var] == drug]
        drug_counts_trt = drug_data.groupby(group_var)["USUBJID"].nunique()
        result[drug] = {}
        for trt in treatments:
            n = int(drug_counts_trt.get(trt, 0))
            N = int(safe_n.get(trt, 1))
            pct = round(100 * n / N, 1) if N > 0 else 0.0
            result[drug][trt] = {"n": n, "N": N, "pct": pct}

    return result
