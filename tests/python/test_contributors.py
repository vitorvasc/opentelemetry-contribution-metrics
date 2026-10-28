import pandas as pd
import pytest

import contributors_to_csv as contributors

# 2026-03-15 12:00 UTC: the current month is March
TODAY = pd.Timestamp("2026-03-15 12:00", tz="UTC")


@pytest.fixture
def fixed_now(monkeypatch):
    monkeypatch.setattr(contributors, "utc_now", lambda: TODAY)


def prs(*rows):
    """Records of (lang, author, created_at, author_type); use None for absent."""
    return pd.DataFrame(rows, columns=["lang", "author", "created_at", "author_type"])


# Who opened what, by month:
#   pt: ana in 2025-11, 2026-01 and 2026-02; bia twice in 2026-01 and in 2026-03;
#       cau in 2026-02; eli in 2026-04, after the current month
#   es: ana in 2026-02 (her first es PR), dan in 2026-03
#   ko: only a bot typed as one, a bot login typed as a user, and a deleted account
HISTORY = prs(
    ("pt", "ana", "2025-11-10T08:00:00Z", "User"),
    ("pt", "ana", "2026-01-05T12:00:00Z", "User"),
    ("pt", "bia", "2026-01-10T00:00:00Z", "User"),
    ("pt", "bia", "2026-01-20T00:00:00Z", "User"),
    ("pt", "cau", "2026-02-03T00:00:00Z", "User"),
    ("pt", "ana", "2026-02-15T00:00:00Z", "User"),
    ("pt", "bia", "2026-03-01T00:00:00Z", "User"),
    ("pt", "eli", "2026-04-02T00:00:00Z", "User"),
    ("es", "ana", "2026-02-20T00:00:00Z", "User"),
    ("es", "dan", "2026-03-02T00:00:00Z", "User"),
    ("ko", "octo-app", "2026-01-05T00:00:00Z", "Bot"),
    ("ko", "renovate[bot]", "2026-01-06T00:00:00Z", "User"),
    ("ko", None, "2026-01-07T00:00:00Z", None),
)


def cell(df, month, lang, column):
    return df.loc[(df["month"] == month) & (df["lang"] == lang), column].item()


def counts(df, month, lang):
    """The (unique, new, returning) counts of a month and language."""
    return tuple(cell(df, month, lang, column) for column in ("unique", "new", "returning"))


# ---------- monthly ----------


def test_monthly_contributors_counts_unique_new_and_returning_authors():
    result = contributors.monthly_contributors(HISTORY, "2026", TODAY)

    assert list(result.columns) == ["month", "lang", "unique", "new", "returning"]
    # ana started in 2025 and bia is new, with two PRs counted once
    assert counts(result, "2026-01", "pt") == (2, 1, 1)
    # cau is new, ana is back
    assert counts(result, "2026-02", "pt") == (2, 1, 1)
    # bia opened her first PR in January
    assert counts(result, "2026-03", "pt") == (1, 0, 1)


def test_monthly_contributors_counts_an_author_once_however_many_prs_they_opened():
    result = contributors.monthly_contributors(HISTORY, "2026", TODAY)

    # Three PRs in January, by ana, bia and bia again
    assert cell(result, "2026-01", "pt", "unique") == 2


def test_monthly_contributors_finds_the_first_pr_over_all_time_not_only_the_year():
    in_2026 = contributors.monthly_contributors(HISTORY, "2026", TODAY)
    in_2025 = contributors.monthly_contributors(HISTORY, "2025", TODAY)

    # ana's first PR is from November 2025, so January 2026 finds her returning
    assert counts(in_2026, "2026-01", "pt") == (2, 1, 1)
    assert counts(in_2025, "2025-11", "pt") == (1, 1, 0)
    assert in_2025["unique"].sum() == 1


def test_monthly_contributors_makes_an_author_new_in_each_language():
    result = contributors.monthly_contributors(HISTORY, "2026", TODAY)

    # ana contributed to pt since 2025, but this is her first es PR
    assert counts(result, "2026-02", "es") == (1, 1, 0)
    assert counts(result, "2026-02", "pt") == (2, 1, 1)


