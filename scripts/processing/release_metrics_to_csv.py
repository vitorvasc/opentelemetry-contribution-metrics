import os

from common import fail, load_json, write_csv

INPUT_FILE = "data/release_metrics.json"
OUTPUT_FILE = "data/release_metrics_accumulated.csv"
FETCH_HINT = "make fetch-release-metrics"
PLOT_HINT = "make plot-release-metrics"


def filter_by_year(df, year):
    """Keep the release months (YYYY-MM) that belong to `year`."""
    return df[df["month"].astype(str).str.startswith(f"{year}-")]


def accumulate_releases(df):
    """Add per-language running totals and month-over-month coverage change."""
    df = df.sort_values(["lang", "month"]).copy()
    by_lang = df.groupby("lang")

    df["total_lines"] = by_lang["lines_added"].cumsum()
    df["total_pages"] = by_lang["pages_added"].cumsum()

    # The first month of each language has no previous month, so its change is 0
    df["coverage_change"] = by_lang["coverage_pct"].diff().fillna(0).round(1)
    return df


def main():
    year = os.environ.get("YEAR", "").strip()

    df = load_json(INPUT_FILE, FETCH_HINT)
    if year:
        filtered = filter_by_year(df, year)
        if filtered.empty:
            found_year = df["month"].astype(str).str[:4].max()
            fail(
                f"no release records for {year} (found: {df['month'].min()} to {df['month'].max()}). "
                f"Run '{PLOT_HINT} YEAR={found_year}' to plot the data you have, "
                f"or '{FETCH_HINT} YEAR={year}' to fetch {year}."
            )
        df = filtered

    df = accumulate_releases(df)
    write_csv(df, OUTPUT_FILE)

    print(f"✓ Successfully converted {len(df)} records to accumulated CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Languages: {', '.join(sorted(df['lang'].unique()))}")
    print(f"  Months: {df['month'].min()} to {df['month'].max()}")


if __name__ == "__main__":
    main()
