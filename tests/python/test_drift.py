import json

import pandas as pd
import pytest

import drift_to_csv as drift_csv

HEAD = "618851c2c99a69fa925a1578ba0d83398a828c23"


@pytest.fixture
def dataset(fixtures_dir):
    return json.loads((fixtures_dir / "drift.json").read_text())


def language(lang, pages, current=0, drifted=0, unpinned=0, orphan=0, invalid_pin=0):
    return {
        "lang": lang,
        "pages": pages,
        "current": current,
        "drifted": drifted,
        "unpinned": unpinned,
        "orphan": orphan,
        "invalid_pin": invalid_pin,
    }


def make_dataset(*languages):
    return {
        "head": {"sha": HEAD, "committed_at": "2026-10-28T15:48:25Z"},
        "generated_at": "2026-10-28T18:17:04.512Z",
        "languages": list(languages),
        "pages": [],
    }


def test_drift_table_ranks_by_drifted_share_with_languages_without_pages_last(dataset):
    table = drift_csv.drift_table(dataset)

    # es and pt are both half drifted; es has more pages
    assert table["lang"].tolist() == ["es", "pt", "zh", "ja", "ko"]
    assert table["drifted_pct"].tolist()[:4] == [50.0, 50.0, 20.0, 12.5]
    assert pd.isna(table["drifted_pct"].iloc[-1])
    assert list(table.columns) == drift_csv.COLUMNS


def test_drift_table_breaks_full_ties_by_language_code():
    table = drift_csv.drift_table(
        make_dataset(language("uk", 2, current=1, drifted=1), language("pl", 2, 1, 1))
    )

    assert table["lang"].tolist() == ["pl", "uk"]


def test_drift_table_rounds_the_drifted_share_to_one_decimal():
    table = drift_csv.drift_table(make_dataset(language("pt", 3, current=2, drifted=1)))

    assert table["drifted_pct"].iloc[0] == 33.3


def test_drift_table_keeps_every_status_count_and_when_it_was_measured(dataset):
    row = drift_csv.drift_table(dataset).set_index("lang").loc["zh"]

    assert row[drift_csv.STATUSES].tolist() == [1, 1, 0, 0, 3]
    assert row["pages"] == sum(row[drift_csv.STATUSES])
    assert row["as_of"] == "2026-10-28"
    assert row["head_sha"] == HEAD


def test_main_writes_the_ranked_csv(stage, workdir, capsys):
    stage("drift.json")

    drift_csv.main()

    out = pd.read_csv(workdir / "data" / "drift.csv")
    assert list(out.columns) == drift_csv.COLUMNS
    assert out["lang"].tolist() == ["es", "pt", "zh", "ja", "ko"]
    printed = capsys.readouterr().out
    assert "converted 5 languages" in printed
    assert "Upstream commit: 618851c2c99a (2026-10-28)" in printed
    assert "es: 50.0% drifted of 6 pages" in printed
    assert "ko: no translated pages" in printed


def test_main_matches_the_fixture_csv(stage, workdir, fixtures_dir):
    stage("drift.json")

    drift_csv.main()

    assert (workdir / "data" / "drift.csv").read_text() == (fixtures_dir / "drift.csv").read_text()


def test_main_fails_with_the_fetch_command_when_the_data_is_missing(workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        drift_csv.main()

    assert exc.value.code == 1
    assert "make fetch-drift" in capsys.readouterr().err


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"languages": []}', json.dumps(make_dataset({"lang": "pt"}))],
    ids=["invalid", "list", "no-head", "partial-record"],
)
def test_main_fails_on_data_it_cannot_read(content, workdir, capsys):
    (workdir / "data" / "drift.json").write_text(content)

    with pytest.raises(SystemExit) as exc:
        drift_csv.main()

    assert exc.value.code == 1
    assert "make fetch-drift" in capsys.readouterr().err
    assert not (workdir / "data" / "drift.csv").exists()


def test_main_fails_without_any_translated_page(workdir, capsys):
    (workdir / "data" / "drift.json").write_text(json.dumps(make_dataset(language("ko", 0))))

    with pytest.raises(SystemExit) as exc:
        drift_csv.main()

    assert exc.value.code == 1
    assert "has no translated pages" in capsys.readouterr().err
    assert not (workdir / "data" / "drift.csv").exists()