def test_monthly_contributors_makes_an_author_returning_after_the_first_month_in_the_year():
    df = prs(
        ("pt", "ana", "2026-01-05T00:00:00Z", "User"),
        ("pt", "ana", "2026-03-05T00:00:00Z", "User"),
    )

    result = contributors.monthly_contributors(df, "2026", TODAY)

    assert [counts(result, month, "pt") for month in ("2026-01", "2026-02", "2026-03")] == [
        (1, 1, 0),
        (0, 0, 0),
        (1, 0, 1),
    ]


def test_monthly_contributors_leaves_out_bots_and_authors_without_an_account():
    result = contributors.monthly_contributors(HISTORY, "2026", TODAY)

    # ko has a Bot-typed app, a `[bot]` login typed as a user and a null author
    ko = result[result["lang"] == "ko"]
    assert len(ko) == 3
    assert ko[["unique", "new", "returning"]].sum().sum() == 0


def test_monthly_contributors_leaves_out_a_bot_whatever_the_signal():
    df = prs(
        ("pt", "typed", "2026-01-05T00:00:00Z", "Bot"),
        ("pt", "named[bot]", "2026-01-05T00:00:00Z", "User"),
        ("pt", "both[bot]", "2026-01-05T00:00:00Z", "Bot"),
        ("pt", "person", "2026-01-05T00:00:00Z", "User"),
        ("pt", "unknown-type", "2026-01-05T00:00:00Z", None),
    )

    result = contributors.monthly_contributors(df, "2026", TODAY)

    assert counts(result, "2026-01", "pt") == (2, 2, 0)


def test_monthly_contributors_keeps_a_language_that_only_bots_contributed_to():
    df = prs(
        ("pt", "ana", "2026-01-05T00:00:00Z", "User"),
        ("ko", "octo-app", "2026-01-05T00:00:00Z", "Bot"),
    )

    result = contributors.monthly_contributors(df, "2026", TODAY)

    assert sorted(result["lang"].unique()) == ["ko", "pt"]
    assert counts(result, "2026-01", "ko") == (0, 0, 0)


def test_monthly_contributors_handles_data_where_no_pr_has_an_author():
    df = prs(("pt", None, "2026-01-05T00:00:00Z", None))

    result = contributors.monthly_contributors(df, "2026", TODAY)

    assert result[["unique", "new", "returning"]].sum().sum() == 0
    assert len(result) == 3


def test_monthly_contributors_has_a_zero_for_every_month_and_language_without_authors():
    result = contributors.monthly_contributors(HISTORY, "2026", TODAY)

    assert len(result) == 9
    assert result["month"].tolist() == ["2026-01"] * 3 + ["2026-02"] * 3 + ["2026-03"] * 3
    assert result["lang"].tolist() == ["es", "ko", "pt"] * 3
    # Nobody opened an es PR in January: a zero, not a gap
    assert counts(result, "2026-01", "es") == (0, 0, 0)
    for column in ("unique", "new", "returning"):
        assert result[column].dtype.kind == "i"


def test_monthly_contributors_stops_at_the_current_month():
    result = contributors.monthly_contributors(HISTORY, "2026", TODAY)

    assert result["month"].unique().tolist() == ["2026-01", "2026-02", "2026-03"]
    # eli's PR is from April, after the current month
    assert result[result["lang"] == "pt"]["unique"].tolist() == [2, 2, 1]


def test_monthly_contributors_keeps_a_past_year_whole():
    result = contributors.monthly_contributors(HISTORY, "2025", TODAY)

    assert len(result) == 36
    assert result["month"].nunique() == 12


def test_monthly_contributors_of_a_future_year_is_empty():
    result = contributors.monthly_contributors(HISTORY, "2027", TODAY)

    assert result.empty
    assert list(result.columns) == ["month", "lang", "unique", "new", "returning"]


def test_monthly_contributors_counts_the_prs_of_any_state():
    df = prs(
        ("pt", "open", "2026-01-05T00:00:00Z", "User"),
        ("pt", "merged", "2026-01-05T00:00:00Z", "User"),
        ("pt", "closed", "2026-01-05T00:00:00Z", "User"),
    )
    df["state"] = ["open", "closed", "closed"]
    df["merged_at"] = [None, "2026-01-06T00:00:00Z", None]

    result = contributors.monthly_contributors(df, "2026", TODAY)

    assert counts(result, "2026-01", "pt") == (3, 3, 0)


