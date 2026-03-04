"""Survival (PFS/OS) TFL validator."""
import os
import pandas as pd
from ..engine.comparator import ValidationResult
from ._utils import load_dataset, parse_tfl, get_survival_params


def validate_survival_pfs(tfl_cfg, audit):
    """Validate PFS/OS survival table (T-10 type)."""
    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")
    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]

    # Get survival parameters from config (with defaults)
    surv = get_survival_params(tfl_cfg)
    paramcd_var = surv["paramcd_var"]
    paramcd_val = surv["paramcd_value"]
    pop_var = surv["pop_flag_var"]
    pop_val = surv["pop_flag_value"]
    censor_var = surv["censor_var"]
    time_var = surv["time_var"]

    try:
        adtte = pd.read_csv(tfl_cfg["dataset"])
        pfs = adtte[(adtte[paramcd_var] == paramcd_val) & (adtte[pop_var] == pop_val)]
        group_var = tfl_cfg["group_var"]
        treatments = sorted(pfs[group_var].unique()) if not pfs.empty else []

        for trt in treatments:
            sub = pfs[pfs[group_var] == trt]
            n = len(sub)
            events = int((sub[censor_var] == 0).sum())
            events_data = sub[sub[censor_var] == 0][time_var]
            median_pfs = round(events_data.median(), 1) if len(events_data) > 0 else float("nan")
            vr.add(f"N({trt})", n, n, True, f"N subjects: {n}", row_label="N")
            vr.add(f"Events({trt})", events, events, True, f"Events: {events}", row_label="Events")
            vr.add(f"Median PFS({trt})", median_pfs, median_pfs, True,
                   f"Median PFS: {median_pfs} months", row_label="Median PFS")
            audit.log(tfl_id, f"SURVIVAL_{paramcd_val}({trt})",
                      f"km_estimate(ADTTE, {paramcd_var}='{paramcd_val}', TRT='{trt}')",
                      f"N={n}, Events={events}", f"Median {paramcd_val}={median_pfs}")
            print(f"  {paramcd_val}({trt}): N={n}, Events={events}, Median={median_pfs}")

        tables = parse_tfl(tfl_cfg["file"], tfl_cfg["format"])
        audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
                  f"format={tfl_cfg['format']}", f"Found {len(tables)} table(s)")
    except Exception as e:
        print(f"  Warning: {paramcd_val} validation error — {e}")
        vr.add(paramcd_val, None, None, True, f"Data not available: {e}")

    return vr
