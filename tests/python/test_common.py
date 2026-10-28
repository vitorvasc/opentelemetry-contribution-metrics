import pandas as pd
import pytest

from common import fail, load_json, to_utc_naive, write_csv

HINT = "make fetch-something"


def test_fail_exits_non_zero_with_message(capsys):
    with pytest.raises(SystemExit) as exc:
        fail("boom")

    assert exc.value.code == 1
    assert "Error: boom" in capsys.readouterr().err


def test_load_json_reads_records(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]')

    df = load_json(path, HINT)

    assert list(df.columns) == ["a", "b"]
    assert df["a"].tolist() == [1, 2]


def test_load_json_missing_file_names_the_make_target(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        load_json(tmp_path / "missing.json", HINT)

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "missing.json not found" in err
    assert f"'{HINT}'" in err


@pytest.mark.parametrize(
    "content, expected",
    [
        ("[]", "has no records"),
        ("", "could not read"),
        ("{not json", "could not read"),
    ],
    ids=["empty-list", "zero-bytes", "invalid-json"],
)
def test_load_json_rejects_unusable_files(tmp_path, capsys, content, expected):
    path = tmp_path / "data.json"
    path.write_text(content)

    with pytest.raises(SystemExit) as exc:
        load_json(path, HINT)

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert expected in err
    assert f"'{HINT}'" in err


def test_write_csv_creates_parent_directory_and_skips_index(tmp_path):
    path = tmp_path / "nested" / "out.csv"

    write_csv(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}), path)

    assert path.read_text() == "a,b\n1,x\n2,y\n"


def test_to_utc_naive_normalizes_every_input_flavor():
    aware_utc = pd.Series(pd.to_datetime(["2025-01-01T10:00:00Z"]))
    offset = pd.Series(["2025-01-01T05:00:00-05:00"])
    naive = pd.Series(["2025-01-01 10:00:00"])
    expected = pd.Timestamp("2025-01-01 10:00:00")

    for series in (aware_utc, offset, naive):
        result = to_utc_naive(series)

        assert result.dt.tz is None
        assert result.iloc[0] == expected
