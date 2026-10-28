import os
import sys
from pathlib import Path

import pandas as pd


def utc_now():
    return pd.Timestamp.now(tz="UTC")


def resolve_year(today):
    """The YEAR environment variable, or the year of `today` when it is unset or empty."""
    return os.environ.get("YEAR", "").strip() or str(today.year)


def fail(message):
    """Print an error and exit with a non-zero status."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def load_json(path, hint):
    """Read a fetch output file into a DataFrame, exiting if it is missing, unreadable or empty.

    `hint` is the make command that regenerates the file.
    """
    path = Path(path)
    if not path.exists():
        fail(f"{path} not found. Run '{hint}' first.")

    try:
        df = pd.read_json(path)
    except (ValueError, OSError) as e:
        fail(f"could not read {path}: {e}. Run '{hint}' to fetch it again.")

    if df.empty:
        fail(f"{path} has no records. Run '{hint}' to fetch it again.")

    return df


def write_csv(df, path):
    """Write a DataFrame to CSV without the index, creating the parent directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def to_utc_naive(series):
    """Convert timestamps (naive, UTC or any offset) to naive UTC datetimes."""
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)
