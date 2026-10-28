import pandas as pd

from common import fail, load_json, resolve_year, to_utc_naive, utc_now, window_months, write_csv

INPUT_FILE = "data/pr_flow.json"
MONTHLY_FILE = "data/pr_flow_contributors.csv"
YEAR_FILE = "data/pr_flow_contributors_year.csv"
FETCH_HINT = "make fetch-pr-flow"
PLOT_HINT = "make plot-contributors"

REQUIRED_COLUMNS = ("lang", "created_at", "author", "author_type")
MONTHLY_COLUMNS = ["month", "lang", "unique", "new", "returning"]
YEAR_COLUMNS = ["year", "lang", "unique", "new", "returning"]


def contributor_prs(df):
    """The PRs opened by people, with the month each was created and the month of the author's first PR.

    Bots (typed as such, or with a login ending in `[bot]`) and PRs without an
    author (a deleted account) are left out. A PR counts in the month it was
    created, in UTC, whatever its state. The first PR is the first one the author
    opened in that language over all of `df`, not only in the year drawn.
    """
    author = df["author"].fillna("").astype(str)
    is_person = (author != "") & ~author.str.endswith("[bot]") & (df["author_type"] != "Bot")

    prs = pd.DataFrame(
        {
            "lang": df["lang"],
            "author": author,
            "month": to_utc_naive(df["created_at"]).dt.to_period("M"),
        }
    )[is_person]
    prs["first_month"] = prs.groupby(["lang", "author"])["month"].transform("min")
    return prs


def count_authors(prs, by):
    """Unique contributors and new ones among `prs`, per `by`."""
    unique = prs.groupby(by)["author"].nunique()
    new = prs[prs["month"] == prs["first_month"]].groupby(by)["author"].nunique()
    return pd.DataFrame({"unique": unique, "new": new})


def monthly_contributors(df, year, today):
    """Contributors per month of `year` and language.

    `unique` is the authors who opened a PR in the month, `new` those whose first
    PR in the language is in it, and `returning` the rest. Every month of the
    window has a row for every language of `df`, with 0 when nobody contributed:
    a month without contributors is a real zero, not a gap. Someone who
    contributes to two languages is counted in each.
    """
    prs = contributor_prs(df)
    grid = pd.MultiIndex.from_product(
        [window_months(year, today), sorted(df["lang"].unique())], names=["month", "lang"]
    )
    result = count_authors(prs, ["month", "lang"]).reindex(grid).fillna(0).astype(int)
    result["returning"] = result["unique"] - result["new"]

    result = result.reset_index()
    result["month"] = result["month"].astype(str)
    return result[MONTHLY_COLUMNS]


def yearly_contributors(df, year, today):
    """Contributors over the months of `year`, per language.

    `unique` counts each author once however many months they contributed in, so
    it is not the sum of the monthly counts. `new` is the authors whose first PR in
    the language is in the window, and `returning` those who contributed before
    it. A year that has not started has no rows.
    """
    months = window_months(year, today)
    prs = contributor_prs(df)
    in_year = prs[prs["month"].isin(months)]

    langs = sorted(df["lang"].unique()) if months else []
    result = count_authors(in_year, "lang").reindex(pd.Index(langs, name="lang"))
    result = result.fillna(0).astype(int)
    result["returning"] = result["unique"] - result["new"]

    result = result.reset_index()
    result.insert(0, "year", int(year))
    return result[YEAR_COLUMNS]


def check_contributors(df, result, year, today):
    """Why `result` has nothing to chart, or None when it has data."""
    if result["unique"].sum() > 0:
        return None

    if int(year) > today.year:
        return (
            f"{year} has not started, so it has no month to count. "
            f"Run '{PLOT_HINT} YEAR={today.year}' to plot the current year."
        )

    years = sorted(contributor_prs(df)["month"].dt.year.unique())
    advice = (
        f"Run '{PLOT_HINT} YEAR={years[-1]}' to plot the data you have."
        if years
        else f"Run '{FETCH_HINT}' to fetch it again."
    )
    return f"no contributors in {year} (found: {', '.join(map(str, years)) or 'none'}). {advice}"


def main():
    df = load_json(INPUT_FILE, FETCH_HINT)

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        fail(
            f"{INPUT_FILE} has no {', '.join(missing)} data. Run '{FETCH_HINT}' to fetch it again."
        )

    # One UTC timestamp drives both the default year and the future-month trim
    today = utc_now()

    year = resolve_year(today)
    if not (year.isdigit() and len(year) == 4):
        fail(f"YEAR must be a four-digit year, got '{year}'")

    monthly = monthly_contributors(df, year, today)
    problem = check_contributors(df, monthly, year, today)
    if problem:
        fail(problem)

    summary = yearly_contributors(df, year, today)
    write_csv(monthly, MONTHLY_FILE)
    write_csv(summary, YEAR_FILE)

    print(f"✓ Successfully converted {len(df)} PRs to the contributors CSVs")
    print(f"  Output: {MONTHLY_FILE}")
    print(f"          {YEAR_FILE}")
    print(f"  Year: {year}")
    for row in summary.itertuples():
        print(
            f"  {row.lang}: {row.unique} contributors in {year} "
            f"({row.new} new, {row.returning} returning)"
        )


if __name__ == "__main__":
    main()
