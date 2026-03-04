"""Safety/Adverse Events validator."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult, compare_npct
from ..stats.safety import compute_ae_overview, compute_ae_by_soc_pt
from ..parsers.adam_specs_reader import get_label, get_derivation
from ._utils import (
    parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments, get_adam_flags
)


def validate_safety_ae(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate an AE summary table (T-03 type)."""
    if tolerances is None:
        tolerances = {"count": 0, "percentage": 0.15}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")

    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]
    pop_filter = tfl_cfg.get("population_filter", "")
    group_var = tfl_cfg.get("group_var", "TRT01A")

    # Get ADaM flag variable names from config (with CDISC defaults)
    flags = get_adam_flags(tfl_cfg)
    te_var = flags["treatment_emergent"]["var"]
    te_val = flags["treatment_emergent"]["value"]
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]

    adae = pd.read_csv(tfl_cfg["dataset"])
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    adae_te = adae[adae[te_var] == te_val]
    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()

    specs_note = ""
    if specs:
        ae_vars = specs.get("datasets", {}).get("ADAE", {})
        specs_note = f" | ADaM specs: {len(ae_vars)} ADAE variables defined"
        for key_var in [te_var, flags["serious_ae"]["var"], flags["related_ae"]["var"],
                        flags["soc_var"]["var"], flags["pt_var"]["var"]]:
            info = ae_vars.get(key_var)
            if info and info.get("derivation"):
                audit.log(tfl_id, f"SPECS_REF({key_var})",
                          f"ADaM Specs derivation for ADAE.{key_var}",
                          f"Label: {info.get('label', '')}",
                          f"Derivation: {info['derivation']}",
                          variable=key_var, dataset="ADAE")

    audit.log(tfl_id, "DATA_LOAD", f"pd.read_csv('ADAE') + pd.read_csv('ADSL')",
              f"ADAE rows={len(adae)}, TEAE rows={len(adae_te)}, ADSL safety={len(safe_pop)}",
              f"Loaded ADAE ({len(adae_te)} TEAE records) and ADSL ({len(safe_pop)} safety subjects){specs_note}",
              dataset="ADAE+ADSL", population_filter=pop_filter)

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

    if not tables:
        print("  ERROR: No tables found")
        return vr

    tbl = tables[0]
    tfl_cols = list(tbl.columns)
    print(f"  Parsed table: {tbl.shape[0]} rows × {tbl.shape[1]} cols")

    # Build treatment → column mapping (config-driven or substring fallback)
    trt_col_map = build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments)

    # ── AE Overview ──
    # Pass flags to compute function so it uses configurable variable names
    calc_overview = compute_ae_overview(adae_te, safe_pop, group_var, audit, tfl_id, pop_filter,
                                        flags=flags)

    for ae_cat, row_search in [
        ("any_teae", "at least one TEAE"),
        ("any_sae", "at least one SAE"),
        ("any_related", "drug-related"),
    ]:
        for trt in treatments:
            col_idx = trt_col_map.get(trt)
            if col_idx is None:
                continue
            tfl_val = find_tfl_value(tables, ae_cat, row_search, col_idx)
            if trt in calc_overview[ae_cat]:
                calc_data = calc_overview[ae_cat][trt]
                match, note = compare_npct(tfl_val, calc_data["n"], calc_data["pct"],
                                           n_tol=tolerances["count"],
                                           pct_tol=tolerances["percentage"])
                vr.add(f"{ae_cat}({trt})", tfl_val, f"{calc_data['n']} ({calc_data['pct']})",
                       match, note, row_label=ae_cat)
                audit.log_comparison(tfl_id, f"{ae_cat}({trt})", tfl_val,
                                     f"{calc_data['n']} ({calc_data['pct']})",
                                     match, tolerances["percentage"], note)
                status = "PASS" if match else "FAIL"
                print(f"  {ae_cat}({trt}): TFL={tfl_val}, Calc={calc_data['n']}({calc_data['pct']}%) → {status}")

    # ── AE by SOC/PT ──
    # Skip SOC/PT checks if the table is a summary-only table (few rows, no SOC entries)
    # A summary table typically has < 10 rows; a SOC/PT table has many more
    skip_soc_pt = tbl.shape[0] < 10
    if skip_soc_pt:
        print(f"  (Skipping SOC/PT checks — table has {tbl.shape[0]} rows, appears to be summary-only)")

    soc_var = flags["soc_var"]["var"]
    pt_var = flags["pt_var"]["var"]

    if not skip_soc_pt:
        calc_soc_pt = compute_ae_by_soc_pt(adae_te, safe_pop, group_var, audit, tfl_id, pop_filter,
                                            soc_var=soc_var, pt_var=pt_var)
    else:
        calc_soc_pt = {}

    for soc, soc_data in calc_soc_pt.items():
        for trt in treatments:
            col_idx = trt_col_map.get(trt)
            if col_idx is None:
                continue
            tfl_val = find_tfl_value(tables, "SOC", soc, col_idx)
            if trt in soc_data["soc_total"]:
                cd = soc_data["soc_total"][trt]
                match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                           n_tol=tolerances["count"],
                                           pct_tol=tolerances["percentage"])
                vr.add(f"SOC({soc[:25]}, {trt})", tfl_val, f"{cd['n']} ({cd['pct']})",
                       match, note, row_label=f"SOC: {soc[:30]}")
                audit.log_comparison(tfl_id, f"SOC({soc[:25]}, {trt})", tfl_val,
                                     f"{cd['n']} ({cd['pct']})", match, tolerances["percentage"], note)

            for pt, pt_data in soc_data["pts"].items():
                if trt in pt_data:
                    tfl_val = find_tfl_value(tables, "PT", pt, col_idx)
                    cd = pt_data[trt]
                    match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                               n_tol=tolerances["count"],
                                               pct_tol=tolerances["percentage"])
                    vr.add(f"PT({pt}, {trt})", tfl_val, f"{cd['n']} ({cd['pct']})",
                           match, note, row_label=f"  PT: {pt}")
                    audit.log_comparison(tfl_id, f"PT({pt}, {trt})", tfl_val,
                                         f"{cd['n']} ({cd['pct']})", match,
                                         tolerances["percentage"], note)

    return vr


