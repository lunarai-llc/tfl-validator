"""Config Loader — reads study_config.xlsx and returns a fully-resolved
config dict.

Usage:
    from config_loader import load_study_config
    config = load_study_config("study_config.xlsx", base_dir=BASE)
"""
import os
import re
import pandas as pd


def _cell(df, label, default=""):
    """Pull a value from a two-column label/value DataFrame by label."""
    row = df[df.iloc[:, 0].astype(str).str.strip() == label]
    if row.empty:
        return default
    v = row.iloc[0, 1]
    return "" if pd.isna(v) else str(v).strip()


def load_study_config(intake_path: str, base_dir: str = None) -> dict:
    """Load all config from the study intake Excel file.

    Args:
        intake_path: Path to study_config.xlsx (absolute or relative to base_dir).
        base_dir:    Root directory for resolving relative file paths in the
                     intake sheet. Defaults to the directory of intake_path.

    Returns:
        config dict with keys: study_info, tfl_configs, tolerances,
        treatment_order, validation_options, and path keys
        (adam_specs_file).
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(intake_path))

    xls = pd.ExcelFile(intake_path)

    # ── Study Info sheet ─────────────────────────────────────────────────
    si_raw = pd.read_excel(xls, sheet_name="Study Info", header=None)
    # Drop section-header rows (those where col B is NaN and col A is a section label)
    si = si_raw[si_raw.iloc[:, 1].notna()].reset_index(drop=True)

    def g(label, default=""):
        return _cell(si, label, default)

    data_dir   = g("Base Data Directory", "sample_data/")
    tfl_dir    = g("TFL Shell Directory", "sample_data/sample_tfls/")
    specs_file = g("ADaM Specs File")
    sas_dir    = g("SAS Output Directory", "sample_data/generated_sas/")

    def abspath(rel):
        if not rel:
            return ""
        return rel if os.path.isabs(rel) else os.path.join(base_dir, rel)

    data_dir_abs = abspath(data_dir)
    tfl_dir_abs  = abspath(tfl_dir)

    study_info = {
        "study_id":    g("Study ID"),
        "study_title": g("Study Title"),
        "protocol":    g("Protocol Number"),
        "sponsor":     g("Sponsor"),
        "cro":         g("CRO / Partner"),
        "phase":       g("Phase"),
        "indication":  g("Indication"),
        "analysis":    g("Analysis Type"),
        "generated_by": "TFL Validator v1.0 (OSS)",
    }

    validation_options = {
        "validate_against_protocol": False,  # Pro feature
        "validate_against_sap":      False,  # Pro feature
        "generate_sas_code":         False,  # Pro feature
        "sas_output_dir":            abspath(sas_dir),
    }

    tolerances = {
        "count":      float(g("Count (integers)", 0)),
        "mean":       float(g("Mean",             0.15)),
        "sd":         float(g("SD",               0.05)),
        "median":     float(g("Median",           0.15)),
        "percentage": float(g("Percentage",       0.15)),
        "p_value":    float(g("P-value",          0.005)),
        "min_max":    0.5,
    }

    # Treatment arm order — collect Arm 1..N rows
    treatment_order = []
    for n in range(1, 9):
        arm = g(f"Arm {n}")
        if arm:
            treatment_order.append(arm)

    # ── Datasets sheet ───────────────────────────────────────────────────
    ds_raw = pd.read_excel(xls, sheet_name="Datasets", header=2)
    ds_raw.columns = [str(c).strip() for c in ds_raw.columns]
    dataset_map = {}   # dataset_name → absolute file path
    for _, row in ds_raw.iterrows():
        name = str(row.get("Dataset Name", "")).strip()
        fname = str(row.get("Filename", "")).strip()
        if name and fname and fname.lower() not in ("", "nan", "not provided — placeholder only"):
            dataset_map[name] = os.path.join(data_dir_abs, fname)

    # ── TFLs sheet ───────────────────────────────────────────────────────
    tfl_raw = pd.read_excel(xls, sheet_name="TFLs", header=2)
    tfl_raw.columns = [str(c).strip() for c in tfl_raw.columns]

    tfl_configs = []
    for _, row in tfl_raw.iterrows():
        tfl_id = str(row.get("TFL ID", "")).strip()
        # Skip blank rows and legend/note rows — valid IDs match T-xx, F-xx, L-xx
        if not tfl_id or tfl_id.lower() == "nan":
            continue
        if not re.match(r'^[TFLtfl]-\d+', tfl_id):
            continue

        # Resolve dataset paths: prefer Datasets sheet mapping, fall back to
        # the filename column in the TFLs sheet directly.
        def resolve_ds(name_col, file_col):
            ds_name  = str(row.get(name_col, "")).strip()
            ds_fname = str(row.get(file_col, "")).strip()
            if ds_name and ds_name in dataset_map:
                return dataset_map[ds_name], ds_name
            if ds_fname and ds_fname.lower() not in ("", "nan"):
                return os.path.join(data_dir_abs, ds_fname), ds_name
            return "", ds_name

        primary_path, primary_name = resolve_ds("Primary Dataset", "Primary Filename")
        aux_path,     aux_name     = resolve_ds("Aux Dataset",     "Aux Filename")

        def s(col, default=""):
            v = row.get(col, default)
            return "" if pd.isna(v) else str(v).strip()

        shell_file = s("Shell Filename")
        shell_path = os.path.join(tfl_dir_abs, shell_file) if shell_file else ""

        cfg = {
            "tfl_id":           tfl_id,
            "title":            s("Title"),
            "tfl_type":         s("TFL Type", "Table"),
            "tfl_category":     s("TFL Category"),
            "validation_type":  s("Validation Type"),
            "file":             shell_path,
            "format":           s("Shell Format", "docx"),
            "dataset":          primary_path,
            "dataset_name":     primary_name,
            "population_filter": s("Population Filter"),
            "group_var":        s("Group Variable", "TRT01A"),
            "notes":            s("Notes"),
        }

        if aux_path:
            cfg["aux_dataset"]      = aux_path
            cfg["aux_dataset_name"] = aux_name

        listing_filter = s("Listing Filter")
        if listing_filter:
            cfg["listing_filter"] = listing_filter

        tfl_configs.append(cfg)

    # ── Column Mapping sheet (optional) ────────────────────────────────
    column_mappings = _load_column_mappings(xls)

    # ── Variable Mapping sheet (optional) ───────────────────────────────
    variable_mappings = _load_variable_mappings(xls)

    # ── Rounding Rules sheet (optional) ─────────────────────────────────
    rounding_rules = _load_rounding_rules(xls)

    # ── Merge per-TFL config enrichments ────────────────────────────────
    for cfg in tfl_configs:
        tid = cfg["tfl_id"]
        if tid in column_mappings:
            cfg["column_mapping"] = column_mappings[tid]
        if tid in variable_mappings:
            cfg["variable_mapping"] = variable_mappings[tid]
        # Rounding: merge global (*) with TFL-specific overrides
        rr = dict(rounding_rules.get("*", {}))
        rr.update(rounding_rules.get(tid, {}))
        if rr:
            cfg["rounding_rules"] = rr

    return {
        "study_info":         study_info,
        "tfl_configs":        tfl_configs,
        "tolerances":         tolerances,
        "treatment_order":    treatment_order,
        "validation_options": validation_options,
        "adam_specs_file":    abspath(specs_file),
        "data_dir":           data_dir_abs,
        "tfl_dir":            tfl_dir_abs,
    }


def _load_column_mappings(xls):
    """Load optional 'Column Mapping' sheet.

    Returns:
        dict: {tfl_id: [{table_idx, col_idx, pattern, treatment}]}
    """
    if "Column Mapping" not in xls.sheet_names:
        return {}
    df = pd.read_excel(xls, sheet_name="Column Mapping", header=0)
    df.columns = [str(c).strip() for c in df.columns]
    result = {}
    for _, row in df.iterrows():
        tid = str(row.get("TFL ID", "")).strip()
        if not tid or tid.lower() == "nan":
            continue
        entry = {
            "table_idx": int(row.get("Table Index", 0)) if pd.notna(row.get("Table Index")) else 0,
            "col_idx":   int(row.get("Column Index", 0)) if pd.notna(row.get("Column Index")) else None,
            "pattern":   str(row.get("Column Header Pattern", "")).strip() if pd.notna(row.get("Column Header Pattern")) else "",
            "treatment": str(row.get("Treatment Arm", "")).strip() if pd.notna(row.get("Treatment Arm")) else "",
        }
        result.setdefault(tid, []).append(entry)
    return result


def _load_variable_mappings(xls):
    """Load optional 'Variable Mapping' sheet.

    Returns:
        dict: {tfl_id: {var_type: [entries]}}
        where each entry has keys: variable_name, value, dataset, notes
    """
    if "Variable Mapping" not in xls.sheet_names:
        return {}
    df = pd.read_excel(xls, sheet_name="Variable Mapping", header=0)
    df.columns = [str(c).strip() for c in df.columns]
    result = {}
    for _, row in df.iterrows():
        tid = str(row.get("TFL ID", "")).strip()
        if not tid or tid.lower() == "nan":
            continue
        var_type = str(row.get("Variable Type", "")).strip().lower()
        if not var_type or var_type == "nan":
            continue
        entry = {
            "variable_name": str(row.get("Variable Name", "")).strip() if pd.notna(row.get("Variable Name")) else "",
            "value":         str(row.get("Value", "")).strip() if pd.notna(row.get("Value")) else "",
            "dataset":       str(row.get("Dataset", "")).strip() if pd.notna(row.get("Dataset")) else "",
            "notes":         str(row.get("Notes", "")).strip() if pd.notna(row.get("Notes")) else "",
        }
        result.setdefault(tid, {}).setdefault(var_type, []).append(entry)
    return result


def _load_rounding_rules(xls):
    """Load optional 'Rounding Rules' sheet.

    Returns:
        dict: {tfl_id: {stat_key: decimal_places}}
        '*' key is used for global defaults.
    """
    if "Rounding Rules" not in xls.sheet_names:
        return {}
    df = pd.read_excel(xls, sheet_name="Rounding Rules", header=0)
    df.columns = [str(c).strip() for c in df.columns]
    result = {}
    for _, row in df.iterrows():
        tid = str(row.get("TFL ID", "")).strip()
        if not tid or tid.lower() == "nan":
            continue
        stat = str(row.get("Statistic", "")).strip()
        dp = row.get("Decimal Places")
        if stat and pd.notna(dp):
            result.setdefault(tid, {})[stat.lower()] = int(dp)
    return result


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "study_config.xlsx"
    cfg = load_study_config(path)
    print(f"Study: {cfg['study_info']['study_id']}")
    print(f"TFLs loaded: {len(cfg['tfl_configs'])}")
    for t in cfg['tfl_configs']:
        print(f"  {t['tfl_id']:6s} [{t['tfl_type']:7s}] {t['title'][:60]}")
