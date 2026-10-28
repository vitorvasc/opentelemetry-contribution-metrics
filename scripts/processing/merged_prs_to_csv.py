import pandas as pd

from common import fail, load_json, resolve_year, to_utc_naive, utc_now, write_csv

INPUT_FILE = "data/merged_prs.json"
OUTPUT_FILE = "data/merged_prs_accumulated.csv"
FETCH_HINT = "make fetch-merged-prs"
PLOT_HINT = "make plot-merged-prs"


def monthly_counts(df, year, today=None):
    """One row per month of `year` with the PR count and the running total.

    For the current year, months after `today` are left out so the running
    total does not continue as a flat line into the future.
    """
    if today is None:
        today = utc_now()
    last_month = today.month if int(year) == today.year else 12

    # Extract month from merged_at
    months = to_utc_naive(df["merged_at"]).dt.strftime("%Y-%m")
    counts = months.value_counts()

    # Include months with zero PRs
    result = pd.DataFrame({"month": [f"{year}-{m:02d}" for m in range(1, last_month + 1)]})
    result["count"] = result["month"].map(counts).fillna(0).astype(int)
    result["total"] = result["count"].cumsum()
    return result


def main():
    df = load_json(INPUT_FILE, FETCH_HINT)

    # One UTC timestamp drives both the default year and the future-month trim
    today = utc_now()

    # Year used to fill missing months
    year = resolve_year(today)
    if not (year.isdigit() and len(year) == 4):
        fail(f"YEAR must be a four-digit year, got '{year}'")

    result = monthly_counts(df, year, today)
    if result["count"].sum() == 0:
        years = sorted(to_utc_naive(df["merged_at"]).dt.year.dropna().astype(int).unique())
        plot_advice = (
            f"'{PLOT_HINT} YEAR={years[-1]}' to plot the data you have, or " if years else ""
        )
        fail(
            f"no merged PRs in {year} (found: {', '.join(map(str, years)) or 'no dates'}). "
            f"Run {plot_advice}'{FETCH_HINT} YEAR={year}' to fetch {year}."
        )

    write_csv(result, OUTPUT_FILE)

    print(f"✓ Successfully converted {len(df)} merged PRs to accumulated CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Year: {year}")
    print(f"  Total merged PRs: {result['total'].iloc[-1]}")


if __name__ == "__main__":
    main()
