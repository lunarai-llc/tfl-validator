"""Medical history validator (T-11 type)."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult, compare_npct
from ..stats.medhist import compute_medhist_summary
from ._utils import (
    parse_tfl, find_tfl_value,
    build_treatment_column_map_with_treatments,
    get_adam_flags
)


def validate_medhist(tfl_cfg, audit, specs=None, tolerances=None):
    """Validate a medical history summary table (T-11 type).

    Validates % subjects with medical history conditions by body system.
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

    admh = pd.read_csv(tfl_cfg["dataset"])
    adsl = pd.read_csv(tfl_cfg["aux_dataset"])
    safe_pop = adsl[adsl[saf_var] == saf_val]
    treatments = sorted(safe_pop[group_var].unique())

    soc_var = tfl_cfg.get("soc_var", "MHBODSYS")
    cat_var = tfl_cfg.get("cat_var", None)

    audit.log(tfl_id, "DATA_LOAD",
              f"pd.read_csv('ADMH') + pd.read_csv('ADSL')",
              f"ADMH rows={len(admh)}, safety_pop={len(safe_pop)}",
              f"Loaded ADMH ({len(admh)} records) and ADSL ({len(safe_pop)} safety subjects)",
              dataset="ADMH+ADSL")

    calc = compute_medhist_summary(admh, adsl, group_var, audit, tfl_id,
                                    soc_var=soc_var, cat_var=cat_var, flags=flags)

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

    # Any medical history
    for trt in treatments:
        col_idx = trt_col_map.get(trt)
        if col_idx is None:
            continue
        tfl_val = find_tfl_value(tables, "medhist", "any medical history", col_idx)
        if trt in calc["any_mh"]:
            cd = calc["any_mh"][trt]
            match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                        n_tol=tolerances["count"],
                                        pct_tol=tolerances["percentage"])
            label = f"AnyMH({trt})"
            vr.add(label, tfl_val, f"{cd['n']} ({cd['pct']})", match, note,
                   row_label="Any Medical History")
            audit.log_comparison(tfl_id, label, tfl_val,
                                  f"{cd['n']} ({cd['pct']})",
                                  match, tolerances["percentage"], note)
            status = "PASS" if match else "FAIL"
            print(f"  {label}: TFL={tfl_val}, Calc={cd['n']}({cd['pct']}%) → {status}")

    # By body system (SOC)
    for soc, trt_data in calc["by_soc"].items():
        for trt in treatments:
            col_idx = trt_col_map.get(trt)
            if col_idx is None or trt not in trt_data:
                continue
            tfl_val = find_tfl_value(tables, "SOC", soc, col_idx)
            cd = trt_data[trt]
            match, note = compare_npct(tfl_val, cd["n"], cd["pct"],
                                        n_tol=tolerances["count"],
                                        pct_tol=tolerances["percentage"])
            label = f"MH_SOC({soc[:20]},{trt})"
            vr.add(label, tfl_val, f"{cd['n']} ({cd['pct']})", match, note,
                   row_label=f"SOC: {soc[:30]}")
            audit.log_comparison(tfl_id, label, tfl_val,
                                  f"{cd['n']} ({cd['pct']})",
                                  match, tolerances["percentage"], note)
            status = "PASS" if match else "FAIL"
            print(f"  MH_SOC({soc[:30]},{trt}): TFL={tfl_val}, Calc={cd['n']}({cd['pct']}%) → {status}")

    return vr
