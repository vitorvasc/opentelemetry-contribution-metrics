import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.colors import to_rgb

import plot
from plotting import draw_by_language, draw_ranked_bars, draw_series

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# (id, CLI args, CSV fixture the source reads)
SMOKE_CASES = [
    ("prs", [], "lang_accumulated.csv"),
    ("releases", ["--source", "releases"], "release_metrics_accumulated.csv"),
    ("merged", ["--source", "merged"], "merged_prs_accumulated.csv"),
    (
        "merged-monthly",
        ["--source", "merged", "--mode", "monthly"],
        "merged_prs_accumulated.csv",
    ),
    ("coverage", ["--source", "coverage"], "release_metrics_accumulated.csv"),
    ("coverage-snapshot", ["--source", "coverage-snapshot"], "coverage_snapshot.csv"),
    ("time-to-merge", ["--source", "time-to-merge"], "pr_flow_time_to_merge.csv"),
    ("backlog", ["--source", "backlog"], "pr_flow_backlog.csv"),
]


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.mark.parametrize(
    "args, csv_name", [(args, csv) for _, args, csv in SMOKE_CASES], ids=[c[0] for c in SMOKE_CASES]
)
def test_plot_writes_png_without_showing_a_window(
    args, csv_name, stage, workdir, monkeypatch, capsys
):
    stage(csv_name)
    monkeypatch.setattr(plt, "show", lambda *a, **k: pytest.fail("plt.show() was called"))
    output = workdir / "charts" / "chart.png"

    plot.main([*args, "--output", str(output)])

    assert output.read_bytes().startswith(PNG_MAGIC)
    assert output.stat().st_size > 1000
    assert plt.get_fignums() == []
    assert "Saved:" in capsys.readouterr().out


def test_plot_without_output_shows_the_chart(stage, monkeypatch):
    stage("merged_prs_accumulated.csv")
    shown = []
    monkeypatch.setattr(plt, "show", lambda *a, **k: shown.append(True))

    plot.main(["--source", "merged"])

    assert shown == [True]


