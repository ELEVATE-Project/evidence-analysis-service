"""
Standalone pre-pre-processing script: splits a row whose evidence-URL cell contains
multiple URLs into one row per URL, duplicating every other column's value unchanged.

Some source CSVs (e.g. observation/survey exports) pack more than one evidence URL into
a single cell for a row, comma-separated (or otherwise delimited) — e.g.
"https://.../a.jpg, https://.../b.jpg". 1-pre-processor.py and 1-main-parallel-script.py
both assume exactly one evidence URL per row (school-filter, task matching, evidence-type
detection, resume/dedup keys all key off a single evidence value), so a multi-URL cell
would either be skipped as an invalid evidence URL or silently misprocessed as one lump
string. This script normalizes such a CSV into the single-evidence-per-row shape the rest
of the pipeline expects, before it reaches 1-pre-processor.py.

URLs are found with a regex (not a fixed delimiter) so any separator — comma, whitespace,
pipe — works and a URL whose own query string happens to contain a comma isn't split
incorrectly. A cell with 0 or 1 URLs is left completely unchanged (byte-for-byte same row),
so this is a no-op for every input that doesn't actually have the multi-URL problem —
which is the common case today.

Usage:
    python scripts/pre-processor/0-split-multi-evidence.py \
        --input-csv path/to/input.csv \
        --output-csv path/to/split_input.csv
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path

# Allow importing from the service package (core/, etc.) — mirrors 1-pre-processor.py
SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
from core.constants import DEFAULT_EVIDENCE_COLUMN

# Same as scripts/processor/2-remove-nonvalidated-and-empty-evidences.py's URL_PATTERN,
# plus excluding ',' — that script only uses its matches for a log-line count, where a
# trailing delimiter comma stuck to the URL doesn't matter. Here the extracted value
# becomes the actual evidence URL for a new row, so "url1, url2" must not leave a
# trailing comma on "url1".
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\],]+')


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Split rows whose evidence-URL cell holds multiple URLs into one row per URL."
    )
    parser.add_argument("--input-csv", required=True, help="Path to the raw input CSV")
    parser.add_argument("--output-csv", required=True, help="Path to write the split CSV")
    parser.add_argument(
        "--evidence-column",
        default=None,
        help="Evidence-URL column in the input CSV (per-tenant, from "
        "CsvSourceType.evidence_columns[0].column); absent = core.constants default",
    )
    return parser.parse_args()


def split_multi_evidence(
    input_csv: str, output_csv: str, evidence_column: str = DEFAULT_EVIDENCE_COLUMN
) -> tuple[int, int, int]:
    """Write input_csv to output_csv with multi-URL evidence rows split into one row per URL.

    Returns (total_rows_in, total_rows_out, rows_split) where rows_split counts only the
    original rows that actually contained more than one URL (not the resulting row count).
    """
    output_dir = os.path.dirname(output_csv)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    total_in = 0
    total_out = 0
    rows_split = 0
    with open(input_csv, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError(f"'{input_csv}' has no header row.")
        if evidence_column not in reader.fieldnames:
            raise ValueError(f"'{input_csv}' is missing column: {evidence_column}")

        with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                total_in += 1
                raw_evidence = row.get(evidence_column) or ""
                urls = URL_PATTERN.findall(raw_evidence)

                if len(urls) <= 1:
                    # 0 URLs (empty/null cell) or exactly 1 URL: pass through unchanged so
                    # 1-pre-processor.py's existing null/invalid-URL handling is untouched.
                    writer.writerow(row)
                    total_out += 1
                    continue

                rows_split += 1
                for url in urls:
                    split_row = dict(row)
                    split_row[evidence_column] = url
                    writer.writerow(split_row)
                    total_out += 1

    return total_in, total_out, rows_split


if __name__ == "__main__":
    args = _parse_args()
    evidence_column = (
        (args.evidence_column or "").strip()
        or (os.getenv("SPLIT_EVIDENCE_COLUMN", "") or "").strip()
        or DEFAULT_EVIDENCE_COLUMN
    )

    print(f"📖 Reading: {args.input_csv}")
    print(f"   EVIDENCE_COLUMN: {evidence_column}")
    total_in, total_out, rows_split = split_multi_evidence(
        args.input_csv, args.output_csv, evidence_column=evidence_column
    )

    print(f"\n{'=' * 60}")
    print(f"{'MULTI-EVIDENCE SPLIT SUMMARY':^60}")
    print(f"{'=' * 60}")
    print(f"Total rows read:                 {total_in}")
    print(f"Rows with multiple evidence URLs: {rows_split}")
    print(f"Total rows written:              {total_out}")
    print(f"Output written to:               {args.output_csv}")
    print(f"{'=' * 60}")
