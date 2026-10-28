import argparse
import os
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

from common import fail
from plotting import (
    create_figure,
    draw_bars,
    draw_by_language,
    draw_series,
    style_axes,
    style_legend,
)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass(frozen=True)
class Source:
    csv_path: Path
    date_column: str
    value_column: str
    title: str
    xlabel: str
    ylabel: str
    hint: str  # make command that produces the CSV
    by_language: bool = True  # one series per `lang`, otherwise a single total
    bars: bool = False


SOURCES = {
    "prs": Source(
        csv_path=Path("data/lang_accumulated.csv"),
        date_column="date",
        value_column="count",
        title="Accumulated Contributions by Language",
        xlabel="Date",
        ylabel="Accumulated Contributions",
        hint="make fetch-lang-contributions",
    ),
    "releases": Source(
        csv_path=Path("data/release_metrics_accumulated.csv"),
        date_column="month",
        value_column="total_lines",
        title="Accumulated Localization by Release Month",
        xlabel="Month",
        ylabel="Accumulated Lines Translated",
        hint="make fetch-release-metrics",
    ),
    "merged": Source(
        csv_path=Path("data/merged_prs_accumulated.csv"),
        date_column="month",
        value_column="total",
        title="Merged PRs",
        xlabel="Month",
        ylabel="Accumulated Merged PRs",
        hint="make fetch-merged-prs",
        by_language=False,
    ),
}


def resolve_source(name, mode, year=""):
    """Look up a source, applying the plot mode to the merged PRs one."""
    source = SOURCES[name]
    if name != "merged":
        return source

    monthly = mode == "monthly"
    mode_label = "month over month" if monthly else "accumulated"
    return replace(
        source,
        value_column="count" if monthly else "total",
        title=f"Merged PRs - {year}, {mode_label}" if year else f"Merged PRs ({mode_label})",
        ylabel="Merged PRs" if monthly else "Accumulated Merged PRs",
        bars=monthly,
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Plot OpenTelemetry contribution metrics")
    parser.add_argument(
        "--source",
        choices=list(SOURCES),
        default="prs",
        help="Data source: 'prs' for PR-based metrics (default), 'releases' for monthly release metrics, 'merged' for total merged PRs",
    )
    parser.add_argument(
        "--mode",
        choices=["accumulated", "monthly"],
        default="accumulated",
        help="Plot mode for merged PRs: 'accumulated' for cumulative line chart (default), 'monthly' for month-over-month bar chart",
    )
    return parser.parse_args(argv)


def load_config():
    if not CONFIG_PATH.exists():
        fail(f"{CONFIG_PATH} not found.")

    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        fail(f"could not read config: {e}")


def load_csv(source):
    if not source.csv_path.exists():
        fail(f"{source.csv_path} not found. Run '{source.hint}' first.")

    try:
        df = pd.read_csv(source.csv_path, parse_dates=[source.date_column])
    except (OSError, ValueError) as e:
        fail(f"could not read {source.csv_path}: {e}")

    if df.empty:
        fail(f"{source.csv_path} has no rows. Run '{source.hint}' first.")

    return df


def render(df, source, config):
    """Draw `df` as described by `source` and return the figure."""
    colors = config.get("colors", {})
    show_endpoint_values = config.get("show_endpoint_values", False)
    date_column = source.date_column
    value_column = source.value_column

    fig, ax = create_figure()

    if source.by_language:
        draw_by_language(ax, df, date_column, value_column, colors, show_endpoint_values)
    else:
        subset = df.sort_values(date_column)
        color = colors.get("total", "#CCCCCC")  # Neutral gray default
        if source.bars:
            draw_bars(ax, subset[date_column], subset[value_column], color, show_endpoint_values)
        else:
            draw_series(
                ax, subset[date_column], subset[value_column], "Total", color, show_endpoint_values
            )

    style_axes(ax, source.title, source.xlabel, source.ylabel)

    # No legend for bar chart
    if not source.bars:
        style_legend(ax, "Language" if source.by_language else None)

    # Tight layout with extra padding for cleaner look
    fig.tight_layout(pad=1.5)
    return fig


def describe(df, source):
    if source.by_language:
        return f"Generated plot with {df['lang'].nunique()} languages"
    if source.bars:
        return "Generated bar chart for merged PRs (month-over-month)"
    return "Generated line chart for merged PRs (accumulated)"


def main(argv=None):
    args = parse_args(argv)
    config = load_config()
    source = resolve_source(args.source, args.mode, os.environ.get("YEAR", ""))
    df = load_csv(source)

    render(df, source, config)

    print(f"✓ {describe(df, source)}")
    date_column = source.date_column
    print(
        f"  Date range: {df[date_column].min().strftime('%Y-%m-%d')} "
        f"to {df[date_column].max().strftime('%Y-%m-%d')}"
    )

    plt.show()


if __name__ == "__main__":
    main()
