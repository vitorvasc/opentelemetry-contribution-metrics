import os

from common import fail, load_json, to_utc_naive, write_csv

INPUT_FILE = "data/lang_contributions.json"
OUTPUT_FILE = "data/lang_accumulated.csv"
FETCH_HINT = "make fetch-lang-contributions"

# TYPE values: "" and "both" keep everything
TYPE_LABELS = {"prs": "PRs", "issues": "issues"}


def filter_by_type(df, type_filter):
    """Keep pull requests, issues or both, telling them apart by URL."""
    if type_filter in ("", "both"):
        return df
    if type_filter not in TYPE_LABELS:
        raise ValueError(f"TYPE must be prs, issues or both, got '{type_filter}'")

    is_pr = df["url"].str.contains("/pull/")
    return df[is_pr] if type_filter == "prs" else df[~is_pr]


def accumulate(df):
    """Cumulative contribution count per language, one row per language and timestamp."""
    # Use created_at as the date; each row counts as one contribution for its language
    df = df.assign(date=to_utc_naive(df["created_at"]), count=1)
    accumulated = df.groupby(["lang", "date"])["count"].sum().groupby(level=0).cumsum()
    return accumulated.reset_index()


def main():
    type_filter = os.environ.get("TYPE", "").strip()

    df = load_json(INPUT_FILE, FETCH_HINT)
    try:
        df = filter_by_type(df, type_filter)
    except ValueError as e:
        fail(str(e))

    if df.empty:
        fail(
            f"{INPUT_FILE} has no {TYPE_LABELS[type_filter]}. "
            f"Run '{FETCH_HINT} TYPE={type_filter}' to fetch them."
        )

    df_accum = accumulate(df)
    write_csv(df_accum, OUTPUT_FILE)

    label = TYPE_LABELS.get(type_filter, "contributions")
    print(f"✓ Successfully converted {len(df)} {label} to accumulated CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Languages: {', '.join(sorted(df['lang'].unique()))}")


if __name__ == "__main__":
    main()
