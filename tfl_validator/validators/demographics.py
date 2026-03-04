"""Demographic table validator."""
import os
import re
from ..engine.comparator import ValidationResult, compare_values, compare_npct
from ..stats.descriptive import (
    compute_n_subjects, compute_mean, compute_sd, compute_median,
    compute_min_max, compute_freq
)
from ..parsers.adam_specs_reader import get_label, get_derivation
from ._utils import (
    load_dataset, parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments,
    get_rounding_precision, get_continuous_vars, get_categorical_vars
)


def validate_demographics(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate a demographic/baseline table (T-01 type)."""
    if tolerances is None:
        tolerances = {"count": 0, "mean": 0.15, "sd": 0.05, "median": 0.15, "percentage": 0.15, "min_max": 0.5}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")

    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])

    df = load_dataset(tfl_cfg["dataset"], tfl_cfg.get("population_filter"))
    group_var = tfl_cfg.get("group_var", "TRT01A")
    treatments = sorted(df[group_var].unique())
    pop_filter = tfl_cfg.get("population_filter", "")
    tfl_id = tfl_cfg["tfl_id"]

    ds_name = tfl_cfg.get("dataset_name", "")
    specs_note = ""
    if specs:
        ds_vars = specs.get("datasets", {}).get(ds_name, {})
        specs_note = f" | ADaM specs loaded: {len(ds_vars)} variables defined for {ds_name}"
    audit.log(tfl_id, "DATA_LOAD", f"pd.read_csv('{ds_name}')",
              f"rows={len(df)}, cols={list(df.columns)[:5]}",
              f"Loaded {len(df)} rows after filter '{pop_filter}'{specs_note}",
              dataset=ds_name, population_filter=pop_filter)

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

    if not tables:
        print(f"  ERROR: No tables found in TFL file")
        return vr

    tbl = tables[0]
    tfl_cols = list(tbl.columns)
    print(f"  Parsed table: {tbl.shape[0]} rows × {tbl.shape[1]} cols")
    print(f"  Columns: {tfl_cols}")

    # Build treatment → column mapping (config-driven or substring fallback)
    trt_col_map = build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments)

    # ── N per treatment ──
    calc_n = compute_n_subjects(df, group_var, audit, tfl_id, pop_filter)
    for trt in treatments:
        col_idx = trt_col_map.get(trt)
        if col_idx is None:
            continue
        tfl_val = find_tfl_value(tables, "N", "N", col_idx)
        for col_header in tfl_cols:
            # Normalize whitespace for matching (headers may contain newlines)
            col_norm = " ".join(str(col_header).split())
            trt_norm = " ".join(str(trt).split())
            if trt_norm in col_norm:
                m = re.search(r'N=(\d+)', col_norm)
                if m:
                    tfl_val = m.group(1)
        calc_val = calc_n.get(trt, 0)
        match, note = compare_values(tfl_val, calc_val, tolerance=tolerances["count"])
        vr.add(f"N({trt})", tfl_val, calc_val, match, note, row_label="N subjects")
        audit.log_comparison(tfl_id, f"N({trt})", tfl_val, calc_val, match, tolerances["count"], note)
        print(f"  N({trt}): TFL={tfl_val}, Calc={calc_val} → {'PASS' if match else 'FAIL'}")

    # ── Continuous variables (config-driven) ──
    continuous_vars, var_section_map = get_continuous_vars(tfl_cfg, specs, ds_name)

    for var in continuous_vars:
        if specs:
            deriv = get_derivation(specs, ds_name, var)
            lbl = get_label(specs, ds_name, var)
            if deriv:
                audit.log(tfl_id, f"SPECS_REF({var})",
                          f"ADaM Specs derivation for {ds_name}.{var}",
                          f"Label: {lbl}",
                          f"Derivation: {deriv}",
                          variable=var, dataset=ds_name)

        calc_mean = compute_mean(df, var, group_var, audit, tfl_id, pop_filter)
        calc_sd = compute_sd(df, var, group_var, audit, tfl_id, pop_filter)
        calc_median = compute_median(df, var, group_var, audit, tfl_id, pop_filter)
        calc_min, calc_max = compute_min_max(df, var, group_var, audit, tfl_id, pop_filter)

        section_ctx = var_section_map.get(var, var.lower())

        for trt in treatments:
            col_idx = trt_col_map.get(trt)
            if col_idx is None:
                continue

            # Try to find combined "Mean (SD)" row first
            mean_sd_val = find_tfl_value(tables, "Mean", "Mean", col_idx, section_context=section_ctx)
            min_max_val = find_tfl_value(tables, "Min", "Min", col_idx, section_context=section_ctx)

            for stat_name, calc_dict, tol_key, row_ctx in [
                ("Mean", calc_mean, "mean", "Mean"),
                ("SD", calc_sd, "sd", "SD"),
                ("Median", calc_median, "median", "Median"),
                ("Min", calc_min, "min_max", "Min"),
                ("Max", calc_max, "min_max", "Max"),
            ]:
                tfl_val = find_tfl_value(tables, stat_name, row_ctx, col_idx, section_context=section_ctx)

                # Parse combined "Mean (SD)" format: "75.2 (8.59)"
                if stat_name == "Mean" and tfl_val and "(" in str(tfl_val):
                    m_match = re.match(r'([\d.]+)\s*\(', str(tfl_val))
                    if m_match:
                        tfl_val = m_match.group(1)
                elif stat_name == "SD" and tfl_val is None and mean_sd_val and "(" in str(mean_sd_val):
                    m_match = re.match(r'[\d.]+\s*\(([\d.]+)\)', str(mean_sd_val))
                    if m_match:
                        tfl_val = m_match.group(1)

                # Parse combined "Min, Max" format: "52, 89"
                if stat_name == "Min" and tfl_val and "," in str(tfl_val):
                    parts = str(tfl_val).split(",")
                    tfl_val = parts[0].strip()
                elif stat_name == "Max" and tfl_val is None and min_max_val and "," in str(min_max_val):
                    parts = str(min_max_val).split(",")
                    if len(parts) >= 2:
                        tfl_val = parts[1].strip()

                calc_val = calc_dict.get(trt)
                match, note = compare_values(tfl_val, calc_val, tolerance=tolerances[tol_key])
                vr.add(f"{stat_name}({var}, {trt})", tfl_val, calc_val, match, note,
                       row_label=f"{var} — {stat_name}")
                audit.log_comparison(tfl_id, f"{stat_name}({var}, {trt})",
                                     tfl_val, calc_val, match, tolerances[tol_key], note)
                status = "PASS" if match else "FAIL"
                print(f"  {var} {stat_name}({trt}): TFL={tfl_val}, Calc={calc_val} → {status}")

    # ── Categorical variables (config-driven) ──
    categorical_vars = get_categorical_vars(tfl_cfg)

    for var in categorical_vars:
        if specs:
            deriv = get_derivation(specs, ds_name, var)
            lbl = get_label(specs, ds_name, var)
            if deriv:
                audit.log(tfl_id, f"SPECS_REF({var})",
                          f"ADaM Specs derivation for {ds_name}.{var}",
                          f"Label: {lbl}",
                          f"Derivation: {deriv}",
                          variable=var, dataset=ds_name)

        # Map ADaM variable names to typical TFL section labels
        var_label_map = {
            "agegr1": "age group", "agegr2": "age group", "agegr3": "age group",
            "sex": "sex", "race": "race", "racegr1": "race",
            "ethnic": "ethnic", "country": "country", "region1": "region",
            "bmibl": "bmi", "bmiblgr1": "bmi", "weightbl": "weight",
            "heightbl": "height", "ecogbsl": "ecog",
        }
        cat_section = var_label_map.get(var.lower(), var.lower())

        # Common ADaM code → TFL label expansions
        cat_label_expand = {
            "F": "Female", "M": "Male",
            "Y": "Yes", "N": "No",
            "WHITE": "White", "BLACK OR AFRICAN AMERICAN": "Black Or African American",
            "AMERICAN INDIAN OR ALASKA NATIVE": "American Indian Or Alaska Native",
            "ASIAN": "Asian", "HISPANIC OR LATINO": "Hispanic Or Latino",
            "NOT HISPANIC OR LATINO": "Not Hispanic Or Latino",
        }

        calc_freq = compute_freq(df, var, group_var, audit, tfl_id, pop_filter)
        for cat, trt_data in calc_freq.items():
            for trt in treatments:
                col_idx = trt_col_map.get(trt)
                if col_idx is None:
                    continue
                # Try the raw category first, then expanded label
                cat_str = str(cat)
                tfl_val = find_tfl_value(tables, var, cat_str, col_idx, section_context=cat_section)
                if tfl_val is None and cat_str in cat_label_expand:
                    tfl_val = find_tfl_value(tables, var, cat_label_expand[cat_str], col_idx, section_context=cat_section)
                if trt in trt_data:
                    calc_n_val = trt_data[trt]["n"]
                    calc_pct = trt_data[trt]["pct"]
                    match, note = compare_npct(tfl_val, calc_n_val, calc_pct,
                                               n_tol=tolerances["count"],
                                               pct_tol=tolerances["percentage"])
                    vr.add(f"Freq({var}={cat}, {trt})", tfl_val,
                           f"{calc_n_val} ({calc_pct})", match, note,
                           row_label=f"{var}: {cat}")
                    audit.log_comparison(tfl_id, f"Freq({var}={cat}, {trt})",
                                         tfl_val, f"{calc_n_val} ({calc_pct})",
                                         match, tolerances["percentage"], note)
                    status = "PASS" if match else "FAIL"
                    print(f"  {var}={cat}({trt}): TFL={tfl_val}, Calc={calc_n_val}({calc_pct}%) → {status}")

    return vr
