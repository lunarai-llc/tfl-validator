"""TFL Validator — Open-source validation engine for clinical trial TFLs.

This package provides tools for:
  - Parsing TFL documents (DOCX, PDF, TXT)
  - Loading and analyzing ADaM datasets
  - Calculating table statistics
  - Comparing TFL outputs against calculated values
  - Generating audit-ready Excel reports

Core API:
  from tfl_validator.core import run_validation
  results = run_validation("study_config.xlsx")
"""

__version__ = "1.0.0"
__author__ = "Lunar AI"
__license__ = "MIT"

from .core import run_validation
from .config_loader import load_study_config

__all__ = ["run_validation", "load_study_config"]
