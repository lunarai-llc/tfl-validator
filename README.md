# TFL Validator

Open-source validation engine for clinical trial **Tables, Figures & Listings (TFLs)**.

Independently recalculates statistics from ADaM datasets, compares against TFL outputs, and generates audit-ready validation reports — built for biostatisticians, statistical programmers, and CROs working under ICH E9 / 21 CFR Part 11.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the demo (validates 15 sample TFLs)
python demo.py

# Or use the CLI
tfl-validate --config study_config.xlsx --output my_report.xlsx
```

> 📊 **See what the output looks like before running anything** — check the [`examples/`](examples/) folder for a sample validation report (Excel) generated from the included synthetic dataset.

## What It Does

TFL Validator implements a complete validation pipeline:

1. **Load Configuration** — reads `study_config.xlsx` for study metadata, dataset paths, and TFL specifications
2. **Parse TFL Documents** — extracts tables from DOCX, PDF, and TXT files using intelligent document parsing
3. **Load ADaM Data** — imports CDISC ADaM datasets (CSV/Excel format)
4. **Recalculate Statistics** — independently computes:
   - Descriptive statistics (mean, SD, median, min/max)
   - Frequency distributions (n/%)
   - Adverse event summaries (SOC/PT, grades, SAE, relatedness)
   - Subject counts by treatment arm
5. **Compare Values** — matches calculated statistics against TFL values with configurable tolerances
6. **Generate Report** — creates an Excel workbook with:
   - Executive summary (TFLs passed/failed)
   - Per-TFL validation details and cell-by-cell comparisons
   - Complete audit trail (every calculation and comparison logged)
   - ADaM specifications reference

## Supported Validation Types

| Type | Description | Example |
|------|-------------|---------|
| `demographics` | Baseline characteristics table | Age, BMI, Race, Sex distributions by treatment |
| `safety_ae` | Adverse events summary | % subjects with any TEAE, by SOC/PT, relatedness |
| `safety_ae_grade` | AE by severity grade | Grade 1-2, 3, 4+ distributions |
| `safety_sae` | Serious adverse events | SAE counts by treatment and SOC |
| `disposition` | Subject enrollment/discontinuation | N enrolled, N safety population by arm |
| `listing` | Subject-level listings | AE listings, deaths, protocol deviations (row count check) |
| `lab_placeholder` | Lab results (structural check only) | Lab tables without full ADaM validation |
| `vitals_placeholder` | Vital signs (structural check only) | Vital sign tables (partial support) |

## Excel-Driven Configuration

No Python coding required. All study setup happens in **`study_config.xlsx`**:

### Study Info sheet
Define study metadata and file locations:
```
Study ID                  XYZ-2025-01
Study Title               A Phase III RCT in Indication X
Protocol Number           XYZ-001
Sponsor                   Example Corp
Base Data Directory       sample_data/
TFL Shell Directory       sample_data/sample_tfls/
ADaM Specs File          sample_data/adam_specs.xlsx
```

### Datasets sheet
Map dataset names to files:
```
Dataset Name  |  Filename
ADSL          |  adsl.csv
ADAE          |  adae.csv
ADTTE         |  adtte.csv
```

### TFLs sheet
Configure each TFL to validate:
```
TFL ID  |  Title           |  Validation Type  |  Shell Filename      |  Primary Dataset
T-01    |  Demographics    |  demographics     |  T14.1.1_demog.docx  |  ADSL
T-02    |  Disposition     |  disposition      |  T14.1.2_disp.docx   |  ADSL
T-03    |  AE Summary      |  safety_ae        |  T14.3.1_ae.docx     |  ADAE (Aux: ADSL)
L-01    |  AE Listing      |  listing          |  L16.2.7.1_ae.docx   |  ADAE
```

## Output

**Excel Report** (`TFL_Validation_Report_YYYYMMDD_HHMMSS.xlsx`):

- **SUMMARY** — Study info, TFL pass/fail counts, audit trail statistics
- **[TFL ID] DETAILS** — Per-TFL validation results:
  - Comparison table (TFL Value vs Calculated Value vs Tolerance vs Match)
  - Calculation details and formulas
  - Notes and warnings
- **AUDIT TRAIL** — Chronological log of all calculations and comparisons
- **ADAM SPECS** — Variable definitions and derivations (if specs provided)

## Project Structure

```
tfl-validator-oss/
├── README.md                    # This file
├── LICENSE                      # MIT
├── pyproject.toml              # Package metadata
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git exclude rules
├── demo.py                     # One-command demo
├── study_config.xlsx           # Study configuration (edit this for your study)
│
├── tfl_validator/              # Main package
│   ├── __init__.py
│   ├── cli.py                  # Command-line interface
│   ├── core.py                 # Main orchestrator
│   ├── config_loader.py        # Excel config reader
│   ├── engine/
│   │   ├── audit_logger.py     # Audit trail logging
│   │   └── comparator.py       # Value comparison logic
│   ├── parsers/
│   │   ├── docx_parser.py      # DOCX table extraction
│   │   ├── pdf_parser.py       # PDF table extraction
│   │   ├── lst_parser.py       # TXT/listing parser
│   │   └── adam_specs_reader.py # CDISC specs reader
│   ├── stats/
│   │   ├── descriptive.py      # Descriptive stats (mean, SD, freq)
│   │   ├── safety.py           # AE summary calculations
│   │   ├── inferential.py      # P-values, CIs
│   │   └── survival.py         # Kaplan-Meier, median survival
│   ├── validators/
│   │   ├── demographics.py     # Demographics validator
│   │   ├── safety_ae.py        # AE validator
│   │   ├── disposition.py      # Disposition validator
│   │   ├── listing.py          # Listing validator
│   │   └── placeholder.py      # Placeholder validator
│   ├── rules/
│   │   └── tfl_type_rules.py   # TFL type classification
│   └── report/
│       └── excel_report.py     # Excel report generator
│
├── sample_data/                # Sample study data
│   ├── adsl.csv                # Subject-level dataset
│   ├── adae.csv                # Adverse events dataset
│   ├── adtte.csv               # Time-to-event dataset
│   ├── adam_specs.xlsx         # CDISC specifications
│   └── sample_tfls/            # Example TFL documents
│       ├── T14.1.1_demog.docx
│       ├── T14.1.2_disposition.docx
│       ├── T14.3.1_AE_summary.docx
│       └── ...
│
└── tests/
    └── test_basic.py           # Basic smoke tests
