import json
from pathlib import Path

import pandas as pd

from common import fail, write_csv

INPUT_FILE = "data/drift.json"
OUTPUT_FILE = "data/drift.csv"
FETCH_HINT = "make fetch-drift"

# Page statuses written by fetch_drift.js, in chart order
STATUSES = ["current", "drifted", "unpinned", "orphan", "invalid_pin"]
COLUMNS = ["lang", "pages", *STATUSES, "drifted_pct", "as_of", "head_sha"]


def drift_table(dataset):
    """One row per language: its translated pages, how many have each status and the drifted share.

    `drifted_pct` is the drifted pages over the translated pages, in percent with
    one decimal, and empty for a language without pages. `as_of` is the day the
    drift was measured and `head_sha` the upstream commit it was measured at.
    Rows go from the most to the least drifted share, ties by more pages, then by
    language code, with the languages without pages last.
    """
    df = pd.DataFrame(dataset["languages"], columns=["lang", "pages", *STATUSES])
    pages = df["pages"].where(df["pages"] > 0)
    df["drifted_pct"] = (df["drifted"] / pages * 100).round(1)
    df["as_of"] = dataset["generated_at"][:10]
    df["head_sha"] = dataset["head"]["sha"]

    df = df.sort_values(
        ["drifted_pct", "pages", "lang"],
        ascending=[False, False, True],
        na_position="last",
        kind="stable",
    )
    return df.reset_index(drop=True)[COLUMNS]


def load_dataset(path):
    """Read the drift dataset, exiting with the fetch command if it is missing or unreadable."""
    path = Path(path)
    if not path.exists():
        fail(f"{path} not found. Run '{FETCH_HINT}' first.")

    try:
        dataset = json.loads(path.read_text())
        table = drift_table(dataset)
    except (OSError, ValueError, KeyError, TypeError) as e:
        fail(f"could not read {path}: {e}. Run '{FETCH_HINT}' to fetch it again.")

    if table["pages"].sum() == 0:
        fail(f"{path} has no translated pages. Run '{FETCH_HINT}' to fetch it again.")
    return table


def main():
    table = load_dataset(INPUT_FILE)
    write_csv(table, OUTPUT_FILE)

    head = table["head_sha"].iloc[0][:12]
    print(f"✓ Successfully converted {len(table)} languages to the drift CSV")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Upstream commit: {head} ({table['as_of'].iloc[0]})")
    for row in table.itertuples():
        if pd.isna(row.drifted_pct):
            print(f"  {row.lang}: no translated pages")
        else:
            print(f"  {row.lang}: {row.drifted_pct:.1f}% drifted of {row.pages} pages")


if __name__ == "__main__":
    main()
