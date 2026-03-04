"""Comparator engine — matches TFL extracted values against recalculated values.
Supports fuzzy numeric comparison with configurable tolerance.
"""
import re
import numpy as np


def parse_numeric(s):
    """Extract numeric value from a string like '54.3', '124', '32.5%', '15 (37.5)', '<0.001'."""
    if s is None:
        return None
    s = str(s).strip()
    if s in ("", "-", "—", "N/A", "NA", "n/a"):
        return None

    # Handle "n (%)" format → return the n
    m = re.match(r'^(\d+)\s*\(', s)
    if m:
        return float(m.group(1))

    # Handle percentage in parentheses "n (xx.x)" or "n (xx.x%)"
    # Return as tuple (n, pct)
    m = re.match(r'^(\d+)\s*\(([\d.]+)%?\)', s)
    if m:
        return float(m.group(1))  # return the count

    # Handle "<0.001" etc
    m = re.match(r'^[<>]\s*([\d.]+)', s)
    if m:
        return float(m.group(1))

    # Handle plain number
    m = re.match(r'^-?[\d.]+', s.replace(",", ""))
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


def parse_pct_from_npct(s):
    """Extract percentage from 'n (xx.x)' or 'n (xx.x%)' format."""
    if s is None:
        return None
    m = re.search(r'\(([\d.]+)%?\)', str(s))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def compare_values(tfl_val, calc_val, tolerance=0.01, value_type="numeric"):
    """Compare a TFL value against a calculated value.
    Returns (match: bool, note: str).
    """
    if tfl_val is None and calc_val is None:
        return True, "Both missing"

    if tfl_val is None:
        return False, f"TFL value missing, calculated={calc_val}"
    if calc_val is None:
        return False, f"TFL={tfl_val}, calculated value missing"

    tfl_num = parse_numeric(str(tfl_val))
    calc_num = float(calc_val) if isinstance(calc_val, (int, float, np.integer, np.floating)) else parse_numeric(str(calc_val))

    if tfl_num is None or calc_num is None:
        # Fall back to string comparison
        s1 = str(tfl_val).strip().lower()
        s2 = str(calc_val).strip().lower()
        if s1 == s2:
            return True, "Exact string match"
        return False, f"String mismatch: TFL='{tfl_val}' vs Calc='{calc_val}'"

    diff = abs(tfl_num - calc_num)
    if diff <= tolerance:
        return True, f"Match within tolerance ({diff:.4f} <= {tolerance})"

    return False, f"MISMATCH: TFL={tfl_num} vs Calc={calc_num} (diff={diff:.4f})"


def compare_npct(tfl_val, calc_n, calc_pct, n_tol=0, pct_tol=0.15):
    """Compare 'n (pct)' formatted value against calculated n and percentage."""
    tfl_n = parse_numeric(str(tfl_val))
    tfl_pct = parse_pct_from_npct(str(tfl_val))

    issues = []
    match = True

    if tfl_n is not None and calc_n is not None:
        if abs(tfl_n - calc_n) > n_tol:
            match = False
            issues.append(f"n mismatch: TFL={int(tfl_n)} vs Calc={int(calc_n)}")
    elif tfl_n is None:
        issues.append("Could not parse n from TFL")
        match = False

    if tfl_pct is not None and calc_pct is not None:
        if abs(tfl_pct - calc_pct) > pct_tol:
            match = False
            issues.append(f"% mismatch: TFL={tfl_pct} vs Calc={calc_pct}")

    note = "; ".join(issues) if issues else f"n and % match (n={int(calc_n)}, %={calc_pct})"
    return match, note


