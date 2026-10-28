import argparse
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from common import fail, load_json, resolve_year, to_utc_naive, utc_now, write_csv

INPUT_FILE = "data/pr_flow.json"
TIME_TO_MERGE_FILE = "data/pr_flow_time_to_merge.csv"
BACKLOG_FILE = "data/pr_flow_backlog.csv"
FETCH_HINT = "make fetch-pr-flow"
PLOT_HINT = "make plot-pr-flow"
BACKLOG_PLOT_HINT = "make plot-pr-backlog"

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


def check_time_to_merge(df, result, year, today):
    """Why `result` has nothing to chart, or None when it has data."""
    if result["count"].sum() > 0:
        return None

    years = sorted(to_utc_naive(df["merged_at"]).dt.year.dropna().astype(int).unique())
    advice = (
        f"Run '{PLOT_HINT} YEAR={years[-1]}' to plot the data you have."
        if years
        else f"Run '{FETCH_HINT}' to fetch it again."
    )
    return f"no merged PRs in {year} (found: {', '.join(map(str, years)) or 'no merges'}). {advice}"


def check_backlog(df, result, year, today):
    """Why `result` has nothing to chart, or None when it has data."""
    first_year = int(to_utc_naive(df["created_at"]).dt.year.min())
    if int(year) > today.year:
        return (
            f"{year} has not started, so it has no month to count. "
            f"Run '{BACKLOG_PLOT_HINT} YEAR={today.year}' to plot the current year."
        )
    if int(year) < first_year:
        return (
            f"no PRs were created by the end of {year} (the data starts in {first_year}). "
            f"Run '{BACKLOG_PLOT_HINT} YEAR={first_year}' to plot the data you have."
        )
    return None


@dataclass(frozen=True)
class Dataset:
    compute: Callable  # (df, year, today) -> DataFrame
    path: str
    check: Callable  # (df, result, year, today) -> why it is empty, or None
    label: str
    describe: Callable  # (result, year) -> the line that sums it up


DATASETS = {
    "time-to-merge": Dataset(
        time_to_merge,
        TIME_TO_MERGE_FILE,
        check_time_to_merge,
        "time to merge",
        lambda result, year: f"PRs merged in {year}: {result['count'].sum()}",
    ),
    "backlog": Dataset(
        open_backlog,
        BACKLOG_FILE,
        check_backlog,
        "backlog",
        lambda result, year: (
            f"Open PRs at the end of {result['month'].max()}: "
            f"{result.loc[result['month'] == result['month'].max(), 'open_prs'].sum()}"
        ),
    ),
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Turn the PR flow data into CSVs")
    parser.add_argument(
        "--only",
        choices=list(DATASETS),
        help=(
            "Write only this CSV and fail only if it has nothing to chart "
            "(default: both, each written when it has data)"
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    df = load_json(INPUT_FILE, FETCH_HINT)

    # One UTC timestamp drives both the default year and the future-month trim
    today = utc_now()

    year = resolve_year(today)
    if not (year.isdigit() and len(year) == 4):
        fail(f"YEAR must be a four-digit year, got '{year}'")

    # Each dataset is written on its own, so one with no data does not hold back the other
    problems = []
    for name in [args.only] if args.only else list(DATASETS):
        dataset = DATASETS[name]
        result = dataset.compute(df, year, today)
        problem = dataset.check(df, result, year, today)
        if problem:
            problems.append(problem)
            continue

        write_csv(result, dataset.path)
        print(f"✓ Successfully converted {len(df)} PRs to the {dataset.label} CSV")
        print(f"  Output: {dataset.path}")
        print(f"  Year: {year}")
        print(f"  {dataset.describe(result, year)}")

    if problems:
        fail("\n       ".join(problems))


if __name__ == "__main__":
    main()
