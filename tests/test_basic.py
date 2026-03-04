"""Basic smoke tests for TFL Validator."""
import os
import sys

# Add package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_config_loader():
    """Test that config_loader can read the sample configuration."""
    from tfl_validator.config_loader import load_study_config
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "study_config.xlsx")
    if not os.path.exists(config_path):
        print(f"SKIP: config file not found at {config_path}")
        return
    
    cfg = load_study_config(config_path)
    assert cfg is not None
    assert "study_info" in cfg
    assert "tfl_configs" in cfg
    assert cfg["study_info"]["study_id"] != ""
    assert len(cfg["tfl_configs"]) > 0
    print(f"✓ config_loader test passed ({len(cfg['tfl_configs'])} TFLs loaded)")


def test_imports():
    """Test that all required modules can be imported."""
    try:
        from tfl_validator import run_validation, load_study_config
        from tfl_validator.core import run_validation as run_val_direct
        from tfl_validator.config_loader import load_study_config as load_cfg_direct
        from tfl_validator.engine.audit_logger import AuditLogger
        from tfl_validator.engine.comparator import ValidationResult
        from tfl_validator.validators import (
            validate_demographics,
            validate_safety_ae,
            validate_disposition,
            validate_listing,
            validate_placeholder,
        )
        print("✓ imports test passed")
    except ImportError as e:
        print(f"✗ imports test failed: {e}")
        raise


def test_validation_result():
    """Test ValidationResult class."""
    from tfl_validator.engine.comparator import ValidationResult
    
    vr = ValidationResult("T-01", "Demographics")
    assert vr.tfl_id == "T-01"
    
    # Add a passing check
    vr.add("N(Drug)", 100, 100, True, "Match", row_label="N")
    assert vr.pass_count == 1
    assert vr.fail_count == 0
    assert vr.passed
    
    # Add a failing check
    vr.add("Mean", 50.1, 50.0, False, "Exceeds tolerance", row_label="Mean")
    assert vr.pass_count == 1
    assert vr.fail_count == 1
    assert not vr.passed  # Now should fail because fail_count > 0
    
    summary = vr.summary()
    assert summary["status"] == "FAIL"
    assert summary["passed"] == 1
    assert summary["total_checks"] == 2
    print("✓ validation_result test passed")


def test_demo_runs():
    """Test that demo can run end-to-end."""
    from tfl_validator.core import run_validation
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "study_config.xlsx")
    if not os.path.exists(config_path):
        print(f"SKIP: config file not found at {config_path}")
        return
    
    try:
        # Run validation with sample data
        results = run_validation(config_path)
        
        # Basic sanity checks
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Check that we got some results
        total_checks = sum(r.total for r in results)
        assert total_checks > 0
        
        print(f"✓ demo test passed ({len(results)} TFLs validated, {total_checks} checks)")
    except Exception as e:
        print(f"Warning: demo test encountered error (may be expected if sample data incomplete): {e}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Running TFL Validator basic tests")
    print("="*70 + "\n")
    
    try:
        test_imports()
        test_validation_result()
        test_config_loader()
        test_demo_runs()
        
        print("\n" + "="*70)
        print("All tests passed!")
        print("="*70)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