class ValidationResult:
    """Collects comparison results for a single TFL."""
    def __init__(self, tfl_id, tfl_title):
        self.tfl_id = tfl_id
        self.tfl_title = tfl_title
        self.comparisons = []
        self.pass_count = 0
        self.fail_count = 0
        self.arm_stats = []   # for listings: [{"arm":..,"subjects":..,"events":..,"rate":..}]
        self.total_records = 0  # for listings: total source records

    def add(self, stat_name, tfl_value, calc_value, match, note, row_label="", col_label=""):
        self.comparisons.append({
            "stat_name": stat_name,
            "row_label": row_label,
            "col_label": col_label,
            "tfl_value": str(tfl_value) if tfl_value is not None else "",
            "calc_value": str(calc_value) if calc_value is not None else "",
            "match": match,
            "note": note,
        })
        if match:
            self.pass_count += 1
        else:
            self.fail_count += 1

    @property
    def total(self):
        return self.pass_count + self.fail_count

    @property
    def passed(self):
        return self.fail_count == 0

    @property
    def match_rate(self):
        return self.pass_count / self.total if self.total > 0 else 0

    def summary(self):
        return {
            "tfl_id": self.tfl_id,
            "tfl_title": self.tfl_title,
            "status": "PASS" if self.passed else "FAIL",
            "total_checks": self.total,
            "passed": self.pass_count,
            "failed": self.fail_count,
            "match_rate": f"{self.match_rate:.1%}",
        }


class ProtocolValidationResult:
    """Collects Protocol cross-validation results for a single TFL."""
    def __init__(self, tfl_id, tfl_title, category=""):
        self.tfl_id = tfl_id
        self.tfl_title = tfl_title
        self.category = category
        self.cross_validations = []
        self.issues = []
        self.warnings = []

    def add_check(self, check_name, expected, found, match, note=""):
        self.cross_validations.append({
            "check": check_name,
            "protocol_value": str(expected) if expected is not None else "",
            "tfl_value": str(found) if found is not None else "",
            "match": match,
            "note": note,
        })
        if not match:
            self.issues.append(f"{check_name}: {note}")

    def add_warning(self, message):
        self.warnings.append(message)

    @property
    def pass_count(self):
        return sum(1 for c in self.cross_validations if c["match"])

    @property
    def fail_count(self):
        return sum(1 for c in self.cross_validations if not c["match"])

    @property
    def total(self):
        return len(self.cross_validations)

    @property
    def passed(self):
        return self.fail_count == 0

    def summary(self):
        return {
            "tfl_id": self.tfl_id,
            "category": self.category,
            "status": "PASS" if self.passed else ("FAIL" if self.issues else "WARN"),
            "total_checks": self.total,
            "passed": self.pass_count,
            "failed": self.fail_count,
            "issues": self.issues,
            "warnings": self.warnings,
        }


class SAPValidationResult:
    """Collects SAP cross-validation results for a single TFL."""
    def __init__(self, tfl_id, tfl_title, category=""):
        self.tfl_id = tfl_id
        self.tfl_title = tfl_title
        self.category = category
        self.cross_validations = []
        self.issues = []
        self.warnings = []

    def add_check(self, check_name, sap_spec, tfl_value, match, note=""):
        self.cross_validations.append({
            "check": check_name,
            "sap_specification": str(sap_spec) if sap_spec is not None else "",
            "tfl_value": str(tfl_value) if tfl_value is not None else "",
            "match": match,
            "note": note,
        })
        if not match:
            self.issues.append(f"{check_name}: {note}")

    def add_warning(self, message):
        self.warnings.append(message)

    @property
    def pass_count(self):
        return sum(1 for c in self.cross_validations if c["match"])

    @property
    def fail_count(self):
        return sum(1 for c in self.cross_validations if not c["match"])

    @property
    def total(self):
        return len(self.cross_validations)

    @property
    def passed(self):
        return self.fail_count == 0

    def summary(self):
        return {
            "tfl_id": self.tfl_id,
            "category": self.category,
            "status": "PASS" if self.passed else ("FAIL" if self.issues else "WARN"),
            "total_checks": self.total,
            "passed": self.pass_count,
            "failed": self.fail_count,
            "issues": self.issues,
            "warnings": self.warnings,
        }
