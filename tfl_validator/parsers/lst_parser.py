"""Parse tables from SAS .lst text output files into structured DataFrames."""
import pandas as pd
import re


def extract_tables(filepath):
    """Parse SAS .lst output into DataFrames.
    SAS .lst files are fixed-width text with dashes separating headers from data.
    """
    with open(filepath, "r") as f:
        content = f.read()

    tables = []
    # Split on form feeds or multiple blank lines (table boundaries)
    sections = re.split(r'\n{3,}|\f', content)

    for s_idx, section in enumerate(sections):
        lines = [l.rstrip() for l in section.split("\n") if l.strip()]
        if len(lines) < 3:
            continue

        # Look for header separator (line of dashes or underscores)
        header_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^[\s\-_=]+$', line) and len(line.strip()) > 5:
                header_idx = i
                break

        if header_idx is not None and header_idx > 0:
            # Header is the line(s) before the separator
            header_line = lines[header_idx - 1]
            data_lines = lines[header_idx + 1:]
        else:
            # Assume first line is header
            header_line = lines[0]
            data_lines = lines[1:]

        # Parse fixed-width columns based on header spacing
        headers = header_line.split()
        if not headers or len(headers) < 2:
            continue

        rows = []
        for line in data_lines:
            if re.match(r'^[\s\-_=]+$', line):
                continue
            cells = line.split()
            if len(cells) >= len(headers) - 1:  # allow slight mismatch
                # Pad or trim to match header count
                while len(cells) < len(headers):
                    cells.append("")
                rows.append(cells[:len(headers)])

        if rows:
            df = pd.DataFrame(rows, columns=headers)
            df.attrs["source_file"] = filepath
            df.attrs["section_index"] = s_idx
            tables.append(df)

    return tables


def extract_all_text(filepath):
    """Read raw text from a .lst file."""
    with open(filepath, "r") as f:
        return f.read()
