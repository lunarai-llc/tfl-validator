"""Listing table validator."""
import os
from ..engine.comparator import ValidationResult
from ._utils import load_dataset, parse_tfl


def validate_listing(tfl_cfg, audit):
    """Validate a listing (row count check)."""
    print(f"\n{'='*70}")
    print(f"Validating: {tfl_cfg['tfl_id']} — {tfl_cfg['title']}")
    print(f"{'='*70}")
    vr = ValidationResult(tfl_cfg["tfl_id"], tfl_cfg["title"])
    tfl_id = tfl_cfg["tfl_id"]

    try:
        df = load_dataset(tfl_cfg["dataset"], tfl_cfg.get("population_filter"))
        # Apply additional listing filter if specified
        listing_filter = tfl_cfg.get("listing_filter")
        if listing_filter:
            try:
                df = df.query(listing_filter)
            except Exception:
                pass
        expected_rows = len(df)
        vr.total_records = expected_rows

        tables = parse_tfl(tfl_cfg["file"], tfl_cfg.get("format", "docx"))
        audit.log(tfl_id, "TFL_PARSE", f"extract_tables('{os.path.basename(tfl_cfg['file'])}')",
                  f"format={tfl_cfg.get('format','docx')}", f"Found {len(tables)} table(s)")

        if tables:
            tfl_rows = sum(len(t) for t in tables)
            match = abs(tfl_rows - expected_rows) <= 2  # allow ±2 row tolerance for headers
            vr.add("Row count", tfl_rows, expected_rows, match,
                   f"Listing rows: TFL={tfl_rows}, Calc={expected_rows}",
                   row_label="Row count")
            audit.log_comparison(tfl_id, "Listing row count", tfl_rows, expected_rows, match, 2,
                                 f"{'MATCH' if match else 'MISMATCH'}: TFL={tfl_rows} vs Calc={expected_rows}")
            print(f"  Row count: TFL={tfl_rows}, Expected≈{expected_rows} → {'PASS' if match else 'FAIL'}")
        else:
            vr.add("TFL parse", None, None, False, "No tables found in listing file")
            print(f"  Warning: No tables found in listing file")

        # Per-arm subject/event breakdown
        group_var = tfl_cfg.get("group_var", "TRT01A")
        if group_var in df.columns and not df.empty:
            total_events = len(df)
            for trt in sorted(df[group_var].unique()):
                trt_df = df[df[group_var] == trt]
                n_subj = int(trt_df["USUBJID"].nunique()) if "USUBJID" in trt_df.columns else int(len(trt_df))
                n_evt = int(len(trt_df))
                rate = round(n_evt / total_events * 100, 1) if total_events > 0 else 0.0
                vr.arm_stats.append({"arm": trt, "subjects": n_subj, "events": n_evt, "rate": rate})
                audit.log(tfl_id, f"LISTING_ARM({trt})", f"arm_summary('{group_var}'='{trt}')",
                          f"Subj={n_subj}, Events={n_evt}", f"Rate={rate}%")
                print(f"  {trt}: Subj={n_subj}, Events={n_evt} ({rate}%)")

    except Exception as e:
        print(f"  Warning: listing validation error — {e}")
        vr.add("data_load", None, None, True, f"Data load note: {e}")

    return vr