def test_monthly_contributors_buckets_by_utc_month():
    # 23:30 on January 31 at UTC-5 is 04:30 on February 1 in UTC
    df = prs(("pt", "ana", "2026-01-31T23:30:00-05:00", "User"))

    result = contributors.monthly_contributors(df, "2026", TODAY)

    assert counts(result, "2026-01", "pt") == (0, 0, 0)
    assert counts(result, "2026-02", "pt") == (1, 1, 0)


def test_monthly_contributors_does_not_modify_its_input():
    before = HISTORY.copy()

    contributors.monthly_contributors(HISTORY, "2026", TODAY)

    pd.testing.assert_frame_equal(HISTORY, before)


# ---------- yearly ----------


def test_yearly_contributors_sums_up_the_window_per_language():
    result = contributors.yearly_contributors(HISTORY, "2026", TODAY)

    assert list(result.columns) == ["year", "lang", "unique", "new", "returning"]
    assert result["lang"].tolist() == ["es", "ko", "pt"]
    assert result["year"].tolist() == [2026, 2026, 2026]
    rows = result.set_index("lang")[["unique", "new", "returning"]]
    # pt: ana, bia and cau contributed; bia and cau are new, ana started in 2025
    assert rows.loc["pt"].tolist() == [3, 2, 1]
    # es: ana (new to es) and dan
    assert rows.loc["es"].tolist() == [2, 2, 0]
    assert rows.loc["ko"].tolist() == [0, 0, 0]


def test_yearly_contributors_counts_an_author_once_across_months():
    monthly = contributors.monthly_contributors(HISTORY, "2026", TODAY)
    yearly = contributors.yearly_contributors(HISTORY, "2026", TODAY)

    # pt had 2, 2 and 1 contributors in the months, but only 3 different people
    pt_months = monthly[monthly["lang"] == "pt"]
    assert pt_months["unique"].sum() == 5
    assert yearly.set_index("lang").loc["pt", "unique"] == 3


def test_yearly_contributors_new_is_the_sum_of_the_monthly_new():
    monthly = contributors.monthly_contributors(HISTORY, "2026", TODAY)
    yearly = contributors.yearly_contributors(HISTORY, "2026", TODAY)

    by_lang = monthly.groupby("lang")["new"].sum()
    assert yearly.set_index("lang")["new"].to_dict() == by_lang.to_dict()


def test_yearly_contributors_returning_are_those_who_contributed_before_the_year():
    yearly = contributors.yearly_contributors(HISTORY, "2026", TODAY)

    # bia is new in January and back in March, but returning only means seen
    # before the year: that is ana alone
    assert yearly.set_index("lang").loc["pt", "returning"] == 1


def test_yearly_contributors_finds_the_first_pr_over_all_time():
    result = contributors.yearly_contributors(HISTORY, "2025", TODAY)

    assert result.set_index("lang").loc["pt", ["unique", "new", "returning"]].tolist() == [1, 1, 0]


def test_yearly_contributors_leaves_out_what_is_after_the_current_month():
    df = prs(
        ("pt", "ana", "2026-01-05T00:00:00Z", "User"),
        ("pt", "eli", "2026-04-02T00:00:00Z", "User"),
    )

    result = contributors.yearly_contributors(df, "2026", TODAY)

    assert result.loc[0, "unique"] == 1


def test_yearly_contributors_of_a_future_year_is_empty():
    result = contributors.yearly_contributors(HISTORY, "2027", TODAY)

    assert result.empty
    assert list(result.columns) == ["year", "lang", "unique", "new", "returning"]


def test_yearly_contributors_does_not_modify_its_input():
    before = HISTORY.copy()

    contributors.yearly_contributors(HISTORY, "2026", TODAY)

    pd.testing.assert_frame_equal(HISTORY, before)


# ---------- main ----------

# Who is in the shared PR flow fixture:
#   pt: joao (2025-03, 2026-01), ana (2025-06, 2026-01) and maria (2025-11, 2026-01)
#       were all there before 2026; renovate[bot] in 2026-02 is a bot
#   es: carlos in 2026-01 and 2026-03, lucia in 2026-03
#   ko: minho in 2026-02


