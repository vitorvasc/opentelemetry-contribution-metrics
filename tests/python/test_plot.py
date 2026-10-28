import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.colors import to_rgb

import plot
from plotting import draw_by_language, draw_series

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


def test_resolve_source_omits_year_from_title_when_unset():
    assert plot.resolve_source("merged", "accumulated").title == "Merged PRs (accumulated)"


def test_resolve_source_ignores_mode_for_language_sources():
    assert plot.resolve_source("prs", "monthly") is plot.SOURCES["prs"]
    assert plot.resolve_source("releases", "monthly") is plot.SOURCES["releases"]


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
