from itertools import pairwise

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.colors import to_rgb

import plot
from plotting import (
    draw_by_language,
    draw_ranked_bars,
    draw_series,
    set_symlog_axis,
    spread_labels,
)

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
    assert ax.get_ylabel() == "Open PRs at month end"


def test_time_to_merge_uses_a_symlog_axis_labeled_in_days(stage, workdir):
    stage("pr_flow_time_to_merge.csv")
    source = plot.resolve_source("time-to-merge", "accumulated", "2026")

    ax = plot.render(plot.load_csv(source), source, plot.load_config()).axes[0]

    assert ax.get_yscale() == "symlog"
    # The largest median is 6 days, so the axis ends on the next tick, 10
    assert ax.get_ylim() == (0, 10)
    assert [tick.get_text() for tick in ax.get_yticklabels()] == ["0", "1", "2", "5", "10"]


def test_backlog_and_the_other_charts_keep_a_linear_axis(stage, workdir):
    stage("pr_flow_backlog.csv")
    source = plot.resolve_source("backlog", "accumulated", "2026")

    ax = plot.render(plot.load_csv(source), source, plot.load_config()).axes[0]

    assert ax.get_yscale() == "linear"
    assert all(not s.symlog_ticks for name, s in plot.SOURCES.items() if name != "time-to-merge")


def test_set_symlog_axis_is_linear_below_the_first_tick_and_log_above():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0.1, 3, 81])

    set_symlog_axis(ax, (0, 1, 2, 5, 10, 30, 90, 180))

    assert ax.get_yscale() == "symlog"
    assert ax.get_ylim() == (0, 90)
    assert [tick.get_text() for tick in ax.get_yticklabels()] == [
        "0",
        "1",
        "2",
        "5",
        "10",
        "30",
        "90",
    ]
    # 0 to 1 is linear, so 0.5 sits halfway; above 1 each factor of 10 is one decade
    to_axes = ax.transData.transform
    zero, half, one, ten, hundred = (to_axes((0, y))[1] for y in (0, 0.5, 1, 10, 100))
    assert half - zero == pytest.approx((one - zero) / 2)
    assert ten - one == pytest.approx(hundred - ten)


def test_set_symlog_axis_keeps_the_top_of_data_beyond_the_last_tick():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 500])

    set_symlog_axis(ax, (0, 1, 10, 100))

    assert ax.get_ylim()[1] > 500
    assert [tick.get_text() for tick in ax.get_yticklabels()] == ["0", "1", "10", "100"]


# ---------- end-of-line labels ----------


def label_axes(values, x="2025-03-01"):
    """Axes with one endpoint label per value, all at the same x, like line chart ends."""
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.set_ylim(0, 10)
    xs = pd.Series(pd.to_datetime(["2025-01-01", x]))
    for value in values:
        draw_series(ax, xs, pd.Series([value, value], dtype=float), "XX", annotate=True, area=False)
    fig.tight_layout()
    return fig, ax


def display_y(ax, label):
    """Vertical position of the center of a label's text, in pixels."""
    renderer = ax.figure.canvas.get_renderer()
    box = label.get_window_extent(renderer)
    return (box.y0 + box.y1) / 2


def test_spread_labels_separates_labels_that_overlap():
    fig, ax = label_axes([5.0, 5.1, 5.2])

    spread_labels(ax, ax.texts)

    centers = sorted(display_y(ax, label) for label in ax.texts)
    gap = 1.2 * 14 * fig.dpi / 72
    assert centers[1] - centers[0] == pytest.approx(gap)
    assert centers[2] - centers[1] == pytest.approx(gap)


def test_spread_labels_keeps_the_order_and_centers_the_group_on_its_points():
    fig, ax = label_axes([5.0, 5.1, 5.2])
    before = [display_y(ax, label) for label in ax.texts]

    spread_labels(ax, ax.texts)

    after = [display_y(ax, label) for label in ax.texts]
    assert after == sorted(after)
    assert sum(after) / 3 == pytest.approx(sum(before) / 3)
    # The points are not touched, only the text
    assert [label.xy[1] for label in ax.texts] == [5.0, 5.1, 5.2]


