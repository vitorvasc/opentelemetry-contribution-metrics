import pandas as pd
import pytest

import pr_flow_to_csv as pr_flow
from common import load_json

# 2026-03-15 12:00 UTC: the current month is March
TODAY = pd.Timestamp("2026-03-15 12:00", tz="UTC")


@pytest.fixture
def records(fixtures_dir):
    return load_json(fixtures_dir / "pr_flow.json", pr_flow.FETCH_HINT)


@pytest.fixture
def fixed_now(monkeypatch):
    monkeypatch.setattr(pr_flow, "utc_now", lambda: TODAY)


def prs(*rows):
    """Records of (lang, created_at, closed_at, merged_at); use None for absent."""
    return pd.DataFrame(rows, columns=["lang", "created_at", "closed_at", "merged_at"])


def cell(df, month, lang, column):
    return df.loc[(df["month"] == month) & (df["lang"] == lang), column].item()


# ---------- window ----------


def test_window_months_stops_at_the_current_month_of_the_current_year():
    months = pr_flow.window_months("2026", TODAY)

    assert [str(m) for m in months] == ["2026-01", "2026-02", "2026-03"]


def test_window_months_keeps_a_past_year_whole_and_drops_a_future_one():
    assert len(pr_flow.window_months("2025", TODAY)) == 12
    assert pr_flow.window_months("2027", TODAY) == []


def test_window_months_includes_the_current_month_on_its_first_day():
    months = pr_flow.window_months("2026", pd.Timestamp("2026-02-01"))

    assert [str(m) for m in months] == ["2026-01", "2026-02"]


# ---------- time to merge ----------


def test_time_to_merge_computes_median_p90_and_count(records):
    result = pr_flow.time_to_merge(records, "2026", TODAY)

    assert list(result.columns) == ["month", "lang", "median_days", "p90_days", "count"]
    # 71, 0.25, 2 and 10 days: the median is (2 + 10) / 2 and the p90 sits 70%
    # of the way from 10 to 71
    assert cell(result, "2026-01", "pt", "median_days") == 6.0
    assert cell(result, "2026-01", "pt", "p90_days") == 52.7
    assert cell(result, "2026-01", "pt", "count") == 4
    # A single PR is its own median and p90: 1 day 12 hours
    assert cell(result, "2026-01", "es", "median_days") == 1.5
    assert cell(result, "2026-01", "es", "p90_days") == 1.5
    assert cell(result, "2026-03", "es", "median_days") == 2.0


def test_time_to_merge_rounds_days_to_two_decimals(records):
    # 2 days and 4.5 hours is 2.1875 days
    result = pr_flow.time_to_merge(records, "2026", TODAY)

    assert cell(result, "2026-02", "pt", "median_days") == 2.19


def test_time_to_merge_leaves_a_gap_for_a_month_without_merges(records):
    result = pr_flow.time_to_merge(records, "2026", TODAY)

    for month, lang in [("2026-02", "es"), ("2026-03", "pt"), ("2026-01", "ko")]:
        assert cell(result, month, lang, "count") == 0
        assert pd.isna(cell(result, month, lang, "median_days"))
        assert pd.isna(cell(result, month, lang, "p90_days"))


def test_time_to_merge_has_a_row_for_every_month_and_language(records):
    result = pr_flow.time_to_merge(records, "2026", TODAY)

    assert len(result) == 9
    assert result["month"].tolist() == ["2026-01"] * 3 + ["2026-02"] * 3 + ["2026-03"] * 3
    assert result["lang"].tolist() == ["es", "ko", "pt"] * 3
    assert result["count"].dtype.kind == "i"


def test_time_to_merge_leaves_out_closed_pull_requests_that_were_not_merged(records):
    # The PR closed unmerged in February would have been the fifth of January's pt
    result = pr_flow.time_to_merge(records, "2026", TODAY)

    assert cell(result, "2026-01", "pt", "count") == 4
    assert cell(result, "2026-02", "pt", "count") == 1
    assert result["count"].sum() == 7


def test_time_to_merge_counts_a_pr_merged_in_the_month_it_was_created():
    df = prs(("pt", "2026-01-05T12:00:00Z", "2026-01-05T18:00:00Z", "2026-01-05T18:00:00Z"))

    result = pr_flow.time_to_merge(df, "2026", TODAY)

    assert cell(result, "2026-01", "pt", "median_days") == 0.25
    assert cell(result, "2026-01", "pt", "count") == 1


def test_time_to_merge_counts_a_pr_in_the_month_it_was_merged_not_created(records):
    result = pr_flow.time_to_merge(records, "2026", TODAY)

    # Created in November 2025 and merged in January 2026
    assert cell(result, "2026-01", "pt", "count") == 4
    assert pr_flow.time_to_merge(records, "2025", TODAY)["count"].sum() == 1


