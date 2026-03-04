"""Shared utilities for validators."""
import os
import re
import pandas as pd
from ..parsers.docx_parser import extract_tables as extract_docx_tables
from ..parsers.pdf_parser import extract_tables as extract_pdf_tables
from ..parsers.lst_parser import extract_tables as extract_lst_tables


def load_dataset(path, population_filter=None):
    """Load a CSV/Excel dataset and apply population filter."""
    if path.endswith(".csv"):
        df = pd.read_csv(path)
    elif path.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported data format: {path}")

    if population_filter:
        try:
            df = df.query(population_filter)
        except Exception as e:
            print(f"  Warning: Could not apply filter '{population_filter}': {e}")
    return df


def parse_tfl(filepath, fmt):
    """Parse a TFL file and return list of DataFrames."""
    if fmt == "docx":
        return extract_docx_tables(filepath)
    elif fmt == "pdf":
        return extract_pdf_tables(filepath)
    elif fmt in ("lst", "txt"):
        return extract_lst_tables(filepath)
    else:
        raise ValueError(f"Unsupported TFL format: {fmt}")


def build_treatment_column_map(tables, tfl_cfg):
    """Build treatment → column index mapping for a TFL.

    Strategy:
    1. If explicit column_mapping config exists → use it
    2. Otherwise → fall back to substring matching on treatment name in column headers

    Args:
        tables: List of DataFrames parsed from TFL
        tfl_cfg: TFL config dict (may contain 'column_mapping' key)

    Returns:
        dict: {treatment_name: col_idx}
    """
    col_mapping = tfl_cfg.get("column_mapping")

    if col_mapping:
        # Use explicit config-driven mapping
        result = {}
        for entry in col_mapping:
            trt = entry.get("treatment", "")
            col_idx = entry.get("col_idx")
            pattern = entry.get("pattern", "")
            table_idx = entry.get("table_idx", 0)

            if col_idx is not None and trt:
                result[trt] = col_idx
            elif pattern and trt and tables:
                # Try pattern matching against column headers
                tbl_idx = min(table_idx, len(tables) - 1)
                for ci, col in enumerate(tables[tbl_idx].columns):
                    if re.search(pattern, str(col), re.IGNORECASE):
                        result[trt] = ci
                        break
        if result:
            return result

    # Fallback: substring matching (current behavior)
    if not tables:
        return {}

    tbl = tables[0]
    tfl_cols = list(tbl.columns)

    # Get treatment list from data via group_var (passed in tfl_cfg context)
    # We need the caller to provide treatments; return mapping for what we can find
    result = {}
    # Try to match any treatment-like columns by looking for (N=XX) pattern
    for ci, col in enumerate(tfl_cols):
        col_str = str(col)
        # Store column index for any column with treatment-like content
        result[f"__col_{ci}"] = ci

    return result


def build_treatment_column_map_with_treatments(tables, tfl_cfg, treatments):
    """Build treatment → column index mapping using known treatment names.

    Args:
        tables: List of DataFrames parsed from TFL
        tfl_cfg: TFL config dict (may contain 'column_mapping' key)
        treatments: List of treatment arm names from data

    Returns:
        dict: {treatment_name: col_idx}
    """
    # First try config-driven mapping
    col_mapping = tfl_cfg.get("column_mapping")
    if col_mapping:
        result = {}
        for entry in col_mapping:
            trt = entry.get("treatment", "")
            col_idx = entry.get("col_idx")
            pattern = entry.get("pattern", "")
            table_idx = entry.get("table_idx", 0)

            if col_idx is not None and trt:
                result[trt] = col_idx
            elif pattern and trt and tables:
                tbl_idx = min(table_idx, len(tables) - 1)
                for ci, col in enumerate(tables[tbl_idx].columns):
                    if re.search(pattern, str(col), re.IGNORECASE):
                        result[trt] = ci
                        break
        if result:
            return result

    # Fallback: substring matching on treatment names in column headers
    if not tables:
        return {}

    tfl_cols = list(tables[0].columns)
    result = {}
    for trt in treatments:
        for ci, col in enumerate(tfl_cols):
            # Normalize whitespace (newlines, tabs) to spaces for matching
            col_normalized = " ".join(str(col).split())
            trt_normalized = " ".join(str(trt).split())
            if trt_normalized in col_normalized:
                result[trt] = ci
                break
    return result


