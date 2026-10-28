from common import load_json, write_csv

INPUT_FILE = "data/coverage_snapshot.json"
OUTPUT_FILE = "data/coverage_snapshot.csv"
FETCH_HINT = "make fetch-coverage"


def rank_coverage(df):
    """Order languages from the most to the least covered, ties by language code."""
    return df.sort_values(["coverage_pct", "lang"], ascending=[False, True]).reset_index(drop=True)


def main():
    df = rank_coverage(load_json(INPUT_FILE, FETCH_HINT))
    write_csv(df, OUTPUT_FILE)

    top = df.iloc[0]
    print(f"✓ Successfully converted {len(df)} languages to the coverage CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Most covered: {top['lang']} ({top['coverage_pct']:.1f}%)")


if __name__ == "__main__":
    main()
