"""ADaM Specifications Reader.
Parses an ADaM specs Excel file to extract variable metadata including:
  - Variable name, label, type (Num/Char), length, format
  - Controlled terms / codelists
  - Source / derivation logic
  - Core status (Req/Perm/Cond)

Supports two common layouts:
  1. Multi-sheet: one sheet per dataset (ADSL, ADAE, ADTTE)
  2. Single-sheet: all datasets in one sheet with a 'Dataset' column

Returns a structured dict: {dataset_name: {var_name: {...metadata...}}}
"""
import os
import pandas as pd


# Common column name aliases (specs files vary in naming conventions)
_COL_MAP = {
    "variable name": "variable",
    "variable": "variable",
    "var name": "variable",
    "name": "variable",
    "label": "label",
    "variable label": "label",
    "description": "label",
    "type": "type",
    "data type": "type",
    "length": "length",
    "len": "length",
    "format": "format",
    "display format": "format",
    "controlled terms": "codelist",
    "controlled terms / codelist": "codelist",
    "codelist": "codelist",
    "code list": "codelist",
    "source": "derivation",
    "source / derivation": "derivation",
    "derivation": "derivation",
    "derivation / comment": "derivation",
    "origin": "derivation",
    "comment": "derivation",
    "core": "core",
    "requirement": "core",
    "dataset": "dataset",
}

# Sheets to skip when reading multi-sheet specs files
_SKIP_SHEETS = {"overview", "cover", "toc", "table of contents", "readme", "notes", "changelog"}


def _normalize_col(col_name):
    """Map a column header to a canonical name."""
    clean = str(col_name).strip().lower()
    return _COL_MAP.get(clean, clean)


def _is_dataset_sheet(name):
    """Check if a sheet name looks like a dataset name (AD*)."""
    n = name.strip().upper()
    return n.startswith("AD") and n.lower() not in _SKIP_SHEETS


def _parse_sheet(df, dataset_name=None):
    """Parse a single sheet/dataframe into variable metadata dict.
    Returns: {var_name: {label, type, length, format, codelist, derivation, core, dataset}}
    """
    # Normalize column names
    col_map = {}
    for col in df.columns:
        norm = _normalize_col(col)
        if norm not in col_map.values():
            col_map[col] = norm
        else:
            col_map[col] = str(col).strip().lower()

    df = df.rename(columns=col_map)

    result = {}
    for _, row in df.iterrows():
        var_name = str(row.get("variable", "")).strip().upper()
        if not var_name or var_name == "NAN" or var_name == "":
            continue

        ds = dataset_name or str(row.get("dataset", "")).strip().upper()

        var_meta = {
            "variable": var_name,
            "label": str(row.get("label", "")).strip(),
            "type": str(row.get("type", "")).strip(),
            "length": row.get("length", ""),
            "format": str(row.get("format", "")).strip(),
            "codelist": str(row.get("codelist", "")).strip(),
            "derivation": str(row.get("derivation", "")).strip(),
            "core": str(row.get("core", "")).strip(),
            "dataset": ds,
        }

        # Clean up 'nan' strings from pandas
        for k, v in var_meta.items():
            if str(v).lower() == "nan":
                var_meta[k] = ""

        result[var_name] = var_meta

    return result


