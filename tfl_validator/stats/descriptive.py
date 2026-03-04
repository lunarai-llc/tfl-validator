"""Descriptive statistics engine for TFL validation.
Computes N, mean, SD, median, min, max, percentages, frequencies.
All calculations are logged via the audit logger.
"""
import pandas as pd
import numpy as np


def compute_n(df, variable, group_var, audit, tfl_id, pop_filter=None):
    """Count of non-missing values per treatment group."""
    code = f"df.groupby('{group_var}')['{variable}'].count()"
    result = df.groupby(group_var)[variable].count().to_dict()
    audit.log(tfl_id, f"N({variable})", code, f"n_rows={len(df)}", result,
              variable=variable, dataset="filtered", population_filter=pop_filter)
    return result


def compute_n_subjects(df, group_var, audit, tfl_id, pop_filter=None):
    """Count of unique subjects per treatment group."""
    code = f"df.groupby('{group_var}')['USUBJID'].nunique()"
    result = df.groupby(group_var)["USUBJID"].nunique().to_dict()
    audit.log(tfl_id, "N_subjects", code, f"n_rows={len(df)}", result,
              variable="USUBJID", dataset="filtered", population_filter=pop_filter)
    return result


def compute_mean(df, variable, group_var, audit, tfl_id, pop_filter=None):
    code = f"df.groupby('{group_var}')['{variable}'].mean()"
    result = {k: round(v, 1) for k, v in df.groupby(group_var)[variable].mean().items()}
    audit.log(tfl_id, f"Mean({variable})", code, f"n_rows={len(df)}", result,
              variable=variable, population_filter=pop_filter)
    return result


def compute_sd(df, variable, group_var, audit, tfl_id, pop_filter=None):
    code = f"df.groupby('{group_var}')['{variable}'].std(ddof=1)"
    result = {k: round(v, 2) for k, v in df.groupby(group_var)[variable].std(ddof=1).items()}
    audit.log(tfl_id, f"SD({variable})", code, f"n_rows={len(df)}", result,
              variable=variable, population_filter=pop_filter)
    return result


def compute_median(df, variable, group_var, audit, tfl_id, pop_filter=None):
    code = f"df.groupby('{group_var}')['{variable}'].median()"
    result = {k: round(v, 1) for k, v in df.groupby(group_var)[variable].median().items()}
    audit.log(tfl_id, f"Median({variable})", code, f"n_rows={len(df)}", result,
              variable=variable, population_filter=pop_filter)
    return result


def compute_min_max(df, variable, group_var, audit, tfl_id, pop_filter=None):
    code_min = f"df.groupby('{group_var}')['{variable}'].min()"
    code_max = f"df.groupby('{group_var}')['{variable}'].max()"
    mins = df.groupby(group_var)[variable].min().to_dict()
    maxs = df.groupby(group_var)[variable].max().to_dict()
    audit.log(tfl_id, f"Min({variable})", code_min, f"n_rows={len(df)}", mins,
              variable=variable, population_filter=pop_filter)
    audit.log(tfl_id, f"Max({variable})", code_max, f"n_rows={len(df)}", maxs,
              variable=variable, population_filter=pop_filter)
    return mins, maxs


def compute_freq(df, variable, group_var, audit, tfl_id, pop_filter=None):
    """Frequency counts and percentages for categorical variable."""
    code = f"pd.crosstab(df['{variable}'], df['{group_var}'])"
    ct = pd.crosstab(df[variable], df[group_var])
    totals = df.groupby(group_var)["USUBJID"].nunique()

    result = {}
    for cat in ct.index:
        result[cat] = {}
        for trt in ct.columns:
            n = int(ct.loc[cat, trt])
            denom = int(totals[trt]) if trt in totals else 1
            pct = round(100 * n / denom, 1) if denom > 0 else 0.0
            result[cat][trt] = {"n": n, "pct": pct, "display": f"{n} ({pct})"}

    audit.log(tfl_id, f"Freq({variable})", code,
              f"categories={list(ct.index)}, groups={list(ct.columns)}", result,
              variable=variable, population_filter=pop_filter)
    return result


def compute_demog_summary(df, group_var, audit, tfl_id, pop_filter=None):
    """Full demographic summary: N, continuous vars (AGE, BMI), categorical vars (SEX, RACE)."""
    results = {}
    results["N"] = compute_n_subjects(df, group_var, audit, tfl_id, pop_filter)

    for var in ["AGE", "BMI"]:
        if var in df.columns:
            results[f"{var}_mean"] = compute_mean(df, var, group_var, audit, tfl_id, pop_filter)
            results[f"{var}_sd"] = compute_sd(df, var, group_var, audit, tfl_id, pop_filter)
            results[f"{var}_median"] = compute_median(df, var, group_var, audit, tfl_id, pop_filter)
            results[f"{var}_min"], results[f"{var}_max"] = compute_min_max(
                df, var, group_var, audit, tfl_id, pop_filter)

    for var in ["SEX", "RACE"]:
        if var in df.columns:
            results[f"{var}_freq"] = compute_freq(df, var, group_var, audit, tfl_id, pop_filter)

    return results
