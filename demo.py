#!/usr/bin/env python3
"""Quick demo — run this to see TFL Validator in action.

Usage:
    python demo.py
"""
import os
import sys

# Add package to path
sys.path.insert(0, os.path.dirname(__file__))

from tfl_validator.core import run_validation

if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "study_config.xlsx")
    
    if not os.path.exists(config_path):
        print(f"ERROR: Configuration file not found at {config_path}")
        sys.exit(1)
    
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                      TFL Validator — Quick Demo                            ║
║                                                                            ║
║  This demo will:                                                           ║
║    1. Load the sample study configuration                                  ║
║    2. Validate 15 sample TFLs (demographics, AE, disposition, listings)    ║
║    3. Generate an Excel validation report                                  ║
║                                                                            ║
║  Output: sample_data/TFL_Validation_Report_YYYYMMDD_HHMMSS.xlsx           ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    run_validation(config_path)
    
    print("""
✓ Demo complete! Check sample_data/ for the generated report.
    """)