def read_adam_specs(filepath):
    """Read an ADaM specifications Excel file.

    Args:
        filepath: Path to the .xlsx specs file

    Returns:
        dict: {
            "datasets": {
                "ADSL": {
                    "AGE": {"variable": "AGE", "label": "Age (years)", "type": "Num", ...},
                    "SEX": {"variable": "SEX", "label": "Sex", "type": "Char", ...},
                    ...
                },
                "ADAE": {...},
                ...
            },
            "overview": {dataset_name: {description, structure, key_variables}},
            "filepath": str,
        }
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"ADaM specs file not found: {filepath}")

    xl = pd.ExcelFile(filepath)
    sheet_names = xl.sheet_names

    datasets = {}
    overview = {}

    # Check for overview sheet
    overview_sheet = None
    for sn in sheet_names:
        if sn.strip().lower() in _SKIP_SHEETS:
            overview_sheet = sn
            break

    # Try multi-sheet approach first (one sheet per dataset)
    dataset_sheets = [s for s in sheet_names if _is_dataset_sheet(s)]

    if dataset_sheets:
        # Multi-sheet layout
        for sheet in dataset_sheets:
            ds_name = sheet.strip().upper()
            df = pd.read_excel(filepath, sheet_name=sheet)
            if df.empty:
                continue
            datasets[ds_name] = _parse_sheet(df, dataset_name=ds_name)
    else:
        # Single-sheet layout — look for a 'Dataset' column
        for sheet in sheet_names:
            if sheet.strip().lower() in _SKIP_SHEETS:
                continue
            df = pd.read_excel(filepath, sheet_name=sheet)
            if df.empty:
                continue
            # Normalize columns to check for 'dataset' column
            norm_cols = {_normalize_col(c): c for c in df.columns}
            if "dataset" in norm_cols:
                ds_col = norm_cols["dataset"]
                for ds_name, group_df in df.groupby(ds_col):
                    ds_name = str(ds_name).strip().upper()
                    datasets[ds_name] = _parse_sheet(group_df, dataset_name=ds_name)
                break
            else:
                # Assume the sheet name is the dataset
                ds_name = sheet.strip().upper()
                if ds_name.startswith("AD"):
                    datasets[ds_name] = _parse_sheet(df, dataset_name=ds_name)

    # Parse overview sheet for dataset descriptions
    if overview_sheet:
        try:
            df_ov = pd.read_excel(filepath, sheet_name=overview_sheet)
            norm_cols = {_normalize_col(c): c for c in df_ov.columns}
            if "dataset" in norm_cols:
                ds_col_name = norm_cols.get("dataset", "")
                for _, row in df_ov.iterrows():
                    ds = str(row.get(ds_col_name, "")).strip().upper()
                    if ds.startswith("AD"):
                        overview[ds] = {
                            "description": str(row.get(norm_cols.get("description", ""), "")).strip(),
                            "structure": str(row.get(norm_cols.get("structure", ""), "")).strip(),
                        }
        except Exception:
            pass

    return {
        "datasets": datasets,
        "overview": overview,
        "filepath": filepath,
    }


def get_variable_info(specs, dataset_name, variable_name):
    """Convenience: get metadata for a specific variable.
    Returns the variable dict or None.
    """
    ds = specs.get("datasets", {}).get(dataset_name.upper(), {})
    return ds.get(variable_name.upper())


def get_derivation(specs, dataset_name, variable_name):
    """Get the derivation/source logic for a variable."""
    info = get_variable_info(specs, dataset_name, variable_name)
    return info.get("derivation", "") if info else ""


def get_label(specs, dataset_name, variable_name):
    """Get the variable label."""
    info = get_variable_info(specs, dataset_name, variable_name)
    return info.get("label", "") if info else ""


def get_type(specs, dataset_name, variable_name):
    """Get the variable type (Num/Char)."""
    info = get_variable_info(specs, dataset_name, variable_name)
    return info.get("type", "") if info else ""


def classify_variables(specs, dataset_name, variable_list):
    """Classify variables into continuous vs categorical based on specs type.

    Args:
        specs: Parsed specs dict from read_adam_specs()
        dataset_name: e.g. "ADSL"
        variable_list: list of variable names to classify

    Returns:
        {"continuous": [...], "categorical": [...]}
    """
    continuous = []
    categorical = []
    ds = specs.get("datasets", {}).get(dataset_name.upper(), {})
    for var in variable_list:
        info = ds.get(var.upper(), {})
        vtype = info.get("type", "").lower()
        if vtype in ("num", "numeric", "number", "float", "integer"):
            continuous.append(var)
        else:
            categorical.append(var)
    return {"continuous": continuous, "categorical": categorical}


def summarize_specs(specs):
    """Return a human-readable summary of loaded specs."""
    lines = []
    lines.append(f"ADaM Specs: {os.path.basename(specs.get('filepath', ''))}")
    for ds_name, variables in specs.get("datasets", {}).items():
        n_vars = len(variables)
        n_num = sum(1 for v in variables.values() if v.get("type", "").lower() in ("num", "numeric"))
        n_char = n_vars - n_num
        lines.append(f"  {ds_name}: {n_vars} variables ({n_num} numeric, {n_char} character)")
    return "\n".join(lines)
