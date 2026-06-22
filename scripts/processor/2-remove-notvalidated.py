"""
Standalone cleanup script: removes notValidated rows from a processed output CSV.

notValidated rows are evidences the relevant-evidence cap skipped (no AI call made) — see the
cap-skip branch in 1-main-parallel-script.py. They're intentionally left in the processor's
merged output for debugging/audit purposes, so removing them for final delivery is a separate,
deliberate step rather than an automatic part of the execution pipeline.

Usage:
    python scripts/processor/2-remove-notvalidated.py \
        --input-csv path/to/merged_output.csv \
        --output-csv path/to/cleaned_output.csv
"""
import argparse
import csv
import os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
from core.constants import RELEVANCE_TAG_NOT_VALIDATED


def _parse_args():
    parser = argparse.ArgumentParser(description="Remove notValidated rows from a processed output CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to the processed output CSV to clean")
    parser.add_argument("--output-csv", required=True, help="Path to write the cleaned CSV")
    return parser.parse_args()


def remove_not_validated(input_csv: str, output_csv: str) -> tuple[int, int]:
    """Write input_csv to output_csv with all Relevance Tag='notValidated' rows removed.

    Returns (total_rows, removed_rows).
    """
    output_dir = os.path.dirname(output_csv)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    total = 0
    removed = 0
    with open(input_csv, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError(f"'{input_csv}' has no header row.")
        if "Relevance Tag" not in reader.fieldnames:
            raise ValueError(f"'{input_csv}' is missing the 'Relevance Tag' column.")

        with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                total += 1
                if row.get("Relevance Tag") == RELEVANCE_TAG_NOT_VALIDATED:
                    removed += 1
                    continue
                writer.writerow(row)

    return total, removed


if __name__ == "__main__":
    args = _parse_args()

    print(f"📖 Reading: {args.input_csv}")
    total, removed = remove_not_validated(args.input_csv, args.output_csv)
    kept = total - removed

    print(f"\n{'=' * 60}")
    print(f"{'NOTVALIDATED CLEANUP SUMMARY':^60}")
    print(f"{'=' * 60}")
    print(f"Total rows read:         {total}")
    print(f"Removed (notValidated):  {removed}")
    print(f"Kept:                    {kept}")
    print(f"Output written to:       {args.output_csv}")
    print(f"{'=' * 60}")