def test_main_writes_the_monthly_and_the_yearly_csv(stage, workdir, monkeypatch, fixed_now, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2026")

    contributors.main()

    monthly = pd.read_csv(workdir / "data" / "pr_flow_contributors.csv")
    assert list(monthly.columns) == ["month", "lang", "unique", "new", "returning"]
    assert len(monthly) == 9
    assert counts(monthly, "2026-01", "pt") == (3, 0, 3)
    assert counts(monthly, "2026-02", "pt") == (0, 0, 0)
    assert counts(monthly, "2026-01", "es") == (1, 1, 0)
    assert counts(monthly, "2026-03", "es") == (2, 1, 1)
    assert counts(monthly, "2026-02", "ko") == (1, 1, 0)
    yearly = pd.read_csv(workdir / "data" / "pr_flow_contributors_year.csv")
    assert yearly.to_dict("records") == [
        {"year": 2026, "lang": "es", "unique": 2, "new": 2, "returning": 0},
        {"year": 2026, "lang": "ko", "unique": 1, "new": 1, "returning": 0},
        {"year": 2026, "lang": "pt", "unique": 3, "new": 0, "returning": 3},
    ]
    printed = capsys.readouterr().out
    assert "converted 13 PRs" in printed
    assert "pt: 3 contributors in 2026 (0 new, 3 returning)" in printed


def test_main_writes_no_logins(stage, workdir, monkeypatch, fixed_now):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2026")

    contributors.main()

    for name in ("pr_flow_contributors.csv", "pr_flow_contributors_year.csv"):
        text = (workdir / "data" / name).read_text()
        for login in ("maria", "joao", "ana", "carlos", "lucia", "minho", "renovate"):
            assert login not in text


def test_main_defaults_the_year_and_the_trim_to_the_same_utc_now(stage, workdir, fixed_now):
    stage("pr_flow.json")

    contributors.main()

    monthly = pd.read_csv(workdir / "data" / "pr_flow_contributors.csv")
    assert monthly["month"].unique().tolist() == ["2026-01", "2026-02", "2026-03"]


def test_main_plots_a_past_year_from_the_same_data(stage, workdir, monkeypatch, fixed_now):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2025")

    contributors.main()

    monthly = pd.read_csv(workdir / "data" / "pr_flow_contributors.csv")
    assert monthly["month"].nunique() == 12
    # joao in March, ana in June and maria in November, all new
    assert monthly["unique"].sum() == 3
    assert monthly["new"].sum() == 3


def test_main_fails_when_the_year_has_no_contributors(
    stage, workdir, monkeypatch, fixed_now, capsys
):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2024")

    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no contributors in 2024 (found: 2025, 2026)" in err
    assert "make plot-contributors YEAR=2026" in err
    assert not (workdir / "data" / "pr_flow_contributors.csv").exists()
    assert not (workdir / "data" / "pr_flow_contributors_year.csv").exists()


def test_main_fails_for_a_year_that_has_not_started(stage, workdir, monkeypatch, fixed_now, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "2027")

    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "2027 has not started" in err
    assert "make plot-contributors YEAR=2026" in err
    assert not (workdir / "data" / "pr_flow_contributors.csv").exists()


def test_main_suggests_fetching_when_only_bots_contributed(workdir, fixed_now, capsys):
    (workdir / "data" / "pr_flow.json").write_text(
        '[{"lang": "pt", "created_at": "2026-01-01T00:00:00Z", "author": "renovate[bot]",'
        ' "author_type": "Bot"},'
        ' {"lang": "pt", "created_at": "2026-01-02T00:00:00Z", "author": null,'
        ' "author_type": null}]'
    )

    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no contributors in 2026 (found: none)" in err
    assert "make fetch-pr-flow" in err


def test_main_fails_when_the_data_has_no_authors(workdir, fixed_now, capsys):
    (workdir / "data" / "pr_flow.json").write_text(
        '[{"lang": "pt", "created_at": "2026-01-01T00:00:00Z"}]'
    )

    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "author, author_type" in err
    assert "make fetch-pr-flow" in err


def test_main_fails_on_invalid_year(stage, monkeypatch, capsys):
    stage("pr_flow.json")
    monkeypatch.setenv("YEAR", "abc")

    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    assert "YEAR must be a four-digit year" in capsys.readouterr().err


def test_main_fails_with_the_fetch_command_when_the_data_is_missing(workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    assert "make fetch-pr-flow" in capsys.readouterr().err


def test_main_fails_on_empty_input(workdir, capsys):
    (workdir / "data" / "pr_flow.json").write_text("[]")

    with pytest.raises(SystemExit) as exc:
        contributors.main()

    assert exc.value.code == 1
    assert "make fetch-pr-flow" in capsys.readouterr().err
    assert not (workdir / "data" / "pr_flow_contributors.csv").exists()
