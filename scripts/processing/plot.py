import argparse
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

import contributors_to_csv as contributors_csv
import coverage_to_csv as coverage_csv
import lang_contributions_to_csv as lang_csv
import merged_prs_to_csv as merged_csv
import pr_flow_to_csv as pr_flow_csv
import release_metrics_to_csv as releases_csv
from common import fail, resolve_year, utc_now
from plotting import (
    create_figure,
    draw_bars,
    draw_by_language,
    draw_ranked_bars,
    draw_series,
    draw_stacked_bars,
    set_symlog_axis,
    spread_labels,
    style_axes,
    style_legend,
)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass(frozen=True)
class Source:
    csv_path: Path
    date_column: str | None  # None for one bar per language, with no date axis
    value_column: str
    title: str
    xlabel: str
    ylabel: str
    hint: str  # make command that produces the CSV
    by_language: bool = True  # one series per `lang`, otherwise a single total
    bars: bool = False  # with `by_language` and a date axis, stacked by language
    value_format: str = "{:.0f}"  # how values are written on the chart
    area: bool = True  # fill under a line, for running totals
    symlog_ticks: tuple[float, ...] = ()  # symlog y axis labeled at these values, if any


SOURCES = {
    "prs": Source(
        csv_path=Path(lang_csv.OUTPUT_FILE),
        date_column="date",
        value_column="count",
        title="Accumulated Contributions by Language",
        xlabel="Date",
        ylabel="Accumulated Contributions",
        hint=lang_csv.FETCH_HINT,
    ),
    "releases": Source(
        csv_path=Path(releases_csv.OUTPUT_FILE),
        date_column="month",
        value_column="total_lines",
        title="Accumulated Localization by Release Month",
        xlabel="Month",
        ylabel="Accumulated Lines Translated",
        hint=releases_csv.FETCH_HINT,
    ),
    "merged": Source(
        csv_path=Path(merged_csv.OUTPUT_FILE),
        date_column="month",
        value_column="total",
        title="Merged PRs",
        xlabel="Month",
        ylabel="Accumulated Merged PRs",
        hint=merged_csv.FETCH_HINT,
        by_language=False,
    ),
    "coverage": Source(
        csv_path=Path(releases_csv.OUTPUT_FILE),
        date_column="month",
        value_column="coverage_pct",
        title="Translation Coverage by Release Month",
        xlabel="Month",
        ylabel="Coverage (% of English pages)",
        hint=releases_csv.FETCH_HINT,
        value_format="{:.1f}%",
        area=False,
    ),
    "coverage-snapshot": Source(
        csv_path=Path(coverage_csv.OUTPUT_FILE),
        date_column=None,
        value_column="coverage_pct",
        title="Translation Coverage by Language",
        xlabel="Language",
        ylabel="Coverage (% of English pages)",
        hint=coverage_csv.FETCH_HINT,
        bars=True,
        value_format="{:.1f}%",
    ),
    "time-to-merge": Source(
        csv_path=Path(pr_flow_csv.TIME_TO_MERGE_FILE),
        date_column="month",
        value_column="median_days",
        title="Median Time to Merge",
        xlabel="Month of merge",
        ylabel="Median days from open to merge",
        hint=pr_flow_csv.FETCH_HINT,
        value_format="{:.1f}",
        area=False,
        # Sub-day medians stay linear, the weeks-long outliers of small languages log
        symlog_ticks=(0, 1, 2, 5, 10, 30, 90, 180, 365),
    ),
    "backlog": Source(
        csv_path=Path(pr_flow_csv.BACKLOG_FILE),
        date_column="month",
        value_column="open_prs",
        title="Open Localization PRs",
        xlabel="Month",
        ylabel="Open PRs at month end",
        hint=pr_flow_csv.FETCH_HINT,
        area=False,
    ),
    "contributors": Source(
        csv_path=Path(contributors_csv.MONTHLY_FILE),
        date_column="month",
        value_column="unique",
        title="Unique Contributors",
        xlabel="Month",
        ylabel="Unique contributors in the month",
        hint=contributors_csv.FETCH_HINT,
        area=False,
    ),
    "new-contributors": Source(
        csv_path=Path(contributors_csv.MONTHLY_FILE),
        date_column="month",
        value_column="new",
        title="New Contributors",
        xlabel="Month",
        ylabel="New contributors in the month",
        hint=contributors_csv.FETCH_HINT,
        bars=True,
    ),
}

# Sources whose data depends on the year, so the title names it
YEAR_TITLED = ("time-to-merge", "backlog", "contributors", "new-contributors")