@pytest.mark.parametrize("source", list(plot.SOURCES))
def test_plot_fails_with_make_target_when_csv_is_missing(source, workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        plot.main(["--source", source, "--output", str(workdir / "x.png")])

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert plot.SOURCES[source].hint in err
    assert plot.SOURCES[source].hint.startswith("make fetch-")


def test_plot_fails_on_csv_without_rows(workdir, capsys):
    (workdir / "data" / "merged_prs_accumulated.csv").write_text("month,count,total\n")

    with pytest.raises(SystemExit) as exc:
        plot.main(["--source", "merged", "--output", str(workdir / "x.png")])

    assert exc.value.code == 1
    assert "has no rows" in capsys.readouterr().err
    assert not (workdir / "x.png").exists()


def test_plot_fails_on_zero_byte_csv(workdir, capsys):
    (workdir / "data" / "merged_prs_accumulated.csv").write_text("")

    with pytest.raises(SystemExit) as exc:
        plot.main(["--source", "merged", "--output", str(workdir / "x.png")])

    assert exc.value.code == 1
    assert "make fetch-merged-prs" in capsys.readouterr().err


def test_cli_accepts_the_arguments_the_makefile_passes():
    assert plot.parse_args([]).source == "prs"
    args = plot.parse_args(["--source=merged", "--mode=monthly"])
    assert (args.source, args.mode, args.output) == ("merged", "monthly", None)
    assert plot.parse_args(["--source=releases"]).source == "releases"


def test_cli_rejects_unknown_source():
    with pytest.raises(SystemExit) as exc:
        plot.parse_args(["--source", "nope"])

    assert exc.value.code == 2


def test_resolve_source_applies_mode_and_year_to_merged_prs():
    accumulated = plot.resolve_source("merged", "accumulated", "2024")
    monthly = plot.resolve_source("merged", "monthly", "2024")

    assert (accumulated.value_column, accumulated.bars) == ("total", False)
    assert accumulated.title == "Merged PRs - 2024, accumulated"
    assert accumulated.ylabel == "Accumulated Merged PRs"
    assert (monthly.value_column, monthly.bars) == ("count", True)
    assert monthly.title == "Merged PRs - 2024, month over month"
    assert monthly.ylabel == "Merged PRs"


def test_resolve_source_ignores_mode_for_language_sources():
    for name in ("prs", "releases", "coverage", "coverage-snapshot"):
        assert plot.resolve_source(name, "monthly", "2024") is plot.SOURCES[name]


@pytest.fixture
def spy_titles(monkeypatch):
    """Titles of the charts drawn by plot.main."""
    titles = []
    draw = plot.render

    def render(df, source, config):
        fig = draw(df, source, config)
        titles.append(fig.axes[0].get_title())
        return fig

    monkeypatch.setattr(plot, "render", render)
    return titles


def test_plot_titles_merged_prs_with_the_default_year_when_year_is_unset(
    stage, workdir, monkeypatch, spy_titles
):
    stage("merged_prs_accumulated.csv")
    monkeypatch.setattr(plot, "utc_now", lambda: pd.Timestamp("2024-03-15 12:00", tz="UTC"))

    plot.main(["--source", "merged", "--output", str(workdir / "x.png")])

    assert spy_titles == ["Merged PRs - 2024, accumulated"]


def test_plot_titles_merged_prs_with_the_year_from_the_environment(
    stage, workdir, monkeypatch, spy_titles
):
    stage("merged_prs_accumulated.csv")
    monkeypatch.setenv("YEAR", "2023")
    monkeypatch.setattr(plot, "utc_now", lambda: pd.Timestamp("2024-03-15 12:00", tz="UTC"))

    plot.main(["--source", "merged", "--mode", "monthly", "--output", str(workdir / "x.png")])

    assert spy_titles == ["Merged PRs - 2023, month over month"]


def render_source(name, csv_name, stage):
    stage(csv_name)
    source = plot.SOURCES[name]
    return plot.render(plot.load_csv(source), source, plot.load_config())


def test_coverage_history_draws_a_percent_line_per_language(stage, workdir):
    fig = render_source("coverage", "release_metrics_accumulated.csv", stage)
    ax = fig.axes[0]

    assert sorted(line.get_label() for line in ax.lines) == ["DE", "ES", "PT"]
    assert len(ax.collections) == 0  # no area fill under the lines
    assert ax.get_ylim()[0] == 0
    # The endpoint values fit between the last point and the legend
    left, right = ax.get_xlim()
    last_x = max(line.get_xdata().max() for line in ax.lines)
    assert right - mdates.date2num(last_x) > 0.1 * (right - left)
    assert sorted(text.get_text() for text in ax.texts) == ["25.1%", "41.9%", "9.6%"]
    assert ax.get_title() == "Translation Coverage by Release Month"
    assert ax.get_ylabel() == "Coverage (% of English pages)"
    assert ax.get_legend() is not None


def test_coverage_snapshot_draws_ranked_bars_in_language_colors(stage, workdir):
    fig = render_source("coverage-snapshot", "coverage_snapshot.csv", stage)
    ax = fig.axes[0]

    labels = [tick.get_text() for tick in ax.get_xticklabels()]
    assert labels == ["PT", "JA", "ZH", "ES", "FR", "UK", "RO", "BN", "KO", "PL"]
    heights = [bar.get_height() for bar in ax.patches]
    assert heights == sorted(heights, reverse=True)
    assert tuple(ax.patches[0].get_facecolor()[:3]) == pytest.approx(to_rgb("#A855F7"))  # pt
    assert ax.texts[0].get_text() == "50.8%"
    assert ax.texts[-1].get_text() == "1.0%"
    assert ax.get_title() == "Translation Coverage by Language - 2025-06-15"
    assert ax.get_xlabel() == "Language"
    assert ax.get_legend() is None


def test_coverage_snapshot_csv_keeps_language_codes_as_text(stage, workdir):
    stage("coverage_snapshot.csv")

    df = plot.load_csv(plot.SOURCES["coverage-snapshot"])

    assert df["lang"].tolist()[:2] == ["pt", "ja"]
    assert df["coverage_pct"].dtype == float


def test_plot_reports_the_snapshot_without_a_date_range(stage, workdir, capsys):
    stage("coverage_snapshot.csv")

    plot.main(["--source", "coverage-snapshot", "--output", str(workdir / "x.png")])

    out = capsys.readouterr().out
    assert "coverage bar chart for 10 languages" in out
    assert "Date range" not in out


def test_draw_series_reuses_the_line_color_when_none_is_configured():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))

    draw_series(ax, x, pd.Series([1, 2]), "XX", annotate=True)

    line_rgb = to_rgb(ax.lines[0].get_color())
    assert tuple(ax.collections[0].get_facecolor()[0][:3]) == pytest.approx(line_rgb)
    assert to_rgb(ax.texts[0].get_color()) == pytest.approx(line_rgb)


def test_draw_series_uses_the_configured_color_for_line_fill_and_annotation():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))

    draw_series(ax, x, pd.Series([1, 2]), "PT", color="#A855F7", annotate=True)

    expected = to_rgb("#A855F7")
    assert to_rgb(ax.lines[0].get_color()) == pytest.approx(expected)
    assert tuple(ax.collections[0].get_facecolor()[0][:3]) == pytest.approx(expected)
    assert to_rgb(ax.texts[0].get_color()) == pytest.approx(expected)
    assert ax.texts[0].get_text() == "2"


def test_draw_series_formats_the_endpoint_value():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))

    draw_series(ax, x, pd.Series([1.0, 33.33]), "XX", annotate=True, value_format="{:.1f}%")

    assert ax.texts[0].get_text() == "33.3%"


def test_draw_series_without_area_draws_a_marked_line_with_no_fill():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))

    draw_series(ax, x, pd.Series([1, 2]), "XX", color="#A855F7", area=False)

    assert len(ax.collections) == 0
    assert ax.lines[0].get_marker() == "o"
    assert ax.lines[0].get_drawstyle() == "default"