def get_rounding_precision(tfl_cfg, var_name, stat_type):
    """Get rounding precision for a variable + statistic.

    Lookup order:
    1. TFL-specific: "{var}_{stat}" key (e.g., "age_mean")
    2. Global stat type: "{stat}" key (e.g., "mean")
    3. Hardcoded defaults

    Args:
        tfl_cfg: TFL config dict (may contain 'rounding_rules' key)
        var_name: Variable name (e.g., "AGE") — can be None
        stat_type: Statistic type (e.g., "mean", "sd", "percentage")

    Returns:
        int: number of decimal places
    """
    rounding_rules = tfl_cfg.get("rounding_rules", {})
    stat_lower = stat_type.lower()

    # 1. Try specific variable + stat
    if var_name:
        key = f"{var_name.lower()}_{stat_lower}"
        if key in rounding_rules:
            return rounding_rules[key]

    # 2. Try just stat type
    if stat_lower in rounding_rules:
        return rounding_rules[stat_lower]

    # 3. Hardcoded defaults
    defaults = {"mean": 1, "sd": 2, "median": 1, "percentage": 1, "min": 0, "max": 0, "count": 0}
    return defaults.get(stat_lower, 1)


def get_adam_flags(tfl_cfg):
    """Get ADaM flag variable names from config, with CDISC defaults.

    Returns:
        dict with keys: treatment_emergent, safety_pop, serious_ae, related_ae,
                        soc_var, pt_var, severity_var
              values: variable name strings
    """
    defaults = {
        "treatment_emergent": ("TRTEMFL", "Y"),
        "safety_pop":         ("SAFFL", "Y"),
        "serious_ae":         ("AESER", "Y"),
        "related_ae":         ("AEREL", ["RELATED", "POSSIBLY RELATED"]),
        "soc_var":            ("AEBODSYS", None),
        "pt_var":             ("AEDECOD", None),
        "severity_var":       ("AESEV", None),
    }

    var_mapping = tfl_cfg.get("variable_mapping", {})
    adam_flags = var_mapping.get("adam_flag", [])

    result = {}
    for purpose, (default_var, default_val) in defaults.items():
        result[purpose] = {"var": default_var, "value": default_val}

    # Override from config
    # Config entries map variable names to purposes
    var_to_purpose = {
        "TRTEMFL": "treatment_emergent", "TREATFL": "treatment_emergent",
        "SAFFL": "safety_pop", "FASFL": "safety_pop",
        "AESER": "serious_ae",
        "AEREL": "related_ae",
        "AEBODSYS": "soc_var",
        "AEDECOD": "pt_var",
        "AESEV": "severity_var", "AETOXGR": "severity_var",
    }

    for entry in adam_flags:
        var_name = entry.get("variable_name", "")
        value = entry.get("value", "")
        purpose = var_to_purpose.get(var_name)
        if purpose:
            result[purpose]["var"] = var_name
            if value:
                # Support comma-separated values (e.g., "PROBABLE,POSSIBLE")
                if "," in str(value):
                    result[purpose]["value"] = [v.strip() for v in str(value).split(",")]
                else:
                    result[purpose]["value"] = value
        else:
            # Unknown variable — store by variable name as purpose
            result[var_name] = {"var": var_name, "value": value if value else None}

    return result


def get_survival_params(tfl_cfg):
    """Get survival-specific ADaM parameters from config, with defaults.

    Returns:
        dict with keys: paramcd_var, paramcd_value, pop_flag_var, pop_flag_value,
                        censor_var, time_var
    """
    defaults = {
        "paramcd_var": "PARAMCD",
        "paramcd_value": "PFS",
        "pop_flag_var": "ITTFL",
        "pop_flag_value": "Y",
        "censor_var": "CNSR",
        "time_var": "AVAL",
    }

    var_mapping = tfl_cfg.get("variable_mapping", {})

    # Check survival_param entries
    for entry in var_mapping.get("survival_param", []):
        var_name = entry.get("variable_name", "")
        value = entry.get("value", "")
        if var_name.upper() == "PARAMCD" and value:
            defaults["paramcd_value"] = value
        elif var_name:
            defaults["paramcd_var"] = var_name
            if value:
                defaults["paramcd_value"] = value

    # Check survival_flag entries
    for entry in var_mapping.get("survival_flag", []):
        var_name = entry.get("variable_name", "")
        value = entry.get("value", "")
        if var_name:
            defaults["pop_flag_var"] = var_name
            if value:
                defaults["pop_flag_value"] = value

    return defaults