def resolve_source(name, mode, year):
    """Look up a source, naming the year in the titles that depend on it and applying the plot mode to the merged PRs one."""
    source = SOURCES[name]
    if name in YEAR_TITLED:
        return replace(source, title=f"{source.title} - {year}")
    if name != "merged":
        return source

    monthly = mode == "monthly"
    mode_label = "month over month" if monthly else "accumulated"
    return replace(
        source,
        value_column="count" if monthly else "total",
        title=f"Merged PRs - {year}, {mode_label}",
        ylabel="Merged PRs" if monthly else "Accumulated Merged PRs",
        bars=monthly,
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Plot OpenTelemetry contribution metrics")
    parser.add_argument(
        "--source",
        choices=list(SOURCES),
        default="prs",
        help=(
            "Data source: 'prs' for PR-based metrics (default), 'releases' for monthly release "
            "metrics, 'merged' for total merged PRs, 'coverage' for the translation coverage "
            "of each release, 'coverage-snapshot' for the current coverage of each language, "
            "'time-to-merge' for the median days to merge a PR, 'backlog' for the PRs open at "
            "the end of each month, 'contributors' for the people who opened a PR in each "
            "month, 'new-contributors' for those on their first PR in the language"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["accumulated", "monthly"],
        default="accumulated",
        help="Plot mode for merged PRs: 'accumulated' for cumulative line chart (default), 'monthly' for month-over-month bar chart",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="Save the chart to PATH (e.g. chart.png) instead of opening a window",
    )
    return parser.parse_args(argv)


def load_config():
    if not CONFIG_PATH.exists():
        fail(f"{CONFIG_PATH} not found.")

    try:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        fail(f"could not read config: {e}")


def load_csv(source):
    if not source.csv_path.exists():
        fail(f"{source.csv_path} not found. Run '{source.hint}' first.")

    try:
        dates = [source.date_column] if source.date_column else []
        df = pd.read_csv(source.csv_path, parse_dates=dates)
    except (OSError, ValueError) as e:
        fail(f"could not read {source.csv_path}: {e}. Run '{source.hint}' to generate it again.")

    if df.empty:
        fail(f"{source.csv_path} has no rows. Run '{source.hint}' first.")

    return df


def render(df, source, config):
    """Draw `df` as described by `source` and return the figure."""
    colors = config.get("colors", {})
    show_endpoint_values = config.get("show_endpoint_values", False)
    date_column = source.date_column
    value_column = source.value_column
    title = source.title
    stacked = source.bars and source.by_language and date_column is not None

    fig, ax = create_figure()

    if date_column is None:
        draw_ranked_bars(ax, df, value_column, colors, show_endpoint_values, source.value_format)
        if "as_of" in df:
            title = f"{title} - {df['as_of'].iloc[0]}"
    elif stacked:
        draw_stacked_bars(
            ax, df, date_column, value_column, colors, show_endpoint_values, source.value_format
        )
    elif source.by_language:
        draw_by_language(
            ax,
            df,
            date_column,
            value_column,
            colors,
            show_endpoint_values,
            source.value_format,
            source.area,
        )
    else:
        subset = df.sort_values(date_column)
        color = colors.get("total", "#CCCCCC")  # Neutral gray default
        if source.bars:
            draw_bars(ax, subset[date_column], subset[value_column], color, show_endpoint_values)
        else:
            draw_series(
                ax, subset[date_column], subset[value_column], "Total", color, show_endpoint_values
            )

    style_axes(ax, title, source.xlabel, source.ylabel, dates=date_column is not None)
    if not source.area:
        # Without a fill to anchor it, a line chart would not start at zero
        ax.set_ylim(bottom=0)
        # Room for the endpoint values, which are wider than the counts and
        # would run under the legend
        left, right = ax.get_xlim()
        ax.set_xlim(left, right + 0.1 * (right - left))
    if source.symlog_ticks:
        set_symlog_axis(ax, source.symlog_ticks)

    # Bars of a single color need no legend, stacked ones name their languages in it,
    # top segment first
    if stacked or not source.bars:
        style_legend(ax, "Language" if source.by_language else None, reverse=stacked)

    # Tight layout with extra padding for cleaner look
    fig.tight_layout(pad=1.5)
    if date_column is not None and not source.bars:
        # The layout is final, so the distance between labels can be measured
        spread_labels(ax, ax.texts)
    return fig


def describe(df, source):
    if source.date_column is None:
        return f"Generated coverage bar chart for {len(df)} languages"
    if source.by_language and source.bars:
        return f"Generated stacked bar chart with {df['lang'].nunique()} languages"
    if source.by_language:
        return f"Generated plot with {df['lang'].nunique()} languages"
    if source.bars:
        return "Generated bar chart for merged PRs (month-over-month)"
    return "Generated line chart for merged PRs (accumulated)"


def main(argv=None):
    args = parse_args(argv)
    config = load_config()
    source = resolve_source(args.source, args.mode, resolve_year(utc_now()))
    df = load_csv(source)

    fig = render(df, source, config)

    print(f"✓ {describe(df, source)}")
    date_column = source.date_column
    if date_column:
        print(
            f"  Date range: {df[date_column].min().strftime('%Y-%m-%d')} "
            f"to {df[date_column].max().strftime('%Y-%m-%d')}"
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Tight bbox keeps the legend, which sits outside the axes, inside the image
        fig.savefig(args.output, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {args.output}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
