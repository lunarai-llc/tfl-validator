"""Concomitant medications validator (T-10 type)."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult, compare_npct
from ..stats.conmeds import compute_conmeds_summary
from ._utils import (
    parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments,
    get_adam_flags
)


def validate_conmeds(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate a concomitant medications summary table (T-10 type).

    Validates % subjects taking any concomitant medication and % by ATC class.
    """
    if tolerances is None:
        tolerances = {"count": 0, "percentage": 0.15}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")

    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]
    group_var = tfl_cfg.get("group_var", "TRT01A")
    flags = get_adam_flags(tfl_cfg)
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    adcm = pd.read_csv(tfl_cfg["dataset"])
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    class_var = tfl_cfg.get("class_var", "CMCLAS")
    ontrt_flag = tfl_cfg.get("ontrt_flag", "ONTRTFL")

    audit.log(tfl_id, "DATA_LOAD",
              f"pd.read_csv('ADCM') + pd.read_csv('ADSL')",
              f"ADCM rows={len(adcm)}, safety_pop={len(safe_pop)}",
              f"Loaded ADCM ({len(adcm)} records) and ADSL ({len(safe_pop)} safety subjects)",
              dataset="ADCM+ADSL")

    calc = compute_conmeds_summary(adcm, adsl, group_var, audit, tfl_id,
                                    class_var=class_var, ontrt_flag=ontrt_flag,
                                    flags=flags)

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE",
              f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

    if not tables:
        print("  ERROR: No tables found")
        return vr

    tbl = tables[0]
    print(f"  Parsed table: {tbl.shape[0]} rows × {tbl.shape[1]} cols")

    trt_col_map = build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments)

    # Any conmed
    for trt in treatments:
        col_idx = trt_col_map.get(trt)
        if col_idx is None:
            continue
        tfl_val = find_tfl_value(tables, "conmed", "any concomitant", col_idx)
        if trt in calc["any_conmed"]:
            cd = calc["any_conmed"][trt]
            match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                        n_tol=tolerances["count"],
                                        pct_tol=tolerances["percentage"])
            label = f"AnyConMed({trt})"
            vr.add(label, tfl_val, f"{cd['n']} ({cd['pct']})", match, note,
                   row_label="Any Concomitant Medication")
            audit.log_comparison(tfl_id, label, tfl_val,
                                  f"{cd['n']} ({cd['pct']})",
                                  match, tolerances["percentage"], note)
            status = "PASS" if match else "FAIL"
            print(f"  {label}: TFL={tfl_val}, Calc={cd['n']}({cd['pct']}%) → {status}")

    # By ATC class
    for cls, trt_data in calc["by_class"].items():
        for trt in treatments:
            col_idx = trt_col_map.get(trt)
            if col_idx is None or trt not in trt_data:
                continue
            tfl_val = find_tfl_value(tables, "class", cls, col_idx)
            cd = trt_data[trt]
            match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                        n_tol=tolerances["count"],
                                        pct_tol=tolerances["percentage"])
            label = f"CM_class({cls[:20]},{trt})"
            vr.add(label, tfl_val, f"{cd['n']} ({cd['pct']})", match, note,
                   row_label=f"ATC: {cls[:30]}")
            audit.log_comparison(tfl_id, label, tfl_val,
                                  f"{cd['n']} ({cd['pct']})",
                                  match, tolerances["percentage"], note)
            status = "PASS" if match else "FAIL"
            print(f"  CM({cls[:25]},{trt}): TFL={tfl_val}, Calc={cd['n']}({cd['pct']}%) → {status}")

    return vr