def get_continuous_vars(tfl_cfg, specs=None, ds_name=""):
    """Get list of continuous variables to validate from config, with defaults.

    Returns:
        list of variable names, and dict of {var: section_context_label}
    """
    var_mapping = tfl_cfg.get("variable_mapping", {})
    continuous_entries = var_mapping.get("continuous", [])

    if continuous_entries:
        # Config-driven
        var_list = [e["variable_name"] for e in continuous_entries if e.get("variable_name")]
        section_map = {}
        for e in continuous_entries:
            vn = e.get("variable_name", "")
            if vn:
                # Use notes as section context hint, or fall back to variable name
                section_map[vn] = e.get("notes", vn).split("(")[0].strip().lower() or vn.lower()
        return var_list, section_map

    # Fallback: use tfl_cfg continuous_vars or hardcoded defaults
    var_list = tfl_cfg.get("continuous_vars", [])
    section_map = {"AGE": "age", "BMI": "bmi"}

    # Enrich from specs if available
    if specs:
        for var in var_list:
            from ..parsers.adam_specs_reader import get_label
            lbl = get_label(specs, ds_name, var)
            if lbl:
                section_map[var] = lbl.split("(")[0].strip().lower()

    return var_list, section_map


def get_categorical_vars(tfl_cfg):
    """Get list of categorical variables to validate from config.

    Returns:
        list of variable names
    """
    var_mapping = tfl_cfg.get("variable_mapping", {})
    cat_entries = var_mapping.get("categorical", [])

    if cat_entries:
        return [e["variable_name"] for e in cat_entries if e.get("variable_name")]

    return tfl_cfg.get("categorical_vars", [])


def find_tfl_value(tables, stat_label, row_context, col_idx, section_context=None):
    """Search parsed TFL tables for a specific value.

    Supports two table layouts:
    - Two-text-column: [section] | [statistic] | [val1] | [val2] ...
      (e.g. demographics) — matches row_context against column 1 (exact)
    - Single-text-column: [category/row label] | [val1] | [val2] ...
      (e.g. AE summary, SOC/PT tables) — matches row_context as substring of column 0
    """
    for tbl in tables:
        in_section = section_context is None
        for _, row in tbl.iterrows():
            row_vals = [str(v).strip() for v in row.values]
            first_col = row_vals[0].lower() if row_vals else ""

            if section_context and first_col and first_col not in ("", " "):
                sc = section_context.lower()
                # Try exact substring match first, then try first-word match
                in_section = (sc in first_col or
                              first_col.split()[0].rstrip(",") in sc.split()[0] or
                              sc.split()[0] in first_col.split()[0].rstrip(","))

            if not in_section:
                continue

            if len(row_vals) > 1:
                # Primary: two-column-label tables (demographics) — match on col 1
                stat_col = row_vals[1].lower().strip()
                rc_lower = row_context.lower()
                # Exact match first, then startswith
                if rc_lower == stat_col or stat_col.startswith(rc_lower + " ") or stat_col.startswith(rc_lower + ","):
                    if col_idx < len(row_vals):
                        return row_vals[col_idx]

                # Fallback: single-column-label tables (AE summary, SOC/PT)
                # Use word-boundary-aware matching to avoid "male" matching "female"
                col0_lower = row_vals[0].lower()
                if rc_lower in col0_lower:
                    # Verify it's a word boundary match (not a substring of another word)
                    idx = col0_lower.find(rc_lower)
                    before_ok = (idx == 0 or not col0_lower[idx-1].isalpha())
                    after_idx = idx + len(rc_lower)
                    after_ok = (after_idx >= len(col0_lower) or not col0_lower[after_idx].isalpha())
                    if before_ok and after_ok:
                        if col_idx < len(row_vals):
                            return row_vals[col_idx]

    return None
