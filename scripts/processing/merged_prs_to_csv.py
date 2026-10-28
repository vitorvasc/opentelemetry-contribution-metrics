import os

import pandas as pd

from common import load_json, to_utc_naive, write_csv

INPUT_FILE = "data/merged_prs.json"
OUTPUT_FILE = "data/merged_prs_accumulated.csv"
FETCH_HINT = "make fetch-merged-prs"


def monthly_counts(df, year):
    """One row per month of `year` with the PR count and the running total."""
    # Extract month from merged_at
    months = to_utc_naive(df["merged_at"]).dt.strftime("%Y-%m")
    counts = months.value_counts()

    # Include months with zero PRs
    result = pd.DataFrame({"month": [f"{year}-{m:02d}" for m in range(1, 13)]})
    result["count"] = result["month"].map(counts).fillna(0).astype(int)
    result["total"] = result["count"].cumsum()
    return result


def main():
    df = load_json(INPUT_FILE, FETCH_HINT)

    # Year used to fill missing months
    year = os.environ.get("YEAR", str(pd.Timestamp.now().year))

    result = monthly_counts(df, year)
    write_csv(result, OUTPUT_FILE)

    print(f"✓ Successfully converted {len(df)} merged PRs to accumulated CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Year: {year}")
    print(f"  Total merged PRs: {result['total'].iloc[-1]}")


if __name__ == "__main__":
    main()