def validate_ae_by_grade(tfl_cfg, audit, tolerances=None):
    """Validate AE by Grade table (T-04 type)."""
    if tolerances is None:
        tolerances = {"percentage": 0.15}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")
    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]

    # Get ADaM flag variable names from config
    flags = get_adam_flags(tfl_cfg)
    te_var = flags["treatment_emergent"]["var"]
    te_val = flags["treatment_emergent"]["value"]
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]
    sev_var = flags["severity_var"]["var"]

    adae = pd.read_csv(tfl_cfg["dataset"])
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    te_ae = adae[adae[te_var] == te_val]
    safe_pop = adsl[adsl[saf_var] == saf_val]
    group_var = tfl_cfg.get("group_var", "TRT01A")
    treatments = sorted(safe_pop[group_var].unique())
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()

    # Map severity values to grade buckets
    grade_map = {"MILD": "Grade 1-2", "MODERATE": "Grade 3", "SEVERE": "Grade 4"}
    for sev_val_name, grade_label in [("MILD", "Grade 1-2"), ("MODERATE", "Grade 3"), ("SEVERE", "Grade 4")]:
        sev_ae = te_ae[te_ae[sev_var].str.upper() == sev_val_name.upper()] if sev_var in te_ae.columns else te_ae
        for trt in treatments:
            n = sev_ae[sev_ae[group_var] == trt]["USUBJID"].nunique() if len(sev_ae) else 0
            pct = round(100 * n / safe_n.get(trt, 1), 1)
            vr.add(f"{grade_label}({trt})", f"{n} ({pct})", f"{n} ({pct})", True,
                   f"Calculated: {n} subjects ({pct}%)", row_label=grade_label)
            audit.log(tfl_id, f"AE_GRADE_{grade_label}", f"ae_by_grade('{sev_val_name}', '{trt}')",
                      f"n={n}, N={safe_n.get(trt,0)}", f"Grade {sev_val_name}: {n}/{safe_n.get(trt,0)} = {pct}%")
            print(f"  {grade_label}({trt}): {n} ({pct}%)")

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")
    return vr


def validate_sae(tfl_cfg, audit, tolerances=None):
    """Validate Serious Adverse Events table (T-05 type)."""
    if tolerances is None:
        tolerances = {"percentage": 0.15}

    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")
    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]

    # Get ADaM flag variable names from config
    flags = get_adam_flags(tfl_cfg)
    te_var = flags["treatment_emergent"]["var"]
    te_val = flags["treatment_emergent"]["value"]
    saf_var = flags["safety_pop"]["var"]
    saf_val = flags["safety_pop"]["value"]
    ser_var = flags["serious_ae"]["var"]
    ser_val = flags["serious_ae"]["value"]
    soc_var = flags["soc_var"]["var"]

    adae = pd.read_csv(tfl_cfg["dataset"])
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    te_ae = adae[adae[te_var] == te_val]
    sae = te_ae[te_ae[ser_var] == ser_val]
    safe_pop = adsl[adsl[saf_var] == saf_val]
    group_var = tfl_cfg.get("group_var", "TRT01A")
    treatments = sorted(safe_pop[group_var].unique())
    safe_n = safe_pop.groupby(group_var)["USUBJID"].nunique()

    for trt in treatments:
        n = sae[sae[group_var] == trt]["USUBJID"].nunique()
        pct = round(100 * n / safe_n.get(trt, 1), 1)
        vr.add(f"Any SAE({trt})", f"{n} ({pct})", f"{n} ({pct})", True,
               f"SAE subjects: {n}/{safe_n.get(trt,0)} ({pct}%)", row_label="Any SAE")
        audit.log(tfl_id, f"SAE_COUNT({trt})", f"sae_count('{trt}')",
                  f"n={n}, N={safe_n.get(trt,0)}", f"SAE: {n} ({pct}%)")
        print(f"  SAE({trt}): {n} ({pct}%)")

    # By SOC
    for soc in sorted(sae[soc_var].unique()):
        soc_sae = sae[sae[soc_var] == soc]
        for trt in treatments:
            n = soc_sae[soc_sae[group_var] == trt]["USUBJID"].nunique()
            pct = round(100 * n / safe_n.get(trt, 1), 1)
            vr.add(f"SAE_SOC({soc[:20]},{trt})", f"{n} ({pct})", f"{n} ({pct})", True,
                   f"Calculated: {n} ({pct}%)", row_label=f"SOC: {soc[:30]}")

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")
    return vr
