"""Placeholder validator for tables without full data validation."""
import os
from ..engine.comparator import ValidationResult
from ._utils import parse_tfl


def validate_placeholder(tfl_cfg, audit):
    """Placeholder validator for TFLs without a full ADaM dataset (lab, vitals, etc.)."""
    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")
    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]

    tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
    audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
              f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")
    vr.add("Structure check", "Document exists", "Document parsed",
           len(tables) > 0,
           f"{'TFL document parsed successfully' if tables else 'No tables found in document'}",
           row_label="Document structure")
    print(f"  Structure check: {'PASS' if tables else 'FAIL'} ({len(tables)} table(s) found)")
    print(f"  Note: Full validation requires {tfl_cfg.get('dataset_name','ADaM')} dataset")
    return vr
