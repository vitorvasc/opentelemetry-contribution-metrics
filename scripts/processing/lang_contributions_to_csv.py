from common import load_json, to_utc_naive, write_csv

INPUT_FILE = "data/lang_contributions.json"
OUTPUT_FILE = "data/lang_accumulated.csv"
FETCH_HINT = "make fetch-lang-contributions"


def accumulate(df):
    """Cumulative contribution count per language, one row per language and timestamp."""
    # Use created_at as the date; each row counts as one contribution for its language
    df = df.assign(date=to_utc_naive(df["created_at"]), count=1)
    accumulated = df.groupby(["lang", "date"])["count"].sum().groupby(level=0).cumsum()
    return accumulated.reset_index()


def main():
    df = load_json(INPUT_FILE, FETCH_HINT)

    # Filter PRs only (exclude issues)
    df = df[df["url"].str.contains("/pull/")]

    df_accum = accumulate(df)
    write_csv(df_accum, OUTPUT_FILE)

    print(f"✓ Successfully converted {len(df)} PRs to accumulated CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Languages: {', '.join(sorted(df['lang'].unique()))}")


if __name__ == "__main__":
    main()