def test_time_to_merge_buckets_by_utc_month():
    # 23:30 on January 31 at UTC-5 is 04:30 on February 1 in UTC
    df = prs(
        ("pt", "2026-01-31T00:00:00Z", "2026-01-31T23:30:00-05:00", "2026-01-31T23:30:00-05:00")
    )

    result = pr_flow.time_to_merge(df, "2026", TODAY)

    assert cell(result, "2026-01", "pt", "count") == 0
    assert cell(result, "2026-02", "pt", "count") == 1
    assert cell(result, "2026-02", "pt", "median_days") == 1.19


def test_time_to_merge_measures_the_duration_in_utc():
    # 00:00 at UTC+2 is 22:00 the day before; a merge 24 hours later is one day
    df = prs(("pt", "2026-01-01T00:00:00+02:00", "2026-01-01T22:00:00Z", "2026-01-01T22:00:00Z"))

    result = pr_flow.time_to_merge(df, "2026", TODAY)

    assert cell(result, "2026-01", "pt", "median_days") == 1.0


def test_time_to_merge_without_any_merge_has_only_gaps():
    df = prs(("pt", "2026-01-01T00:00:00Z", None, None))

    result = pr_flow.time_to_merge(df, "2026", TODAY)

    assert result["count"].tolist() == [0, 0, 0]
    assert result["median_days"].isna().all()


def test_time_to_merge_of_a_future_year_is_empty(records):
    result = pr_flow.time_to_merge(records, "2027", TODAY)

    assert result.empty
    assert list(result.columns) == ["month", "lang", "median_days", "p90_days", "count"]


def test_time_to_merge_does_not_modify_its_input(records):
    before = records.copy()

    pr_flow.time_to_merge(records, "2026", TODAY)

    pd.testing.assert_frame_equal(records, before)


# ---------- open backlog ----------


def test_open_backlog_counts_the_open_pull_requests_at_each_month_end(records):
    result = pr_flow.open_backlog(records, "2026", TODAY)

    assert list(result.columns) == ["month", "lang", "open_prs"]
    assert result["month"].tolist() == ["2026-01"] * 3 + ["2026-02"] * 3 + ["2026-03"] * 3
    assert result["lang"].tolist() == ["es", "ko", "pt"] * 3
    # pt in January: the PR from June 2025, the one created on January 28 and
    # the one created on January 30, both closed in February
    assert result["open_prs"].tolist() == [0, 0, 3, 0, 1, 2, 1, 1, 2]


def test_open_backlog_counts_pull_requests_created_before_the_year(records):
    result = pr_flow.open_backlog(records, "2025", TODAY)

    assert len(result) == 36
    pt = result[result["lang"] == "pt"]["open_prs"].tolist()
    # Open since June 1 (206), joined by the one from November 10 (201), which
    # merged in January 2026; the one of March 2025 was closed within the month
    assert pt == [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2]
    assert result[result["lang"] != "pt"]["open_prs"].sum() == 0


def test_open_backlog_drops_a_pull_request_closed_without_a_merge(records):
    result = pr_flow.open_backlog(records, "2026", TODAY)

    # Created on January 28 and closed unmerged on February 10: open at the end
    # of January only
    unmerged_only = records[records["number"] == 205]
    alone = pr_flow.open_backlog(unmerged_only, "2026", TODAY)
    assert alone["open_prs"].tolist() == [1, 0, 0]
    assert cell(result, "2026-02", "pt", "open_prs") == 2


def test_open_backlog_ends_the_current_month_at_today():
    df = prs(("pt", "2026-03-14T00:00:00Z", None, None))

    before = pr_flow.open_backlog(df, "2026", pd.Timestamp("2026-03-13 12:00", tz="UTC"))
    after = pr_flow.open_backlog(df, "2026", pd.Timestamp("2026-03-15 12:00", tz="UTC"))

    assert cell(before, "2026-03", "pt", "open_prs") == 0
    assert cell(after, "2026-03", "pt", "open_prs") == 1


def test_open_backlog_accepts_a_naive_or_aware_today():
    df = prs(("pt", "2026-03-14T00:00:00Z", None, None))

    aware = pr_flow.open_backlog(df, "2026", pd.Timestamp("2026-03-15 12:00", tz="UTC"))
    naive = pr_flow.open_backlog(df, "2026", pd.Timestamp("2026-03-15 12:00"))

    pd.testing.assert_frame_equal(aware, naive)


def test_open_backlog_decides_at_the_last_instant_of_the_month():
    df = prs(
        ("a", "2025-12-01T00:00:00Z", "2026-01-31T23:59:59Z", None),
        ("b", "2025-12-01T00:00:00Z", "2026-02-01T00:00:00Z", None),
        ("c", "2026-01-31T23:59:59Z", None, None),
        ("d", "2026-02-01T00:00:00Z", None, None),
    )

    result = pr_flow.open_backlog(df, "2026", TODAY)

    january = result[result["month"] == "2026-01"].set_index("lang")["open_prs"]
    assert january.to_dict() == {"a": 0, "b": 1, "c": 1, "d": 0}


