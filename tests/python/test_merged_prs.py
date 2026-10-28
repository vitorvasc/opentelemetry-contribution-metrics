import warnings

import pandas as pd
import pytest

import merged_prs_to_csv as merged_csv


def prs(*merged_at):
    return pd.DataFrame({"merged_at": list(merged_at)})


def test_monthly_counts_fills_missing_months_and_accumulates():
    df = prs(
        "2024-01-03T10:00:00Z",
        "2024-01-20T10:00:00Z",
        "2024-03-05T10:00:00Z",
    )

    result = merged_csv.monthly_counts(df, "2024", today=pd.Timestamp("2025-06-01"))

    assert result["month"].tolist() == [f"2024-{m:02d}" for m in range(1, 13)]
    assert result["count"].tolist() == [2, 0, 1] + [0] * 9
    assert result["total"].tolist() == [2, 2, 3] + [3] * 9


def test_monthly_counts_trims_months_after_today_in_current_year():
    df = prs("2026-01-10T10:00:00Z", "2026-03-02T10:00:00Z")

    result = merged_csv.monthly_counts(df, "2026", today=pd.Timestamp("2026-03-15"))

    assert result["month"].tolist() == ["2026-01", "2026-02", "2026-03"]
    assert result["total"].tolist() == [1, 1, 2]


def test_monthly_counts_keeps_current_month_on_its_first_day():
    result = merged_csv.monthly_counts(
        prs("2026-01-10T10:00:00Z"), "2026", today=pd.Timestamp("2026-02-01")
    )

    assert result["month"].tolist() == ["2026-01", "2026-02"]


def test_monthly_counts_keeps_all_months_for_past_year():
    result = merged_csv.monthly_counts(
        prs("2025-12-31T23:59:59Z"), "2025", today=pd.Timestamp("2026-03-15")
    )

    assert len(result) == 12
    assert result["total"].iloc[-1] == 1


def test_monthly_counts_ignores_prs_from_other_years():
    df = prs("2023-12-31T10:00:00Z", "2024-02-01T10:00:00Z", "2025-01-01T10:00:00Z")

    result = merged_csv.monthly_counts(df, "2024", today=pd.Timestamp("2026-03-15"))

    assert result["count"].sum() == 1
    assert result.loc[result["month"] == "2024-02", "count"].item() == 1


def test_monthly_counts_buckets_by_utc_month():
    # 23:30 at UTC-5 on Jan 31 is already February in UTC
    df = prs("2024-01-31T23:30:00-05:00")

    result = merged_csv.monthly_counts(df, "2024", today=pd.Timestamp("2026-03-15"))

    assert result.loc[result["month"] == "2024-01", "count"].item() == 0
    assert result.loc[result["month"] == "2024-02", "count"].item() == 1


def test_monthly_counts_handles_empty_frame():
    df = pd.DataFrame({"number": [], "merged_at": []})

    result = merged_csv.monthly_counts(df, "2024", today=pd.Timestamp("2026-03-15"))

    assert len(result) == 12
    assert result["count"].tolist() == [0] * 12
    assert result["total"].tolist() == [0] * 12


def test_monthly_counts_accepts_timezone_aware_datetimes_without_warning():
    df = pd.DataFrame({"merged_at": pd.to_datetime(["2024-05-05T10:00:00Z"])})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = merged_csv.monthly_counts(df, "2024", today=pd.Timestamp("2026-03-15"))

    assert result.loc[result["month"] == "2024-05", "count"].item() == 1


def test_main_writes_csv_for_requested_year(stage, workdir, monkeypatch):
    stage("merged_prs.json")
    monkeypatch.setenv("YEAR", "2024")

    merged_csv.main()

    out = pd.read_csv(workdir / "data" / "merged_prs_accumulated.csv")
    assert list(out.columns) == ["month", "count", "total"]
    assert len(out) == 12
    assert out["total"].iloc[-1] == 23


def test_main_fails_when_year_has_no_prs(stage, workdir, monkeypatch, capsys):
    stage("merged_prs.json")
    monkeypatch.setenv("YEAR", "2023")

    with pytest.raises(SystemExit) as exc:
        merged_csv.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no merged PRs in 2023" in err
    assert "found: 2024" in err
    assert "make fetch-merged-prs YEAR=2023" in err
    assert not (workdir / "data" / "merged_prs_accumulated.csv").exists()


def test_main_fails_on_invalid_year(stage, monkeypatch, capsys):
    stage("merged_prs.json")
    monkeypatch.setenv("YEAR", "abc")

    with pytest.raises(SystemExit) as exc:
        merged_csv.main()

    assert exc.value.code == 1
    assert "YEAR must be a four-digit year" in capsys.readouterr().err


def test_main_fails_on_empty_input(workdir, capsys):
    (workdir / "data" / "merged_prs.json").write_text("[]")

    with pytest.raises(SystemExit) as exc:
        merged_csv.main()

    assert exc.value.code == 1
    assert "make fetch-merged-prs" in capsys.readouterr().err