def test_draw_ranked_bars_keeps_row_order_and_colors_each_bar_by_language():
    fig, ax = plt.subplots()
    df = pd.DataFrame({"lang": ["pt", "es", "xx"], "coverage_pct": [50.0, 20.25, 3.0]})

    draw_ranked_bars(
        ax, df, "coverage_pct", colors={"pt": "#A855F7", "es": "#00FF7F"}, annotate=True,
        value_format="{:.1f}%",
    )  # fmt: skip

    assert [bar.get_height() for bar in ax.patches] == [50.0, 20.25, 3.0]
    assert [tick.get_text() for tick in ax.get_xticklabels()] == ["PT", "ES", "XX"]
    assert tuple(ax.patches[1].get_facecolor()[:3]) == pytest.approx(to_rgb("#00FF7F"))
    assert [text.get_text() for text in ax.texts] == ["50.0%", "20.2%", "3.0%"]


def test_draw_by_language_extends_shorter_series_to_the_latest_date():
    fig, ax = plt.subplots()
    df = pd.DataFrame(
        {
            "lang": ["pt", "pt", "de"],
            "date": pd.to_datetime(["2025-01-01", "2025-03-01", "2025-01-15"]),
            "count": [1, 3, 1],
        }
    )

    draw_by_language(ax, df, "date", "count", colors={"pt": "#A855F7"})

    lines = {line.get_label(): line for line in ax.lines}
    assert list(lines) == ["PT", "DE"]  # larger series is drawn first
    assert pd.Timestamp(lines["DE"].get_xdata()[-1]) == pd.Timestamp("2025-03-01")
    assert lines["DE"].get_ydata()[-1] == 1


def test_draw_series_leaves_a_gap_where_a_value_is_missing():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]))

    draw_series(ax, x, pd.Series([1.0, None, 3.0]), "XX", area=False)

    assert pd.isna(ax.lines[0].get_ydata()[1])


def test_draw_series_labels_the_last_value_when_the_series_ends_in_a_gap():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]))

    draw_series(
        ax, x, pd.Series([1.0, 2.5, None]), "XX", annotate=True, value_format="{:.1f}", area=False
    )

    assert [text.get_text() for text in ax.texts] == ["2.5"]
    assert ax.texts[0].xy[0] == pd.Timestamp("2025-02-01")


def test_draw_series_without_any_value_has_nothing_to_label():
    fig, ax = plt.subplots()
    x = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))

    draw_series(ax, x, pd.Series([None, None], dtype=float), "XX", annotate=True, area=False)

    assert len(ax.texts) == 0


def test_draw_by_language_skips_a_language_without_any_value():
    fig, ax = plt.subplots()
    months = pd.to_datetime(["2025-01-01", "2025-02-01"])
    df = pd.DataFrame(
        {
            "lang": ["pt", "pt", "ko", "ko"],
            "month": list(months) * 2,
            "days": [1.0, 2.0, None, None],
        }
    )

    draw_by_language(ax, df, "month", "days", colors={}, area=False)

    assert [line.get_label() for line in ax.lines] == ["PT"]


def test_pr_flow_titles_name_the_year():
    assert plot.resolve_source("time-to-merge", "accumulated", "2026").title == (
        "Median Time to Merge - 2026"
    )
    assert plot.resolve_source("backlog", "accumulated", "2025").title == (
        "Open Localization PRs - 2025"
    )
    assert plot.SOURCES["backlog"].title == "Open Localization PRs"


def test_time_to_merge_draws_a_line_per_language_with_a_median_and_breaks_at_gaps(stage, workdir):
    stage("pr_flow_time_to_merge.csv")
    source = plot.resolve_source("time-to-merge", "accumulated", "2026")

    fig = plot.render(plot.load_csv(source), source, plot.load_config())

    ax = fig.axes[0]
    lines = {line.get_label(): line for line in ax.lines}
    # ko never merged a PR, so it has nothing to draw
    assert list(lines) == ["PT", "ES"]
    assert pd.isna(lines["ES"].get_ydata()[1])
    assert lines["PT"].get_ydata()[0] == 6.0
    assert ax.get_ylim()[0] == 0
    assert ax.get_title() == "Median Time to Merge - 2026"
    # Each label sits on the last month with a value: February for PT, March for ES
    assert [text.get_text() for text in ax.texts] == ["2.2", "2.0"]


def test_backlog_draws_every_language_including_zero_counts(stage, workdir):
    stage("pr_flow_backlog.csv")
    source = plot.resolve_source("backlog", "accumulated", "2026")

    fig = plot.render(plot.load_csv(source), source, plot.load_config())

    ax = fig.axes[0]
    lines = {line.get_label(): line for line in ax.lines}
    assert sorted(lines) == ["ES", "KO", "PT"]
    assert list(lines["ES"].get_ydata()) == [0, 0, 1]
    assert ax.get_ylim()[0] == 0
    assert ax.get_ylabel() == "Open PRs"
