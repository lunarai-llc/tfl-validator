"""Audit Logger — records every computation step for regulatory traceability.
Each log entry captures: timestamp, TFL ID, statistic name, source code reference,
code logic description, input data summary, computed result, and comparison outcome.

Source references point to exact file, function, and line numbers so auditors
can trace any calculation back to the code that produced it.
"""
import datetime
import inspect
import os


# Project root for making paths relative
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_caller_info(stack_depth=2):
    """Inspect the call stack to capture the source file, function, and line number
    of the code that invoked the audit log.
    Returns dict with source_file, function, line_start, line_end, and source_snippet.
    """
    frame = inspect.stack()[stack_depth]
    abs_path = os.path.abspath(frame.filename)
    rel_path = os.path.relpath(abs_path, _PROJECT_ROOT) if abs_path.startswith(_PROJECT_ROOT) else abs_path
    func_name = frame.function
    lineno = frame.lineno

    # Try to get the full function source code range
    line_start = lineno
    line_end = lineno
    source_snippet = ""
    try:
        source_lines, start_line = inspect.getsourcelines(frame[0].f_code)
        line_start = start_line
        line_end = start_line + len(source_lines) - 1
        # Get a short snippet around the call site (±2 lines)
        call_offset = lineno - start_line
        snippet_start = max(0, call_offset - 1)
        snippet_end = min(len(source_lines), call_offset + 2)
        snippet_lines = source_lines[snippet_start:snippet_end]
        source_snippet = "".join(snippet_lines).strip()
        # Truncate if too long
        if len(source_snippet) > 300:
            source_snippet = source_snippet[:300] + "..."
    except (OSError, TypeError):
        pass

    return {
        "source_file": rel_path,
        "function": func_name,
        "line_number": lineno,
        "line_range": f"L{line_start}-L{line_end}",
        "source_ref": f"{rel_path}::{func_name}() [L{lineno}]",
        "source_snippet": source_snippet,
    }


class AuditLogger:
    def __init__(self):
        self.entries = []
        self._entry_num = 0

    def log(self, tfl_id, stat_name, code_description, input_summary, result,
            variable=None, dataset=None, population_filter=None):
        """Log a calculation step with automatic source code reference.

        Args:
            tfl_id: Which TFL this calculation belongs to
            stat_name: Name of the statistic being computed
            code_description: Short description of the computation logic (e.g. pandas expression)
            input_summary: Summary of input data (row counts, shape, etc.)
            result: The computed result
            variable: ADaM variable name
            dataset: Source dataset name
            population_filter: Population filter applied
        """
        caller = _get_caller_info(stack_depth=2)
        self._entry_num += 1
        self.entries.append({
            "entry_num": self._entry_num,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "tfl_id": tfl_id,
            "statistic": stat_name,
            "variable": variable or "",
            "dataset": dataset or "",
            "population_filter": population_filter or "",
            "source_file": caller["source_file"],
            "function": caller["function"],
            "line_number": caller["line_number"],
            "line_range": caller["line_range"],
            "source_ref": caller["source_ref"],
            "source_snippet": caller["source_snippet"],
            "code_description": code_description,
            "input_summary": str(input_summary)[:500],
            "result": str(result),
        })
        return self._entry_num

    def log_comparison(self, tfl_id, stat_name, tfl_value, calc_value, match, tolerance, note=""):
        """Log a comparison step (TFL value vs calculated value)."""
        caller = _get_caller_info(stack_depth=2)
        self._entry_num += 1
        self.entries.append({
            "entry_num": self._entry_num,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "tfl_id": tfl_id,
            "statistic": stat_name,
            "variable": "",
            "dataset": "",
            "population_filter": "",
            "source_file": caller["source_file"],
            "function": caller["function"],
            "line_number": caller["line_number"],
            "line_range": caller["line_range"],
            "source_ref": caller["source_ref"],
            "source_snippet": "",
            "code_description": f"COMPARE: TFL='{tfl_value}' vs Calc='{calc_value}' | tol={tolerance}",
            "input_summary": f"TFL value: {tfl_value}, Calculated: {calc_value}",
            "result": f"{'PASS' if match else 'FAIL'}{' — ' + note if note else ''}",
        })

    def get_entries(self):
        return self.entries

    def summary(self):
        total = len(self.entries)
        calcs = sum(1 for e in self.entries if not e["code_description"].startswith("COMPARE"))
        comps = total - calcs
        passes = sum(1 for e in self.entries if e["result"].startswith("PASS"))
        fails = sum(1 for e in self.entries if e["result"].startswith("FAIL"))
        return {
            "total_entries": total,
            "calculations": calcs,
            "comparisons": comps,
            "passes": passes,
            "fails": fails,
        }
