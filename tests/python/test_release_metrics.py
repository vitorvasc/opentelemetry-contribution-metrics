import pandas as pd
import pytest

import release_metrics_to_csv as releases_csv
from common import load_json


@pytest.fixture
def releases(fixtures_dir):
    return load_json(fixtures_dir / "release_metrics.json", releases_csv.FETCH_HINT)


def lang_rows(df, lang):
    return df[df["lang"] == lang].reset_index(drop=True)


def test_accumulate_releases_sums_lines_and_pages_per_language(releases):
    result = releases_csv.accumulate_releases(releases)

    pt = lang_rows(result, "pt")
    assert pt["month"].tolist() == ["2025-01", "2025-02", "2025-03", "2025-04"]
    assert pt["total_lines"].tolist() == [420, 420, 1730, 1980]
    assert pt["total_pages"].tolist() == [3, 3, 15, 16]
    # Totals restart for each language
    assert lang_rows(result, "es")["total_lines"].tolist() == [80, 690, 840, 840]


def test_accumulate_releases_computes_rounded_coverage_change(releases):
    result = releases_csv.accumulate_releases(releases)

    assert lang_rows(result, "pt")["coverage_change"].tolist() == [0.0, 0.0, 2.8, 0.9]
    assert lang_rows(result, "es")["coverage_change"].tolist() == [0.0, 2.3, 0.3, 0.0]
    # Coverage can also drop
    assert lang_rows(result, "de")["coverage_change"].tolist() == [0.0, 0.0, -0.1, 4.7]


def test_accumulate_releases_sorts_by_language_then_month(releases):
    shuffled = releases.sample(frac=1, random_state=1)

    result = releases_csv.accumulate_releases(shuffled)

    assert result[["lang", "month"]].values.tolist() == sorted(
        result[["lang", "month"]].values.tolist()
    )
    assert lang_rows(result, "pt")["total_lines"].tolist() == [420, 420, 1730, 1980]


def test_accumulate_releases_does_not_modify_its_input(releases):
    before = releases.copy()

    releases_csv.accumulate_releases(releases)

    pd.testing.assert_frame_equal(releases, before)


def test_filter_by_year_keeps_only_months_of_that_year(releases):
    older = releases.assign(month=releases["month"].str.replace("2025", "2024"))
    both_years = pd.concat([older, releases], ignore_index=True)

    result = releases_csv.filter_by_year(both_years, "2025")

    assert len(result) == len(releases)
    assert result["month"].str.startswith("2025-").all()


def test_filter_by_year_returns_empty_when_nothing_matches(releases):
    assert releases_csv.filter_by_year(releases, "2024").empty


def test_main_processes_all_months_when_year_is_unset(stage, workdir):
    stage("release_metrics.json")

    releases_csv.main()

    out = pd.read_csv(workdir / "data" / "release_metrics_accumulated.csv")
    assert len(out) == 12
    assert {"total_lines", "total_pages", "coverage_change"} <= set(out.columns)


def test_main_honors_year(stage, workdir, monkeypatch):
    stage("release_metrics.json")
    monkeypatch.setenv("YEAR", "2025")

    releases_csv.main()

    out = pd.read_csv(workdir / "data" / "release_metrics_accumulated.csv")
    assert len(out) == 12


def test_main_fails_when_year_matches_no_month(stage, workdir, monkeypatch, capsys):
    stage("release_metrics.json")
    monkeypatch.setenv("YEAR", "2024")

    with pytest.raises(SystemExit) as exc:
        releases_csv.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no release records for 2024" in err
    assert "2025-01 to 2025-04" in err
    # Leads with replotting the data on disk; fetching is the alternative
    assert err.index("make plot-release-metrics YEAR=2025") < err.index(
        "make fetch-release-metrics YEAR=2024"
    )
    assert not (workdir / "data" / "release_metrics_accumulated.csv").exists()


def test_main_suggests_plotting_the_latest_year_found(workdir, monkeypatch, capsys):
    record = '{"lang": "pt", "month": "%s", "lines_added": 1, "pages_added": 0, "coverage_pct": 1.0}'
    months = ["2025-12", "2026-01", "2026-02"]
    (workdir / "data" / "release_metrics.json").write_text(
        "[" + ",".join(record % month for month in months) + "]"
    )
    monkeypatch.setenv("YEAR", "2024")

    with pytest.raises(SystemExit):
        releases_csv.main()

    assert "make plot-release-metrics YEAR=2026" in capsys.readouterr().err


def test_main_fails_on_empty_input(workdir, capsys):
    (workdir / "data" / "release_metrics.json").write_text("[]")

    with pytest.raises(SystemExit) as exc:
        releases_csv.main()

    assert exc.value.code == 1
    assert "make fetch-release-metrics" in capsys.readouterr().err