```

## Configuration Reference

### Tolerances

Set acceptable differences between TFL and calculated values (in `study_config.xlsx` Study Info sheet):

| Parameter | Default | Units | Meaning |
|-----------|---------|-------|---------|
| Count (integers) | 0 | absolute | Exact match required |
| Mean | 0.15 | relative | ±15% difference allowed |
| SD | 0.05 | relative | ±5% difference allowed |
| Median | 0.15 | relative | ±15% difference allowed |
| Percentage | 0.15 | relative | ±15 percentage points |
| P-value | 0.005 | absolute | ±0.005 difference |
| Min/Max | 0.5 | absolute | ±0.5 units |

### Population Filters

Apply ADaM population filters (e.g., "SAFFL == 'Y'") in the TFLs sheet "Population Filter" column to subset data before calculations.

### Treatment Arm Order

Specify the order of treatment arms (Arm 1, Arm 2, ..., Arm 8) for consistent report formatting.

## Limitations

This open-source version **does not support**:

- **Complex TFL parsing**: tables with merged cells, nested headers, or non-standard layouts may require manual adjustment
- **Non-standard variable names**: assumes CDISC ADaM naming conventions (USUBJID, TRT01A, TRTEMFL, AESER, etc.)
- **MMRM models**: analysis of continuous endpoints using mixed models
- **Protocol/SAP cross-validation**: comparison against protocol-specified analyses (Pro feature)
- **SAS code generation**: automated SAS program generation (Pro feature)
- **Interactive portal**: sponsor/CRO portal (Pro feature)
- **Derivation validation**: complex ADaM derivations may need manual review

For advanced features, see the **Pro Version** below.

## Running Tests

```bash
python tests/test_basic.py
```

## Pro Version

For advanced features including:

- **Interactive Sponsor Portal** — Web-based dashboard for results review and sign-off
- **Protocol & SAP Validation** — Automatic comparison against protocol-specified analyses
- **SAS Code Generation** — Generate SAS validation programs from TFL specs
- **Advanced Parsing** — Handle complex, non-standard TFL layouts
- **Priority Support** — Direct support from Lunar AI team

Contact: **info@lunarai.llc** | [lunarai.llc](https://lunarai.llc)

## Development

Install dev dependencies:
```bash
pip install -e ".[dev]"
```

Run tests:
```bash
pytest tests/
```

Format code:
```bash
black tfl_validator/
isort tfl_validator/
```

## License

MIT License — See [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

- **GitHub Issues** — Bug reports and feature requests: https://github.com/lunarai-llc/tfl-validator/issues
- **Documentation** — Full guide: https://github.com/lunarai-llc/tfl-validator/blob/main/README.md
- **Email** — For questions: info@lunarai.llc

## Citation

If you use TFL Validator in your research or regulatory submissions, please cite:

```
TFL Validator (2026). Open-source validation engine for clinical trial TFLs.
Lunar AI LLC. https://github.com/lunarai-llc/tfl-validator
```

---

**Built with care for biostatisticians, statistical programmers, and CROs.**

*TFL Validator is not affiliated with CDISC. CDISC and ADaM are registered trademarks of CDISC.*
