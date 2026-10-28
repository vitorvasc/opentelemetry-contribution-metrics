import pandas as pd

from common import fail, load_json, resolve_year, to_utc_naive, utc_now, write_csv

INPUT_FILE = "data/pr_flow.json"
TIME_TO_MERGE_FILE = "data/pr_flow_time_to_merge.csv"
BACKLOG_FILE = "data/pr_flow_backlog.csv"
FETCH_HINT = "make fetch-pr-flow"
PLOT_HINT = "make plot-pr-flow"

SECONDS_PER_DAY = 24 * 60 * 60


def window_months(year, today):
    """The months of `year`, up to the month of `today` when `year` is the current one.

    A year after `today` has no months, so its charts are empty rather than flat.
    """
    year = int(year)
    if year > today.year:
        return []
    last_month = today.month if year == today.year else 12
    return [pd.Period(year=year, month=month, freq="M") for month in range(1, last_month + 1)]


def to_naive_utc(timestamp):
    """A timestamp as a naive UTC one, like the columns `to_utc_naive` returns."""
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def time_to_merge(df, year, today):
    """Days from creation to merge, per month of `year` and language.

    A PR counts in the month it was merged, in UTC. Closed PRs that were never
    merged are left out. Every month of the window has a row for every language
    of `df`; a language with no merge in a month has a count of 0 and no median
    or p90, a gap rather than a zero. Days are rounded to two decimals.
    """
    created = to_utc_naive(df["created_at"])
    merged = to_utc_naive(df["merged_at"])

    done = pd.DataFrame(
        {
            "lang": df["lang"],
            "month": merged.dt.to_period("M"),
            "days": (merged - created).dt.total_seconds() / SECONDS_PER_DAY,
        }
    )[merged.notna()]
    stats = done.groupby(["month", "lang"])["days"].agg(
        median_days="median",
        p90_days=lambda days: days.quantile(0.9),
        count="count",
    )

    grid = pd.MultiIndex.from_product(
        [window_months(year, today), sorted(df["lang"].unique())], names=["month", "lang"]
    )
    result = stats.reindex(grid).reset_index()
    result["month"] = result["month"].astype(str)
    result["count"] = result["count"].fillna(0).astype(int)
    result[["median_days", "p90_days"]] = result[["median_days", "p90_days"]].round(2)
    return result


def open_backlog(df, year, today):
    """PRs still open at the end of each month of `year`, per language.

    A PR is open at the end of a month when it was created by then and was not
    closed, or only closed after it. A PR closed without a merge stops being
    open at its close, like a merged one. The current month ends at `today`, so
    its count is the open PRs right now. Every month has a row for every
    language of `df`, 0 when none was open.
    """
    created = to_utc_naive(df["created_at"])
    # A merged PR is closed at its merge, in case closed_at is missing
    closed = to_utc_naive(df["closed_at"]).fillna(to_utc_naive(df["merged_at"]))
    now = to_naive_utc(today)
    langs = sorted(df["lang"].unique())

    rows = []
    for month in window_months(year, today):
        end = min(month.end_time, now)
        is_open = (created <= end) & (closed.isna() | (closed > end))
        counts = df.loc[is_open].groupby("lang").size().reindex(langs, fill_value=0)
        rows.extend(
            {"month": str(month), "lang": lang, "open_prs": int(counts[lang])} for lang in langs
        )
    return pd.DataFrame(rows, columns=["month", "lang", "open_prs"])


def main():
    df = load_json(INPUT_FILE, FETCH_HINT)

    # One UTC timestamp drives both the default year and the future-month trim
    today = utc_now()

    year = resolve_year(today)
    if not (year.isdigit() and len(year) == 4):
        fail(f"YEAR must be a four-digit year, got '{year}'")

    durations = time_to_merge(df, year, today)
    if durations["count"].sum() == 0:
        years = sorted(to_utc_naive(df["merged_at"]).dt.year.dropna().astype(int).unique())
        plot_advice = (
            f"Run '{PLOT_HINT} YEAR={years[-1]}' to plot the data you have."
            if years
            else f"Run '{FETCH_HINT}' to fetch it again."
        )
        fail(
            f"no merged PRs in {year} (found: {', '.join(map(str, years)) or 'no merges'}). "
            f"{plot_advice}"
        )

    backlog = open_backlog(df, year, today)
    write_csv(durations, TIME_TO_MERGE_FILE)
    write_csv(backlog, BACKLOG_FILE)

    last_month = backlog["month"].max()
    open_at_end = backlog.loc[backlog["month"] == last_month, "open_prs"].sum()
    print(f"✓ Successfully converted {len(df)} PRs to time to merge and backlog CSVs")
    print(f"  Output: {TIME_TO_MERGE_FILE}, {BACKLOG_FILE}")
    print(f"  Year: {year}")
    print(f"  PRs merged in {year}: {durations['count'].sum()}")
    print(f"  Open PRs at the end of {last_month}: {open_at_end}")


if __name__ == "__main__":
    main()
