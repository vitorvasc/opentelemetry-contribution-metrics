import pandas as pd
import pytest

import lang_contributions_to_csv as lang_csv
from common import load_json


@pytest.fixture
def contributions(fixtures_dir):
    return load_json(fixtures_dir / "lang_contributions.json", lang_csv.FETCH_HINT)


@pytest.mark.parametrize("type_filter", ["", "both"])
def test_filter_by_type_keeps_everything_for_both(contributions, type_filter):
    result = lang_csv.filter_by_type(contributions, type_filter)

    assert len(result) == len(contributions) == 18


def test_filter_by_type_prs_keeps_only_pull_requests(contributions):
    result = lang_csv.filter_by_type(contributions, "prs")

    assert len(result) == 12
    assert result["url"].str.contains("/pull/").all()


def test_filter_by_type_issues_keeps_only_issues(contributions):
    result = lang_csv.filter_by_type(contributions, "issues")

    assert len(result) == 6
    assert result["url"].str.contains("/issues/").all()


def test_filter_by_type_rejects_unknown_value(contributions):
    with pytest.raises(ValueError, match="bogus"):
        lang_csv.filter_by_type(contributions, "bogus")


def test_accumulate_counts_cumulatively_per_language(contributions):
    prs = lang_csv.filter_by_type(contributions, "prs")

    result = lang_csv.accumulate(prs)

    assert list(result.columns) == ["lang", "date", "count"]
    pt = result[result["lang"] == "pt"]
    # Two PRs share the 2025-02-03 timestamp and count together
    assert pt["count"].tolist() == [1, 3, 4, 5]
    assert pt["date"].is_monotonic_increasing
    assert result.groupby("lang")["count"].max().to_dict() == {"de": 2, "es": 3, "ko": 2, "pt": 5}


def test_accumulate_dates_are_naive_utc(contributions):
    result = lang_csv.accumulate(contributions)

    assert result["date"].dt.tz is None
    first_pt = result[result["lang"] == "pt"].iloc[0]
    assert first_pt["date"] == pd.Timestamp("2025-01-14 09:21:05")


def test_main_writes_accumulated_csv_for_all_types_by_default(stage, workdir):
    stage("lang_contributions.json")

    lang_csv.main()

    out = pd.read_csv(workdir / "data" / "lang_accumulated.csv")
    assert sorted(out["lang"].unique()) == ["de", "es", "ko", "pt", "uk"]
    assert out.groupby("lang")["count"].max().sum() == 18


def test_main_honors_type_from_environment(stage, workdir, monkeypatch):
    stage("lang_contributions.json")
    monkeypatch.setenv("TYPE", "issues")

    lang_csv.main()

    out = pd.read_csv(workdir / "data" / "lang_accumulated.csv")
    assert sorted(out["lang"].unique()) == ["es", "ko", "pt", "uk"]
    assert out.groupby("lang")["count"].max().sum() == 6


def test_main_fails_when_no_item_matches_type(workdir, monkeypatch, capsys):
    only_prs = (
        '[{"lang": "pt", "created_at": "2025-01-01T00:00:00Z", '
        '"url": "https://github.com/o/r/pull/1"}]'
    )
    (workdir / "data" / "lang_contributions.json").write_text(only_prs)
    monkeypatch.setenv("TYPE", "issues")

    with pytest.raises(SystemExit) as exc:
        lang_csv.main()

    assert exc.value.code == 1
    assert "make fetch-lang-contributions TYPE=issues" in capsys.readouterr().err
    assert not (workdir / "data" / "lang_accumulated.csv").exists()


def test_main_fails_on_unknown_type(stage, monkeypatch, capsys):
    stage("lang_contributions.json")
    monkeypatch.setenv("TYPE", "bogus")

    with pytest.raises(SystemExit) as exc:
        lang_csv.main()

    assert exc.value.code == 1
    assert "TYPE must be prs, issues or both" in capsys.readouterr().err


def test_main_fails_on_missing_input(workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        lang_csv.main()

    assert exc.value.code == 1
    assert "make fetch-lang-contributions" in capsys.readouterr().err
