"""Exposure/treatment duration validator (T-09 type)."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult, compare_mean_sd, compare_npct
from ..stats.exposure import compute_exposure_summary, compute_exposure_categories
from ._utils import (
    parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments,
    get_adam_flags, get_rounding_precision
)


def validate_exposure(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate an exposure/treatment duration table (T-09 type).

    Validates mean, median, SD, min, max of treatment duration (days)
    and % subjects by duration categories per treatment arm.
    """
    if tolerances is None:
        tolerances = {"mean": 0.15, "count": 0, "percentage": 0.15}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")

    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]
    group_var = tfl_cfg.get("group_var", "TRT01A")
    flags = get_adam_flags(tfl_cfg)
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]
    dur_var = tfl_cfg.get("duration_var", "TRTDURD")

    adsl = pd.read_csv(tfl_cfg["dataset"])
    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    audit.log(tfl_id, "DATA_LOAD",
              f"pd.read_csv('ADSL')",
              f"ADSL rows={len(adsl)}, safety_pop={len(safe_pop)}",
              f"Loaded ADSL ({len(safe_pop)} safety subjects)",
              dataset="ADSL")

    # Summary statistics
    calc_summary = compute_exposure_summary(adsl, group_var, audit, tfl_id,
                                             dur_var=dur_var, flags=flags)

    # Category breakdown
    categories = tfl_cfg.get("duration_categories", [
        ("< 12 weeks", 0, 83),
        ("12 to <24 weeks", 84, 167),
        (">= 24 weeks", 168, 9999),
    ])
    calc_cats = compute_exposure_categories(adsl, group_var, audit, tfl_id,
                                             dur_var=dur_var, categories=categories,
                                             flags=flags)

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE",
              f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

    if not tables:
        print("  ERROR: No tables found")
        return vr

    print(f"  Parsed table: {tables[0].shape[0]} rows × {tables[0].shape[1]} cols")

    trt_col_map = build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments)

    # Validate summary stats
    for trt in treatments:
        col_idx = trt_col_map.get(trt)
        if col_idx is None or trt not in calc_summary:
            continue
        cd = calc_summary[trt]

        for stat_label, stat_key in [("mean", "mean"), ("median", "median"),
                                      ("min", "min"), ("max", "max")]:
            if cd[stat_key] is None:
                continue
            tfl_val = find_tfl_value(tables, "Duration", stat_label, col_idx)
            match, note = compare_mean_sd(tfl_val, cd[stat_key],
                                          tolerance=tolerances["mean"])
            label = f"Duration_{stat_label}({trt})"
            vr.add(label, tfl_val, str(cd[stat_key]), match, note,
                   row_label=f"Duration {stat_label}")
            audit.log_comparison(tfl_id, label, tfl_val, str(cd[stat_key]),
                                  match, tolerances["mean"], note)
            status = "PASS" if match else "FAIL"
            print(f"  {label}: TFL={tfl_val}, Calc={cd[stat_key]} → {status}")

    # Validate categories
    for cat_label, trt_data in calc_cats.items():
        for trt in treatments:
            col_idx = trt_col_map.get(trt)
            if col_idx is None or trt not in trt_data:
                continue
            cd = trt_data[trt]
            tfl_val = find_tfl_value(tables, "Duration", cat_label, col_idx)
            match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                        n_tol=tolerances["count"],
                                        pct_tol=tolerances["percentage"])
            label = f"DurCat({cat_label},{trt})"
            vr.add(label, tfl_val, f"{cd['n']} ({cd['pct']})", match, note,
                   row_label=cat_label)
            audit.log_comparison(tfl_id, label, tfl_val,
                                  f"{cd['n']} ({cd['pct']})",
                                  match, tolerances["percentage"], note)
            status = "PASS" if match else "FAIL"
            print(f"  {label}: TFL={tfl_val}, Calc={cd['n']}({cd['pct']}%) → {status}")

    return vr
