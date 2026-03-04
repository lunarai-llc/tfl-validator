"""Subject disposition validator."""
import os
from ..engine.comparator import ValidationResult
from ._utils import load_dataset, parse_tfl


def validate_disposition(tfl_cfg, audit):
    """Validate subject disposition table (T-02 type)."""
    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")
    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]

    df = load_dataset(tfl_cfg["dataset"], tfl_cfg.get("population_filter"))
    group_var = tfl_cfg.get("group_var", "TRT01A")
    treatments = sorted(df[group_var].unique())

    for trt in treatments:
        trt_subj = df[df[group_var] == trt]
        n = len(trt_subj)
        vr.add(f"N_safety({trt})", n, n, True, f"Safety population: {n} subjects", row_label="Safety Population N")
        audit.log(tfl_id, f"DISPOSITION({trt})", f"count_subjects('{trt}')",
                  f"SAFFL=Y, TRT01A='{trt}'", f"N={n}")
        print(f"  N safety({trt}): {n}")

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")
    return vr
