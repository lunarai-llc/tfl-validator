"""Core validation orchestrator."""
import os
import sys
import datetime
import pandas as pd

from .config_loader import load_study_config
from .engine.audit_logger import AuditLogger
from .parsers.adam_specs_reader import read_adam_specs
from .report.excel_report import generate_report
from .validators import (
    validate_demographics,
    validate_safety_ae,
    validate_ae_by_grade,
    validate_sae,
    validate_disposition,
    validate_survival_pfs,
    validate_listing,
    validate_placeholder,
)
from .validators.lab import validate_lab_summary
from .validators.vitals import validate_vitals_summary
from .validators.exposure import validate_exposure
from .validators.conmeds import validate_conmeds
from .validators.medhist import validate_medhist


def run_validation(config_path, output_path=None):
    """Main orchestrator: loads config, validates TFLs, generates reports.
    
    Args:
        config_path: Path to study_config.xlsx
        output_path: Optional output Excel report path
        
    Returns:
        List of ValidationResult objects
    """
    print(f"Loading config from: {config_path}")
    config = load_study_config(config_path)
    
    # Setup output path
    if output_path is None:
        base_dir = os.path.dirname(os.path.abspath(config_path))
        output_dir = os.path.join(base_dir, "sample_data")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"TFL_Validation_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
    
    study_info = config["study_info"]
    tfl_configs = config["tfl_configs"]
    tolerances = config["tolerances"]
    validation_options = config["validation_options"]
    
    print(f"\nStudy: {study_info['study_id']}")
    print(f"Title: {study_info['study_title']}")
    print(f"TFLs to validate: {len(tfl_configs)}")
    print(f"Output: {output_path}\n")
    
    # Load ADaM specs if available
    specs = None
    specs_file = config.get("adam_specs_file")
    if specs_file and os.path.exists(specs_file):
        print(f"Loading ADaM specs from: {specs_file}")
        specs = read_adam_specs(specs_file)
    else:
        print("No ADaM specs file provided")
    
    # Initialize audit logger
    audit = AuditLogger()
    audit.log("STUDY", "INIT", "run_validation()", f"Study: {study_info['study_id']}", 
              f"Starting validation of {len(tfl_configs)} TFLs")
    
    # Validate each TFL
    results = []
    print(f"\n{'='*70}")
    print("VALIDATION STARTING")
    print(f"{'='*70}")
    
    for tfl_cfg in tfl_configs:
        vtype = tfl_cfg.get("validation_type", "").lower()
        
        if not vtype:
            print(f"\nSkipping {tfl_cfg['tfl_id']}: no validation type specified")
            continue
        
        try:
            if vtype == "demographics":
                vr = validate_demographics(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype == "safety_ae":
                vr = validate_safety_ae(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype == "safety_ae_grade":
                vr = validate_ae_by_grade(tfl_cfg, audit, tolerances=tolerances)
            elif vtype == "safety_sae":
                vr = validate_sae(tfl_cfg, audit, tolerances=tolerances)
            elif vtype == "disposition":
                vr = validate_disposition(tfl_cfg, audit)
            elif vtype == "survival_pfs":
                vr = validate_survival_pfs(tfl_cfg, audit)
            elif vtype == "listing":
                vr = validate_listing(tfl_cfg, audit)
            elif vtype == "lab_summary":
                vr = validate_lab_summary(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype == "vitals_summary":
                vr = validate_vitals_summary(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype == "exposure":
                vr = validate_exposure(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype == "conmeds":
                vr = validate_conmeds(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype == "medhist":
                vr = validate_medhist(tfl_cfg, audit, specs=specs, tolerances=tolerances)
            elif vtype in ("lab_placeholder", "vitals_placeholder", "exposure_placeholder", "efficacy_placeholder"):
                vr = validate_placeholder(tfl_cfg, audit)
            else:
                print(f"\nSkipping {tfl_cfg['tfl_id']}: unknown validation type '{vtype}'")
                continue
            
            results.append(vr)
            s = vr.summary()
            print(f"\n  ── Result: {s['status']} ({s['passed']}/{s['total_checks']} checks passed) ──")
        
        except Exception as e:
            print(f"\nERROR validating {tfl_cfg['tfl_id']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*70}")
    print("VALIDATION SUMMARY")
    print(f"{'='*70}")
    total_pass = sum(1 for r in results if r.passed)
    total_fail = len(results) - total_pass
    print(f"  TFLs Validated:  {len(results)}")
    print(f"  PASSED:          {total_pass}")
    print(f"  FAILED:          {total_fail}")
    audit_summary = audit.summary()
    print(f"  Calculations:    {audit_summary['calculations']}")
    print(f"  Comparisons:     {audit_summary['comparisons']}")
    print(f"  Audit entries:   {audit_summary['total_entries']}")
    
    # Generate Excel report
    print(f"\nGenerating Excel report...")
    report_config = {
        "study_info": study_info,
        "tolerances": tolerances,
        "tfl_configs": tfl_configs,
        "adam_specs": specs,
        "validation_options": validation_options,
    }
    generate_report(results, audit, report_config, output_path)
    print(f"\n✓ Excel report saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TFL Validator — Core validation engine")
    parser.add_argument("--config", "-c", required=True, help="Path to study_config.xlsx")
    parser.add_argument("--output", "-o", default=None, help="Output Excel report path")
    args = parser.parse_args()
    
    run_validation(args.config, args.output)
