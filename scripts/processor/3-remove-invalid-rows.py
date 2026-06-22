"""
Standalone cleanup script: removes rows with no AI-evaluation result from a processed output CSV.

A row ends up with an empty 'Task evidence Q and A' / 'Task evidence Q and A Reason' when the
processor never got a usable AI answer for it — see 1-main-parallel-script.py's skip paths: no
question found for the task ("User-Owned"), the relevant-evidence cap was reached ("Capped",
tag=notValidated), the AI response was invalid ("Failed"), or the evidence type was unsupported
("Unsupported"). These rows carry no evaluation signal, so removing them for final delivery is a
separate, deliberate step rather than an automatic part of the execution pipeline — same reasoning
as 2-remove-notvalidated.py, but broader: this also catches Failed/Unsupported/User-Owned rows that
script 2 leaves behind because their Relevance Tag isn't 'notValidated'.

Usage:
    python scripts/processor/3-remove-invalid-rows.py \
        --input-csv path/to/merged_output.csv \
        --output-csv path/to/cleaned_output.csv
"""
import argparse
import csv
import os
import re

CHECK_COLUMNS = ("Task evidence Q and A", "Task evidence Q and A Reason")
URL_COLUMN = "Task Evidence"
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Remove rows with no AI-evaluation result (blank Q&A/reason) from a processed output CSV."
    )
    parser.add_argument("--input-csv", required=True, help="Path to the processed output CSV to clean")
    parser.add_argument("--output-csv", required=True, help="Path to write the cleaned CSV")
    return parser.parse_args()


def remove_invalid_rows(input_csv: str, output_csv: str) -> tuple[int, int, list[str]]:
    """Write input_csv to output_csv with rows missing both Q&A columns removed.

    Returns (total_rows, removed_rows, extracted_urls) — extracted_urls are pulled from the
    removed rows' Task Evidence column, for visibility into what evidence never got evaluated.
    """
    output_dir = os.path.dirname(output_csv)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    total = 0
    removed = 0
    extracted_urls: list[str] = []
    with open(input_csv, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError(f"'{input_csv}' has no header row.")
        missing = [col for col in (*CHECK_COLUMNS, URL_COLUMN) if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"'{input_csv}' is missing column(s): {', '.join(missing)}")

        with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                total += 1
                is_invalid = any(not (row.get(col) or "").strip() for col in CHECK_COLUMNS)
                if is_invalid:
                    removed += 1
                    evidence_value = (row.get(URL_COLUMN) or "").strip()
                    if evidence_value:
                        found = URL_PATTERN.findall(evidence_value)
                        extracted_urls.extend(found or [evidence_value])
                    continue
                writer.writerow(row)

    return total, removed, extracted_urls


if __name__ == "__main__":
    args = _parse_args()

    print(f"📖 Reading: {args.input_csv}")
    total, removed, extracted_urls = remove_invalid_rows(args.input_csv, args.output_csv)
    kept = total - removed

    print(f"\n{'=' * 60}")
    print(f"{'INVALID ROWS CLEANUP SUMMARY':^60}")
    print(f"{'=' * 60}")
    print(f"Total rows read:               {total}")
    print(f"Removed (no AI evaluation):    {removed}")
    print(f"Kept:                          {kept}")
    print(f"Output written to:             {args.output_csv}")
    print(f"{'=' * 60}")

    if extracted_urls:
        print(f"\nEvidence URLs from removed rows ({len(extracted_urls)}):")
        for i, url in enumerate(extracted_urls, 1):
            print(f"{i}. {url}")