def test_open_backlog_closes_a_merged_pull_request_that_has_no_close_date():
    df = prs(("pt", "2026-01-01T00:00:00Z", None, "2026-01-10T00:00:00Z"))

    result = pr_flow.open_backlog(df, "2026", TODAY)

    assert result["open_prs"].tolist() == [0, 0, 0]


def test_open_backlog_converts_offsets_to_utc():
    # Created at 00:30 on February 1 at UTC+1, which is still January 31 in UTC
    df = prs(("pt", "2026-02-01T00:30:00+01:00", None, None))

    result = pr_flow.open_backlog(df, "2026", TODAY)

    assert result["open_prs"].tolist() == [1, 1, 1]


def test_open_backlog_of_a_future_year_is_empty(records):
    result = pr_flow.open_backlog(records, "2027", TODAY)

    assert result.empty
    assert list(result.columns) == ["month", "lang", "open_prs"]


def test_open_backlog_does_not_modify_its_input(records):
    before = records.copy()

    pr_flow.open_backlog(records, "2026", TODAY)

    pd.testing.assert_frame_equal(records, before)


# ---------- main ----------


def test_main_writes_both_csvs(stage, workdir, monkeypatch, fixed_now, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2026")

    pr_flow.main()

    durations = pd.read_csv(workdir / "data" / "pr_flow_time_to_merge.csv")
    assert list(durations.columns) == ["month", "lang", "median_days", "p90_days", "count"]
    assert len(durations) == 9
    assert cell(durations, "2026-01", "pt", "p90_days") == 52.7
    backlog = pd.read_csv(workdir / "data" / "pr_flow_backlog.csv")
    assert list(backlog.columns) == ["month", "lang", "open_prs"]
    assert backlog["open_prs"].tolist() == [0, 0, 3, 0, 1, 2, 1, 1, 2]
    printed = capsys.readouterr().out
    assert "converted 13 PRs" in printed
    assert "PRs merged in 2026: 7" in printed
    assert "Open PRs at the end of 2026-03: 4" in printed


def test_main_writes_a_gap_as_an_empty_cell(stage, workdir, monkeypatch, fixed_now):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2026")

    pr_flow.main()

    lines = (workdir / "data" / "pr_flow_time_to_merge.csv").read_text().splitlines()
    assert "2026-01,ko,,,0" in lines
    assert "2026-01,pt,6.0,52.7,4" in lines


def test_main_defaults_the_year_and_the_trim_to_the_same_utc_now(stage, workdir, fixed_now):
    stage("pr_flow.json")

    pr_flow.main()

    backlog = pd.read_csv(workdir / "data" / "pr_flow_backlog.csv")
    assert backlog["month"].unique().tolist() == ["2026-01", "2026-02", "2026-03"]


def test_main_plots_a_past_year_from_the_same_data(stage, workdir, monkeypatch, fixed_now):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2025")

    pr_flow.main()

    durations = pd.read_csv(workdir / "data" / "pr_flow_time_to_merge.csv")
    assert durations["month"].nunique() == 12
    assert durations["count"].sum() == 1


def test_main_fails_when_the_year_has_no_merged_prs(stage, workdir, monkeypatch, fixed_now, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2024")

    with pytest.raises(SystemExit) as exc:
        pr_flow.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no merged PRs in 2024" in err
    assert "found: 2025, 2026" in err
    assert "make plot-pr-flow YEAR=2026" in err
    assert not (workdir / "data" / "pr_flow_time_to_merge.csv").exists()
    assert not (workdir / "data" / "pr_flow_backlog.csv").exists()


def test_main_fails_for_a_year_that_has_not_started(stage, monkeypatch, fixed_now, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2027")

    with pytest.raises(SystemExit) as exc:
        pr_flow.main()

    assert exc.value.code == 1
    assert "no merged PRs in 2027" in capsys.readouterr().err


def test_main_suggests_fetching_when_nothing_was_ever_merged(workdir, fixed_now, capsys):
    (workdir / "data" / "pr_flow.json").write_text(
        '[{"lang": "pt", "created_at": "2026-01-01T00:00:00Z", "closed_at": null,'
        ' "merged_at": null}]'
    )

    with pytest.raises(SystemExit):
        pr_flow.main()

    err = capsys.readouterr().err
    assert "found: no merges" in err
    assert "make fetch-pr-flow" in err


def test_main_fails_on_invalid_year(stage, monkeypatch, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "abc")

    with pytest.raises(SystemExit) as exc:
        pr_flow.main()

    assert exc.value.code == 1
    assert "YEAR must be a four-digit year" in capsys.readouterr().err


def test_main_fails_with_the_fetch_command_when_the_data_is_missing(workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        pr_flow.main()

    assert exc.value.code == 1
    assert "make fetch-pr-flow" in capsys.readouterr().err


def test_main_fails_on_empty_input(workdir, capsys):
    (workdir / "data" / "pr_flow.json").write_text("[]")

    with pytest.raises(SystemExit) as exc:
        pr_flow.main()

    assert exc.value.code == 1
    assert "make fetch-pr-flow" in capsys.readouterr().err
    assert not (workdir / "data" / "pr_flow_backlog.csv").exists()
