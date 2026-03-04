"""Parse tables from PDF TFL files into structured DataFrames."""
import pandas as pd
import pdfplumber


def extract_tables(filepath):
    """Extract all tables from a PDF file using pdfplumber.
    Returns a list of DataFrames, one per table found.
    """
    tables = []
    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            for t_idx, table_data in enumerate(page_tables):
                if not table_data or len(table_data) < 2:
                    continue
                header = [str(c).strip() if c else f"Col_{j}" for j, c in enumerate(table_data[0])]
                data = table_data[1:]
                # Clean cells
                clean_data = []
                for row in data:
                    clean_data.append([str(c).strip() if c else "" for c in row])
                df = pd.DataFrame(clean_data, columns=header)
                df.attrs["source_file"] = filepath
                df.attrs["page"] = page_num + 1
                df.attrs["table_index"] = t_idx
                tables.append(df)
    return tables


def extract_all_text(filepath):
    """Extract all text from a PDF file."""
    lines = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.append(text)
    return "\n".join(lines)
