import pandas as pd
import pytest

import coverage_to_csv as coverage_csv
from common import load_json


@pytest.fixture
def snapshot(fixtures_dir):
    return load_json(fixtures_dir / "coverage_snapshot.json", coverage_csv.FETCH_HINT)


def test_rank_coverage_orders_from_most_to_least_covered(snapshot):
    result = coverage_csv.rank_coverage(snapshot)

    assert result["lang"].tolist() == [
        "pt",
        "ja",
        "zh",
        "es",
        "fr",
        "uk",
        "ro",
        "bn",
        "ko",
        "pl",
    ]
    assert result["coverage_pct"].is_monotonic_decreasing


def test_rank_coverage_breaks_ties_by_language_code(snapshot):
    tied = snapshot[snapshot["lang"].isin(["uk", "fr"])]

    assert coverage_csv.rank_coverage(tied)["lang"].tolist() == ["fr", "uk"]


def test_rank_coverage_keeps_languages_without_content_at_the_bottom(snapshot):
    empty = pd.DataFrame(
        [{"lang": "ko", "coverage_pct": 0.0, "lang_files": 0, "en_files": 1180, "as_of": "x"}]
    )

    result = coverage_csv.rank_coverage(pd.concat([empty, snapshot], ignore_index=True))

    assert result["lang"].iloc[-1] == "ko"
    assert result["coverage_pct"].iloc[-1] == 0.0


def test_rank_coverage_does_not_modify_its_input(snapshot):
    before = snapshot.copy()

    coverage_csv.rank_coverage(snapshot)

    pd.testing.assert_frame_equal(snapshot, before)


def test_main_writes_the_ranked_csv(stage, workdir, capsys):
    stage("coverage_snapshot.json")

    coverage_csv.main()

    out = pd.read_csv(workdir / "data" / "coverage_snapshot.csv")
    assert list(out.columns) == ["lang", "coverage_pct", "lang_files", "en_files", "as_of"]
    assert out["lang"].iloc[0] == "pt"
    assert len(out) == 10
    assert out["as_of"].eq("2025-06-15").all()
    printed = capsys.readouterr().out
    assert "converted 10 languages" in printed
    assert "Most covered: pt (50.8%)" in printed


def test_main_writes_percentages_with_one_decimal(workdir):
    record = '{"lang": "%s", "coverage_pct": %s, "lang_files": 2, "en_files": 796, "as_of": "x"}'
    (workdir / "data" / "coverage_snapshot.json").write_text(
        "[" + record % ("pl", "0.3") + "," + record % ("ko", "7.5") + "]"
    )

    coverage_csv.main()

    lines = (workdir / "data" / "coverage_snapshot.csv").read_text().splitlines()
    assert lines[1:] == ["ko,7.5,2,796,x", "pl,0.3,2,796,x"]


def test_main_fails_with_the_fetch_command_when_the_data_is_missing(workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        coverage_csv.main()

    assert exc.value.code == 1
    assert "make fetch-coverage" in capsys.readouterr().err


def test_main_fails_on_empty_input(workdir, capsys):
    (workdir / "data" / "coverage_snapshot.json").write_text("[]")

    with pytest.raises(SystemExit) as exc:
        coverage_csv.main()

    assert exc.value.code == 1
    assert "make fetch-coverage" in capsys.readouterr().err
    assert not (workdir / "data" / "coverage_snapshot.csv").exists()
