"""Vital signs summary validator (T-08 type)."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult, compare_mean_sd
from ..stats.vitals import compute_vitals_summary
from ._utils import (
    parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments,
    get_adam_flags, get_rounding_precision
)


def validate_vitals_summary(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate a vital signs summary table (T-08 type).

    Validates mean ± SD for vital signs parameters at baseline and
    end-of-treatment (or configured visits).
    """
    if tolerances is None:
        tolerances = {"mean": 0.15, "sd": 0.15}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")

    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]
    group_var = tfl_cfg.get("group_var", "TRT01A")
    flags = get_adam_flags(tfl_cfg)
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    adlb = pd.read_csv(tfl_cfg["dataset"], low_memory=False)
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    # Determine PARAMCDs
    var_mapping = tfl_cfg.get("variable_mapping", {})
    cont_entries = var_mapping.get("continuous", [])
    paramcds = [e["variable_name"] for e in cont_entries if e.get("variable_name")] if cont_entries else None
    if not paramcds:
        paramcds = tfl_cfg.get("paramcds", ["SYSBP", "DIABP", "PULSE"])

    visits = tfl_cfg.get("visits", ["Baseline", "End of Treatment"])

    audit.log(tfl_id, "DATA_LOAD",
              f"pd.read_csv('ADVS') + pd.read_csv('ADSL')",
              f"ADVS rows={len(adlb)}, safety_pop={len(safe_pop)}",
              f"Loaded ADVS ({len(adlb)} records) and ADSL ({len(safe_pop)} safety subjects)",
              dataset="ADVS+ADSL")

    calc = compute_vitals_summary(adlb, adsl, group_var, audit, tfl_id,
                                   paramcds=paramcds, visits=visits, flags=flags)

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE",
              f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

    if not tables:
        print("  ERROR: No tables found")
        return vr

    print(f"  Parsed table: {tables[0].shape[0]} rows × {tables[0].shape[1]} cols")

    trt_col_map = build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments)

    for paramcd, visit_data in calc.items():
        for visit_label, trt_data in visit_data.items():
            # visit_label is derived from visit_name: "baseline" → "baseline mean"
            # "end_of_treatment" → "end of treatment mean"
            row_ctx_mean = f"{visit_label.replace('_', ' ')} mean"

            for trt in treatments:
                col_idx = trt_col_map.get(trt)
                if col_idx is None or trt not in trt_data:
                    continue
                cd = trt_data[trt]
                # Section context = paramcd label (col 0 of TFL)
                section_ctx = paramcd.lower()

                # Row context matches col 1: e.g., "Baseline Mean" or "End of Treatment Mean"
                tfl_mean = find_tfl_value(tables, paramcd, row_ctx_mean, col_idx,
                                          section_context=section_ctx)
                if cd["mean"] is not None:
                    match, note = compare_mean_sd(tfl_mean, cd["mean"],
                                                  tolerance=tolerances["mean"])
                    label = f"{paramcd}_{visit_label}_mean({trt})"
                    vr.add(label, tfl_mean, str(cd["mean"]), match, note,
                           row_label=f"{paramcd} {visit_label} Mean")
                    audit.log_comparison(tfl_id, label, tfl_mean, str(cd["mean"]),
                                         match, tolerances["mean"], note)
                    status = "PASS" if match else "FAIL"
                    print(f"  {label}: TFL={tfl_mean}, Calc={cd['mean']} → {status}")

    return vr
