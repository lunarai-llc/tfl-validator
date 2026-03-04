"""Command-line interface for TFL Validator."""
import sys
import argparse
from .core import run_validation


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TFL Validator — Open-source validation engine for clinical trial TFLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tfl-validate --config study_config.xlsx
  tfl-validate --config study_config.xlsx --output my_report.xlsx
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to study_config.xlsx configuration file"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output Excel report path (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    try:
        results = run_validation(args.config, args.output)
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
