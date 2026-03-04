"""Lab summary validator (T-07 type)."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult, compare_mean_sd
from ..stats.lab import compute_lab_summary
from ._utils import (
    parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments,
    get_adam_flags, get_rounding_precision
)


def validate_lab_summary(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate a lab results summary table (T-07 type).

    Validates mean ± SD at baseline and post-baseline visit for
    selected laboratory parameters.
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

    # Load datasets
    adlb = pd.read_csv(tfl_cfg["dataset"], low_memory=False)
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    # Determine which PARAMCDs to validate
    var_mapping = tfl_cfg.get("variable_mapping", {})
    cont_entries = var_mapping.get("continuous", [])
    paramcds = [e["variable_name"] for e in cont_entries if e.get("variable_name")] if cont_entries else None
    if not paramcds:
        paramcds = tfl_cfg.get("paramcds", ["ALT", "AST", "CHOLES", "CREAT", "BUN"])

    visit_baseline = tfl_cfg.get("visit_baseline", "Baseline")
    visit_post = tfl_cfg.get("visit_post", "Week 26")

    audit.log(tfl_id, "DATA_LOAD",
              f"pd.read_csv('ADLB') + pd.read_csv('ADSL')",
              f"ADLB rows={len(adlb)}, safety_pop={len(safe_pop)}",
              f"Loaded ADLB ({len(adlb)} records) and ADSL ({len(safe_pop)} safety subjects)",
              dataset="ADLB+ADSL")

    # Compute statistics
    calc = compute_lab_summary(adlb, adsl, group_var, audit, tfl_id,
                                paramcds=paramcds,
                                visit_baseline=visit_baseline,
                                visit_post=visit_post,
                                flags=flags)

    # Parse TFL
    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE",
              f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

    if not tables:
        print("  ERROR: No tables found")
        return vr

    print(f"  Parsed table: {tables[0].shape[0]} rows × {tables[0].shape[1]} cols")

    trt_col_map = build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments)

    # Map visit_label key → TFL row label prefix used in the shell
    # visit_label comes from compute_lab_summary: "baseline" or "postbaseline"
    visit_row_label_map = {
        "baseline":    "baseline",
        "postbaseline": visit_post.lower(),   # e.g., "week 26"
    }

    for paramcd, visit_data in calc.items():
        for visit_label, trt_data in visit_data.items():
            # Build the exact row label used in col 1 of the TFL
            # e.g., "Baseline Mean", "Week 26 Mean", "Baseline SD", "Week 26 SD"
            vis_prefix = visit_row_label_map.get(visit_label, visit_label)

            for trt in treatments:
                col_idx = trt_col_map.get(trt)
                if col_idx is None:
                    continue
                if trt not in trt_data:
                    continue
                cd = trt_data[trt]

                # Section context = paramcd (col 0 of TFL)
                section_ctx = paramcd.lower()

                # Mean — row_context matches col 1: e.g., "Baseline Mean"
                row_ctx_mean = f"{vis_prefix} mean"
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

                # SD — row_context matches col 1: e.g., "Baseline SD"
                row_ctx_sd = f"{vis_prefix} sd"
                tfl_sd = find_tfl_value(tables, paramcd, row_ctx_sd, col_idx,
                                        section_context=section_ctx)
                if cd["sd"] is not None:
                    match, note = compare_mean_sd(tfl_sd, cd["sd"],
                                                  tolerance=tolerances["sd"])
                    label = f"{paramcd}_{visit_label}_sd({trt})"
                    vr.add(label, tfl_sd, str(cd["sd"]), match, note,
                           row_label=f"{paramcd} {visit_label} SD")
                    audit.log_comparison(tfl_id, label, tfl_sd, str(cd["sd"]),
                                         match, tolerances["sd"], note)
                    status = "PASS" if match else "FAIL"
                    print(f"  {label}: TFL={tfl_sd}, Calc={cd['sd']} → {status}")

    return vr