def test_spread_labels_leaves_labels_that_are_apart_where_they_are():
    fig, ax = label_axes([1.0, 5.0, 9.0])

    spread_labels(ax, ax.texts)

    assert [tuple(label.xyann) for label in ax.texts] == [(10, 0)] * 3


def test_spread_labels_only_moves_the_nearby_labels():
    fig, ax = label_axes([1.0, 5.0, 5.1, 9.0])

    spread_labels(ax, ax.texts)

    assert [tuple(label.xyann) for label in ax.texts][0] == (10, 0)
    assert [tuple(label.xyann) for label in ax.texts][3] == (10, 0)
    assert tuple(ax.texts[1].xyann) != (10, 0)
    assert tuple(ax.texts[2].xyann) != (10, 0)


def test_spread_labels_keeps_a_group_at_the_bottom_inside_the_axes():
    fig, ax = label_axes([0.0, 0.0, 0.0, 0.1])

    spread_labels(ax, ax.texts)

    centers = sorted(display_y(ax, label) for label in ax.texts)
    assert centers[0] >= ax.bbox.y0 - 0.5
    assert all(b - a > 1.2 * 14 * fig.dpi / 72 - 0.5 for a, b in pairwise(centers))


def test_spread_labels_ignores_labels_at_other_x_positions():
    fig, ax = label_axes([5.0])
    xs = pd.Series(pd.to_datetime(["2025-01-01", "2025-02-01"]))
    draw_series(ax, xs, pd.Series([5.0, 5.0]), "YY", annotate=True, area=False)

    spread_labels(ax, ax.texts)

    assert [tuple(label.xyann) for label in ax.texts] == [(10, 0)] * 2


def test_spread_labels_works_on_a_symlog_axis():
    fig, ax = label_axes([0.5, 0.6, 8.0])
    set_symlog_axis(ax, (0, 1, 10, 30))

    spread_labels(ax, ax.texts)

    centers = sorted(display_y(ax, label) for label in ax.texts)
    assert centers[1] - centers[0] == pytest.approx(1.2 * 14 * fig.dpi / 72)


LINE_CHARTS = [
    ("prs", "lang_accumulated.csv"),
    ("releases", "release_metrics_accumulated.csv"),
    ("coverage", "release_metrics_accumulated.csv"),
    ("time-to-merge", "pr_flow_time_to_merge.csv"),
    ("backlog", "pr_flow_backlog.csv"),
]


@pytest.mark.parametrize("name, csv_name", LINE_CHARTS, ids=[c[0] for c in LINE_CHARTS])
def test_line_charts_do_not_draw_end_labels_over_each_other(name, csv_name, stage, workdir):
    stage(csv_name)
    source = plot.resolve_source(name, "accumulated", "2025")

    fig = plot.render(plot.load_csv(source), source, plot.load_config())

    ax = fig.axes[0]
    renderer = fig.canvas.get_renderer()
    columns = {}
    for label in ax.texts:
        columns.setdefault(label.xy[0], []).append(label.get_window_extent(renderer))
    assert ax.texts
    for boxes in columns.values():
        for i, a in enumerate(boxes):
            for b in boxes[i + 1 :]:
                assert a.y0 >= b.y1 - 0.5 or b.y0 >= a.y1 - 0.5


def test_backlog_end_labels_stay_on_their_points_with_the_right_values(stage, workdir):
    stage("pr_flow_backlog.csv")
    source = plot.resolve_source("backlog", "accumulated", "2026")

    ax = plot.render(plot.load_csv(source), source, plot.load_config()).axes[0]

    # March 2026: es 1, ko 1, pt 2 overlap and are nudged, never moved off their value
    assert sorted(label.get_text() for label in ax.texts) == ["1", "1", "2"]
    assert sorted(label.xy[1] for label in ax.texts) == [1, 1, 2]
