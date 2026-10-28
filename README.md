# OpenTelemetry Contribution Metrics

Visualization tool for tracking accumulated contributions — OpenTelemetry.io.

## Features

- Fetches contribution data from GitHub API
- Filters PRs by language labels (bn, es, fr, ja, ko, pl, pt, ro, uk, zh)
- **Seven tracking modes**:
  - **PR-based**: Track individual PRs over time by language
  - **Release-based**: Measure lines/pages translated per monthly release
  - **Merged PRs**: Track total merged PRs across the entire repository
  - **Translation coverage**: Show how complete each locale is, now and at each monthly release
  - **PR flow**: Show how fast each locale's PRs are merged and how many stay open
  - **Contributors**: Show how many people contribute to each locale and how many are new
  - **Translation drift**: Show what share of each locale's pages is out of date with the English source
- Calculates translation coverage percentages
- Generates accumulated contribution metrics over time
- Creates Grafana-style dark theme visualizations
- Configurable colors and display options
- Shows charts in a window or saves them as PNG files, with no display needed

## Prerequisites

- **Node.js `^22.18.0 || >=24.2.0`** (24 is pinned in `.node-version`). The fetch
  scripts use `import.meta.main`, which older 22.x releases lack
- **Python 3.11+** (3.12 is pinned in `.python-version`)
- **git 2.44+** for the translation drift pipeline, which clones
  opentelemetry.io (it reads the clone with `GIT_NO_LAZY_FETCH`, which older
  git ignores)
- **GitHub Personal Access Token** that can read public repositories: a
  fine-grained token with "Public repositories (read-only)" access and no
  permissions, or a classic token with no scopes

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/vitorvasc/opentelemetry-contribution-metrics.git
cd opentelemetry-contribution-metrics
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your GitHub token:

```bash
GITHUB_TOKEN=ghp_your_token_here
```

Get a token at: https://github.com/settings/tokens

You can export `GITHUB_TOKEN` in your shell instead (for example in CI, where
there is no `.env`). The environment wins over `.env`.

### 3. Install Node.js dependencies

```bash
npm install
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

**Recommended**: Use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

To run the tests and linters, also install the development tools (pytest, Ruff):

```bash
pip install -r requirements-dev.txt
```

### 5. Verify setup

```bash
make setup-check
```

This validates the Node.js and Python versions, the `GITHUB_TOKEN` (from the
environment or `.env`) and the installed dependencies.

## Usage

### Using Make (Recommended)

The tool provides four automated pipelines - each command fetches data, converts
to CSV, and generates visualizations automatically:

#### Language Contributions Pipeline

Track PR and issue contributions by language over time:

```bash
# Fetch, process, and plot all language contributions (PRs + issues)
make fetch-lang-contributions

# Fetch only PRs
make fetch-lang-contributions TYPE=prs

# Fetch only issues
make fetch-lang-contributions TYPE=issues

# Filter by year
make fetch-lang-contributions YEAR=2024

# Filter by specific languages
make fetch-lang-contributions LANGS=pt,es

# Combine filters
make fetch-lang-contributions TYPE=prs YEAR=2024 LANGS=pt,es

# Clean generated data
make clean-lang-contributions
```

#### Release Metrics Pipeline

Track translation metrics by monthly release:

```bash
# Fetch, process, and plot release metrics
make fetch-release-metrics

# Filter by year
make fetch-release-metrics YEAR=2024

# Filter by languages
make fetch-release-metrics LANGS=pt,es YEAR=2024

# Clean generated data
make clean-release-metrics
```

#### Merged PRs Pipeline

Track total merged PRs across the entire repository:

```bash
# Fetch, process, and plot total merged PRs (accumulated line chart)
make fetch-merged-prs

# Filter by year
make fetch-merged-prs YEAR=2024

# Month-over-month bar chart
make fetch-merged-prs MODE=monthly

# Combined: specific year with bar chart
make fetch-merged-prs YEAR=2024 MODE=monthly

# Clean generated data
make clean-merged-prs
```

#### Translation Coverage Pipeline

Show how complete each locale is: the Markdown pages under `content/<lang>/`
as a percentage of the Markdown pages under `content/en/`.

```bash
# Current coverage of every language at the HEAD of the default branch
# (one API request), as a bar chart ranked from most to least covered
make fetch-coverage

# Only some languages
make fetch-coverage LANGS=pt,ja

# Coverage of each language at every monthly release of a year, as a line
# chart, from the release metrics data (see Release Metrics Pipeline)
make fetch-release-metrics YEAR=2024
make plot-coverage-history YEAR=2024

# Clean generated data
make clean-coverage
```

The history has no fetch of its own: it plots the `coverage_pct` that
`make fetch-release-metrics` already records for each release, so it needs that
data first.

#### PR Flow Pipeline

Show how responsive the review of each locale is, from every `lang:*` PR the
repository ever had: the median days from creation to merge per month, and the
PRs still open at each month end.

```bash
# Fetch every localization PR (all time), then draw the median time to merge
# of the current year as a line chart
make fetch-pr-flow

# Draw the PRs open at each month end from the same data
make plot-pr-backlog

# Another year, from the data already fetched (no API calls)
make plot-pr-flow YEAR=2025
make plot-pr-backlog YEAR=2025

# Only some languages
make fetch-pr-flow LANGS=pt,ja

# Clean generated data
make clean-pr-flow
```

The fetch always covers every PR since the repository was created, whatever
`YEAR` is: the backlog needs the PRs created before the year that were still
open, and the [contributors charts](#contributors-pipeline) need every earlier
PR to tell a new contributor from a returning one. `YEAR` only picks the months
drawn. The backlog has no fetch of its own, it plots the data
`make fetch-pr-flow` fetched.

The two charts are independent: each plot target converts only its own CSV, so
a year with open PRs but no merges still draws the backlog (and `make charts`
reports only the time to merge as missing).

#### Contributors Pipeline

Show how big and how healthy each locale's community is: the people who opened
a `lang:*` PR in each month, and how many of them were on their first PR in that
language. It needs no fetch of its own, it uses the PR flow data.

```bash
# Fetch the PR flow data once (all time)
make fetch-pr-flow

# Draw the unique contributors of each month, a line per language
make plot-contributors

# Draw the new contributors of each month, bars stacked by language
make plot-new-contributors

# Another year, from the data already fetched (no API calls)
make plot-contributors YEAR=2025
make plot-new-contributors YEAR=2025
```

Both plot targets convert the data to `data/pr_flow_contributors.csv` (a row per
month and language, read by both charts) and `data/pr_flow_contributors_year.csv`
(a row per language, summing up `YEAR`). The CSVs hold counts only, never the
logins of the contributors. `make clean-pr-flow` removes them with the rest of
the PR flow data.

#### Translation Drift Pipeline

Show what share of each locale's translated pages is out of date with the
English page it translates. It clones opentelemetry.io instead of calling the
GitHub API, so it needs no token, but it needs git 2.44+.

```bash
# Clone opentelemetry.io (first run) or update the clone, then draw one 100%
# bar per language, split into current, drifted, unpinned and orphan pages
make fetch-drift

# Only some languages
make fetch-drift LANGS=pt,es

# Clean generated data (keeps the clone)
make clean-drift

# Remove the clone too
make clean-drift-cache
```

The clone lives in `data/.cache/opentelemetry.io` (set `CLONE_DIR` to move
it). It is a blobless clone with a sparse checkout of the `content/<lang>`
folders, so it holds the whole commit history but only the translated pages.
Measured on the full upstream repository: the first run takes about 11 s and
leaves 37 MB on disk (20 MB of it git history); later runs update the clone in
about 1 s and take about 2 s in all.

`fetch-drift` only updates (`git reset --hard`) a clone it created itself,
which it marks with the `contribution-metrics.cache` git config key, and
`clean-drift-cache` only removes such a clone. Pointing `CLONE_DIR` at your own
checkout of opentelemetry.io fails instead of touching it.

#### All Charts

Run every pipeline and write the charts as PNG files to `out/` (needs
`GITHUB_TOKEN`, no display needed):

```bash
make charts

# Same, for one year and some languages
make charts YEAR=2024 LANGS=pt,es
```

This writes `out/lang-contributions.png`, `out/release-metrics.png`,
`out/merged-prs-accumulated.png`, `out/merged-prs-monthly.png`,
`out/coverage-history.png`, `out/coverage-snapshot.png`, `out/time-to-merge.png`,
`out/backlog.png`, `out/contributors.png`, `out/new-contributors.png` and
`out/drift.png`. The drift chart clones or updates opentelemetry.io (see
[Translation Drift Pipeline](#translation-drift-pipeline)), so `make charts`
also needs git 2.44+ and network access to github.com.

Every chart is attempted even when one fails, for example the release metrics
of a year with no published release. `make charts` then names the charts it
could not write and fails.

To save a single chart, set `OUTPUT` on any `fetch-*` or `plot-*` target:

```bash
make plot-merged-prs OUTPUT=out/merged-prs.png
```

`OUTPUT` (or `--output` when calling `plot.py`) saves the chart instead of
opening a window and creates the folder if needed. On a machine without a
display, also set `MPLBACKEND=Agg`; `make charts` and `make test` already do.

#### Plot Only (no API calls)

Re-process and re-plot the data from the last fetch:

```bash
make plot-lang-contributions
make plot-release-metrics
make plot-merged-prs MODE=monthly
make plot-coverage
make plot-coverage-history
make plot-pr-flow
make plot-pr-backlog
make plot-contributors
make plot-new-contributors
make plot-drift
```

Use the same `YEAR` as the fetch, see [Parameters](#parameters). The PR flow and
contributor charts can show any year from one fetch.

#### Other Commands

```bash
make setup-check  # Verify environment configuration
make test         # JavaScript and Python tests
make lint         # Biome, Ruff and ShellCheck
make help         # Show all available commands
```

### Parameters

Pass parameters on the command line (`make fetch-merged-prs YEAR=2024`) or
through the environment (`YEAR=2024 make fetch-merged-prs`). A parameter that is
unset or empty uses its default.

| Parameter     | Description                                                | Default            | Example                  |
| ------------- | ---------------------------------------------------------- | ------------------ | ------------------------ |
| `YEAR=XXXX`   | Year to fetch and plot                                     | current year (UTC) | `YEAR=2024`              |
| `LANGS=xx,yy` | Languages to fetch (comma-separated)                       | all                | `LANGS=pt,es,fr`         |
| `TYPE=xxx`    | Contribution type: `prs`, `issues` or `both`               | both               | `TYPE=prs`               |
| `MODE=xxx`    | Merged PRs chart: `accumulated` (line) or `monthly` (bars) | accumulated        | `MODE=monthly`           |
| `OUTPUT=PATH` | Save the chart to a file instead of opening a window       | none               | `OUTPUT=out/chart.png`   |
| `CLONE_DIR=PATH` | Where the drift pipeline keeps its opentelemetry.io clone | `data/.cache/opentelemetry.io` | `CLONE_DIR=/tmp/otel-io` |
| `PYTHON=path` | Python interpreter used by `make`                          | `python3`          | `PYTHON=venv/bin/python` |

Not every pipeline reads every parameter:

| Pipeline               | Fetch step              | CSV and plot step |
| ---------------------- | ----------------------- | ----------------- |
| Language contributions | `YEAR`, `LANGS`, `TYPE` | `TYPE`            |
| Release metrics        | `YEAR`, `LANGS`         | `YEAR`            |
| Merged PRs             | `YEAR`                  | `YEAR`, `MODE`    |
| Translation coverage   | `LANGS`                 | none              |
| Coverage history       | (release metrics)       | `YEAR`            |
| PR flow                | `LANGS`                 | `YEAR`            |
| PR backlog             | (PR flow)               | `YEAR`            |
| Contributors           | (PR flow)               | `YEAR`            |
| New contributors       | (PR flow)               | `YEAR`            |
| Translation drift      | `LANGS`, `CLONE_DIR`    | none              |

- `OUTPUT` applies to every plot step.
- Use the same `YEAR` for `plot-*` as for the fetch. The release metrics and
  merged PRs CSV steps exit with a hint when the fetched data has nothing for
  that year (merged PRs also when `YEAR` is unset and the data is not from the
  current year). The language contributions CSV step has no year filter and
  relies on the fetch's.
- The PR flow fetch is all time and ignores `YEAR`; its CSV step takes any
  `YEAR` and exits with a hint for a dataset with nothing to chart: no PR merged
  that year (time to merge), or none created by its end or the year not started
  (backlog). The fetched data covers every year, so re-plot with another `YEAR`
  instead of fetching again. `pr_flow_to_csv.py` writes each CSV that has data
  and, without `--only {time-to-merge,backlog}`, fails at the end if one has not.
- The contributors CSV step reads the PR flow data too and takes any `YEAR`. It
  exits with a hint when nobody contributed that year, or the year has not
  started, and writes nothing then.
- `TYPE` must be `prs`, `issues` or `both`; any other value exits with status 1.
- `MODE` is a `make` parameter. When calling `plot.py` directly, use `--mode`.

### Using npm Scripts

```bash
npm run fetch-lang-contributions  # Language contributions pipeline
npm run fetch-release-metrics     # Release metrics pipeline
npm run fetch-merged-prs          # Merged PRs pipeline
npm run fetch-coverage            # Translation coverage snapshot pipeline
npm run fetch-pr-flow             # PR flow pipeline (time to merge chart)
npm run fetch-drift               # Translation drift pipeline
npm run clean-lang-contributions  # Clean language data
npm run clean-release-metrics     # Clean release data
npm run clean-merged-prs          # Clean merged PRs data
npm run clean-coverage            # Clean coverage data
npm run clean-pr-flow             # Clean PR flow data
npm run clean-drift               # Clean translation drift data (keeps the clone)
npm run setup-check               # Verify setup
npm test                          # JavaScript tests
```

The npm scripts call `python3` and cannot pass `MODE` or `OUTPUT`, so
`npm run fetch-merged-prs` always plots the accumulated chart in a window.
`YEAR`, `LANGS` and `TYPE` still work from the environment, for example
`YEAR=2024 npm run fetch-merged-prs`. Remove the drift clone with
`make clean-drift-cache`, which checks that the folder is a clone the pipeline
made; there is no npm script for it.

### Direct Script Execution

Run the scripts from the project root: the `data/` paths are relative to the
current directory.

```bash
# Language contributions
node scripts/fetch/fetch_lang_issues.js
python3 scripts/processing/lang_contributions_to_csv.py
python3 scripts/processing/plot.py

# Release metrics
node scripts/fetch/fetch_release_metrics.js
python3 scripts/processing/release_metrics_to_csv.py
python3 scripts/processing/plot.py --source=releases

# Merged PRs
node scripts/fetch/fetch_merged_prs.js
python3 scripts/processing/merged_prs_to_csv.py
python3 scripts/processing/plot.py --source=merged

# Translation coverage snapshot
node scripts/fetch/fetch_coverage.js
python3 scripts/processing/coverage_to_csv.py
python3 scripts/processing/plot.py --source=coverage-snapshot

# Coverage history (after fetching the release metrics)
python3 scripts/processing/release_metrics_to_csv.py
python3 scripts/processing/plot.py --source=coverage

# PR flow: time to merge, then the backlog from the same data
node scripts/fetch/fetch_pr_flow.js
python3 scripts/processing/pr_flow_to_csv.py --only=time-to-merge
python3 scripts/processing/plot.py --source=time-to-merge
python3 scripts/processing/pr_flow_to_csv.py --only=backlog
python3 scripts/processing/plot.py --source=backlog

# Contributors: one conversion for both charts, from the same PR flow data
python3 scripts/processing/contributors_to_csv.py
python3 scripts/processing/plot.py --source=contributors
python3 scripts/processing/plot.py --source=new-contributors

# Translation drift (clones or updates data/.cache/opentelemetry.io)
node scripts/fetch/fetch_drift.js
python3 scripts/processing/drift_to_csv.py
python3 scripts/processing/plot.py --source=drift
```

`plot.py` options:

```bash
python3 scripts/processing/plot.py --source {prs,releases,merged,coverage,coverage-snapshot,time-to-merge,backlog,contributors,new-contributors,drift}  # default: prs
python3 scripts/processing/plot.py --mode {accumulated,monthly}    # merged PRs only
python3 scripts/processing/plot.py --output out/chart.png          # save instead of opening a window
```

## Understanding the Pipelines

The tool provides seven complementary ways to track OpenTelemetry contributions:

### Language Contributions Pipeline

Tracks **individual PR and issue contributions** over time:

- **What it tracks**: Every PR/issue with a `lang:*` label
- **Granularity**: One step per PR/issue, at its creation time
- **Use case**: See contribution activity and engagement over time
- **Filters**: Can filter by type (PRs only, issues only, or both)

### Release Metrics Pipeline

Tracks **translation progress by monthly release**:

- **What it tracks**: Lines translated, pages added, coverage % per monthly
  release (YYYY.MM tags)
- **Granularity**: Month-by-month snapshots aligned with OpenTelemetry releases
- **Use case**: Measure actual translation coverage and progress against English
  baseline
- **Data source**: https://github.com/open-telemetry/opentelemetry.io/releases

### Merged PRs Pipeline

Tracks **total merged PRs** across the entire repository:

- **What it tracks**: All merged PRs regardless of labels
- **Granularity**: Month-by-month accumulation based on merge date
- **Use case**: See overall repository activity and merged contribution volume
- **Features**: Monthly date-chunking to handle large volumes, deduplication by PR number

### Translation Coverage Pipeline

Tracks **how complete each locale is**:

- **What it tracks**: Markdown pages in `content/<lang>/` as a percentage of the
  pages in `content/en/`
- **Granularity**: A snapshot of the default branch (`HEAD`) read with a single
  git tree request, plus the per-release history the Release Metrics Pipeline
  already records
- **Use case**: See which languages are furthest along and how fast they are
  catching up with the English content
- **Data source**: https://github.com/open-telemetry/opentelemetry.io, the
  recursive git tree of the default branch

### PR Flow Pipeline

Tracks **how responsive the review of each locale is**:

- **What it tracks**: Every PR with a `lang:*` label since the repository was
  created (`data/pr_flow.json`, with `merged_at`, `author` and `author_type`)
- **Time to merge**: Per language and month of merge (UTC), the median and p90
  of the days from `created_at` to `merged_at`, with the PR count. PRs closed
  without a merge are left out. A language with no merge in a month has no
  value that month (a gap in the line, not a zero)
- **Open backlog**: Per language, the PRs open at the end of each month: created
  by then and not yet closed or merged. A PR closed without a merge leaves the
  backlog when it is closed. The current month is counted as of now
- **Charts**: The median time to merge (`--source=time-to-merge`) and the open
  backlog (`--source=backlog`), one marked line per language. The time to merge
  axis is symmetric log (linear up to 1 day, logarithmic above) labeled in days,
  so sub-day medians stay readable next to the weeks-long medians of small
  languages. The p90 is in the CSV only
- **Use case**: See which locales are waiting for review and which merge quickly
- **Cost**: One repository request and about 40 Search requests for all
  languages (the search of a language over 1000 PRs is split by date range)

### Contributors Pipeline

Tracks **how big and how healthy each locale's community is**, from the PR flow
data (no fetch of its own):

- **Contributor**: An author who opened at least one `lang:<code>` PR in the
  month, by `created_at` (UTC), in any state. Bots (`author_type` of `Bot`, or a
  login ending in `[bot]`) and PRs without an author (deleted accounts) are left
  out
- **New contributor**: The author's first PR in that language, over all the data
  and not only `YEAR`, was opened that month. Someone who contributes to two
  languages is new in each. **Returning** is the unique contributors minus the
  new ones
- **Months**: The months of `YEAR`, up to the current month. A month nobody
  contributed in is a zero, not a gap
- **Yearly summary**: Per language over the months drawn: `unique` counts each
  person once however many months they contributed in (so it is not the sum of
  the monthly values), `new` is the sum of the monthly new, and `returning` is
  `unique` minus `new`: the people who had contributed to the language before
  the months drawn
- **Aggregates only**: The CSVs hold counts per language, no logins and no
  leaderboard
- **Charts**: The unique contributors (`--source=contributors`), one marked line
  per language, and the new contributors (`--source=new-contributors`), bars
  stacked by language with the total on top, which shows the inflow of
  newcomers across the whole localization effort
- **Use case**: See which locales have a growing community, which depend on a
  few people, and how many newcomers keep arriving
- **Cost**: None, it plots the data `make fetch-pr-flow` fetched

### Translation Drift Pipeline

Tracks **how up to date each locale's translated pages are**, with the rules of
upstream's own drift check, `scripts/i18n/drift.mjs` in opentelemetry.io
(checked at commit `618851c`):

- **Pin**: A translated page records the English commit it was translated from
  as `default_lang_commit: <sha>` in its front matter. The first line of the
  file that matches, in any letter case, is the pin; a `# patched` comment after
  it is kept in the per-page data but does not change the status
- **English page**: `content/<lang>/<path>.md` translates
  `content/en/<path>.md` (the same path, `_index.md` included)
- **Pages**: Every `.md` file under `content/<lang>/` at the head of the default
  branch, for the languages in `LANGS`
- **Status**, decided in this order:
  - **orphan**: The English page no longer exists (even if the page is pinned)
  - **unpinned**: The page has no pin
  - **drifted**: The English page changed since the pin, by
    `git diff --name-only <pin>...HEAD -- content/en` (three dots: since the
    common ancestor of the pin and the head)
  - **current**: The English page has not changed since the pin
  - **invalid_pin**: git cannot diff the pin, for example a commit that is not
    in the repository
- **Matches upstream**: On 2026-10-28 the statuses of all 1384 translated pages
  matched the `drifted_from_default` values upstream stores in its pages
- **Chart**: One 100% horizontal bar per language, from the most to the least
  drifted share, with the number of translated pages next to the language. The
  segments are current, drifted, unpinned, orphan and invalid pin, in that
  order and in the `status_colors` of `config.yaml`; a status that no language
  has is left out of the chart and its legend
- **Use case**: See which locales need the most catch-up work after English
  changes, and how large each locale is
- **Cost**: No API requests. One `git diff` per distinct pin (about 620 for all
  languages), about 1 s

### Metrics Calculated

For each release month and language:

1. **Lines Added**: Total lines of translated content added in `.md` files
2. **Pages Added**: Count of new markdown files in `content/{lang}/`
3. **Coverage %**: Markdown files in `content/{lang}/` as a percentage of the
   Markdown files in `content/en/`
4. **Coverage Change**: Month-over-month improvement in coverage
5. **Files Updated**: Count of modified markdown files in `content/{lang}/`
6. **PR Count**: Merged PRs labeled `lang:{lang}` that month

### Output Files

**Language Contributions:**
- `data/lang_contributions.json` - Raw PR/issue data per language
- `data/lang_accumulated.csv` - Cumulative contribution count per language

**Release Metrics:**
- `data/release_metrics.json` - Detailed metrics per release/language
- `data/release_metrics_accumulated.csv` - Accumulated totals for visualization

**Merged PRs:**
- `data/merged_prs.json` - Raw merged PR data (number, merged_at)
- `data/merged_prs_accumulated.csv` - Monthly counts with cumulative totals

**Translation Coverage:**
- `data/coverage_snapshot.json` - Coverage per language at the default branch HEAD
- `data/coverage_snapshot.csv` - The same, ranked from most to least covered

The coverage history has no files of its own: it plots `coverage_pct` from the
release metrics files.

**PR Flow:**
- `data/pr_flow.json` - Every `lang:*` PR since the repository was created
- `data/pr_flow_time_to_merge.csv` - Median days, p90 days and count per month
  and language (empty median and p90 where nothing was merged)
- `data/pr_flow_backlog.csv` - PRs open at each month end per language

**Contributors:**
- `data/pr_flow_contributors.csv` - Unique, new and returning contributors per
  month and language
- `data/pr_flow_contributors_year.csv` - The same per language, summed up over
  the months of `YEAR`

The PR backlog and contributor charts have no fetch of their own: they plot the
PR flow files.

**Translation Drift:**
- `data/drift.json` - The upstream head commit, the counts per language and
  status, and every translated page with its status, pin and `patched` flag
- `data/drift.csv` - The counts per language, with `drifted_pct`, `as_of` and
  `head_sha`, from the most to the least drifted
- `data/.cache/opentelemetry.io/` - The clone, kept by `make clean-drift` and
  removed by `make clean-drift-cache`

**Charts:** `make charts` writes PNG files to `out/`.

### Example Output

`data/release_metrics_accumulated.csv` (illustrative values):

```csv
lang,month,lines_added,pages_added,files_updated,coverage_pct,pr_count,total_lines,total_pages,coverage_change
es,2025-01,892,7,6,25.3,15,892,7,0.0
es,2025-02,654,4,3,28.9,11,1546,11,3.6
pt,2025-01,423,3,2,12.5,8,423,3,0.0
pt,2025-02,567,5,4,18.2,12,990,8,5.7
```

## Configuration

### config.yaml

Customize plot appearance:

```yaml
show_endpoint_values: true # Show/hide numbers at end of lines

colors:
  bn: '#FF6B6B' # Bengali - coral red
  es: '#00FF7F' # Spanish - green
  fr: '#3B82F6' # French - blue
  ja: '#F59E0B' # Japanese - amber
  ko: '#38BDF8' # Korean - sky blue
  pl: '#A3E635' # Polish - lime
  pt: '#A855F7' # Portuguese - purple
  ro: '#EC4899' # Romanian - pink
  uk: '#14B8A6' # Ukrainian - teal
  zh: '#EF4444' # Chinese - red
  total: '#CCCCCC' # Total merged PRs - neutral gray

# Translation drift statuses, from good to bad
status_colors:
  current: '#0CA30C'
  drifted: '#FAB219'
  unpinned: '#8A8A85'
  orphan: '#EC835A'
  invalid_pin: '#D03B3B'
```

### Environment Variables

`GITHUB_TOKEN` (required for `fetch-*` except `fetch-drift`, and for
`charts`), in a `.env` file:

```bash
GITHUB_TOKEN=your_token_here
```

or exported in the shell, which wins over `.env`:

```bash
export GITHUB_TOKEN=your_token_here
```

Command-line parameters (optional, see [Parameters](#parameters)):

```bash
# Filter by languages
make fetch-lang-contributions LANGS=pt,es

# Filter by contribution type
TYPE=prs make fetch-lang-contributions

# Filter by year
YEAR=2024 make fetch-release-metrics

# Save the chart instead of opening a window
make plot-merged-prs OUTPUT=out/merged-prs.png
```

## Project Structure

```
opentelemetry-contribution-metrics/
├── scripts/
│   ├── fetch/                         # Data fetching scripts (Node.js)
│   │   ├── lib/
│   │   │   ├── github.js              # Shared config, GitHub API client (retries, rate limits, search splitting) and JSON output
│   │   │   ├── coverage.js            # Shared git tree fetch and translation coverage calculation
│   │   │   └── drift.js               # Clone handling and translation drift classification
│   │   ├── fetch_lang_issues.js       # Fetches PR-based data from GitHub API
│   │   ├── fetch_release_metrics.js   # Fetches release-based metrics
│   │   ├── fetch_merged_prs.js        # Fetches total merged PRs
│   │   ├── fetch_coverage.js          # Fetches the translation coverage snapshot
│   │   ├── fetch_pr_flow.js           # Fetches every localization PR, all time
│   │   └── fetch_drift.js             # Clones opentelemetry.io and measures translation drift
│   ├── processing/                    # Data processing scripts (Python)
│   │   ├── common.py                      # Shared helpers: JSON loading, CSV writing, error exit
│   │   ├── plotting.py                    # Shared matplotlib styling and drawing helpers
│   │   ├── lang_contributions_to_csv.py   # Converts PR JSON to accumulated CSV
│   │   ├── release_metrics_to_csv.py      # Converts release JSON to accumulated CSV
│   │   ├── merged_prs_to_csv.py           # Converts merged PRs JSON to accumulated CSV
│   │   ├── coverage_to_csv.py             # Ranks the coverage snapshot JSON into a CSV
│   │   ├── pr_flow_to_csv.py              # Computes time to merge and open backlog CSVs
│   │   ├── contributors_to_csv.py         # Computes unique and new contributors per language
│   │   ├── drift_to_csv.py                # Ranks the translation drift per language into a CSV
│   │   └── plot.py                        # Generates visualization (supports all modes)
│   └── check_setup.sh                 # Validates environment setup
├── tests/
│   ├── js/                            # Node.js tests (node --test)
│   └── python/                        # pytest tests and fixtures
├── .github/workflows/ci.yml           # CI: lint, tests, Renovate config, dependency review
├── .github/workflows/charts.yml       # Scheduled chart regeneration, uploaded as a build artifact
├── data/
│   ├── lang_contributions.json        # Raw PR data (generated)
│   ├── lang_accumulated.csv           # Accumulated PR data (generated)
│   ├── release_metrics.json           # Raw release data (generated)
│   ├── release_metrics_accumulated.csv # Accumulated release data (generated)
│   ├── merged_prs.json                # Raw merged PRs data (generated)
│   ├── merged_prs_accumulated.csv     # Accumulated merged PRs data (generated)
│   ├── coverage_snapshot.json         # Raw coverage snapshot (generated)
│   ├── coverage_snapshot.csv          # Ranked coverage snapshot (generated)
│   ├── pr_flow.json                   # Raw localization PRs, all time (generated)
│   ├── pr_flow_time_to_merge.csv      # Time to merge per month and language (generated)
│   ├── pr_flow_backlog.csv            # Open PRs per month end and language (generated)
│   ├── pr_flow_contributors.csv       # Contributors per month and language (generated)
│   ├── pr_flow_contributors_year.csv  # Contributors per language for the year (generated)
│   ├── drift.json                     # Translation drift per page and language (generated)
│   ├── drift.csv                      # Translation drift per language (generated)
│   └── .cache/opentelemetry.io/       # Clone used by the drift pipeline (generated)
├── out/                               # Charts written by make charts (generated, gitignored)
├── config.yaml                        # Plot configuration
├── .env.example                       # Environment template
├── .env                               # Your environment variables (gitignored)
├── .node-version                      # Pinned Node.js version
├── .python-version                    # Pinned Python version
├── .gitignore                         # Git ignore rules
├── Makefile                           # Build automation
├── package.json                       # Node.js dependencies and scripts
├── pytest.ini                         # pytest configuration
├── renovate.json                      # Dependency update configuration
├── requirements.txt                   # Python dependencies
├── requirements-dev.txt               # Python development tools (pytest, Ruff)
└── README.md                          # This file
```

## Development

```bash
make test   # npm test (node --test) and pytest, with MPLBACKEND=Agg
make lint   # Biome, Ruff check and format, ShellCheck
```

To use a virtualenv for the Python side, pass its interpreter:
`make test PYTHON=venv/bin/python`. Run the suites separately with `npm test`
and `MPLBACKEND=Agg python3 -m pytest`. `make lint` expects `ruff` and
`shellcheck` on your `PATH`.

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request:

- **lint**: Ruff (check and format), Biome, ShellCheck, actionlint, zizmor
- **test-js** and **test-python**: the two test suites
- **renovate-config**: validates `renovate.json` in strict mode
- **dependency-review**: flags vulnerable dependency changes (pull requests only)
- **ci**: aggregates all of the above and is the single required check

### Charts workflow

`.github/workflows/charts.yml` runs `make charts` and uploads `out/*.png` and
`data/*.csv` as the `charts-<year>-<run id>-<attempt>` artifact, kept for 90
days. It never commits to the repository. The job summary lists the files and
the GitHub API requests left.

- **Schedule**: monthly, on day 2 at 06:00 UTC. It charts the year of the
  month that just ended (the previous year on January 2) for all languages.
  Upstream `YYYY.MM` releases can be published weeks after their month, so
  it charts the releases published so far.
- **Manual run** (Actions → Charts → Run workflow): optional `year` (four
  digits) and `langs` (comma-separated codes such as `pt,es`, lowercased and
  stripped of spaces). Empty means the current year and all languages. Invalid
  values fail before any request.
- **Pull requests** that change the workflow file run it with `LANGS=pt` and
  the previous year, whose releases are all published.
- **Missing data**: a chart without data (for example no release published
  yet for the year) is skipped. The other charts are still written and
  uploaded, the run ends red, and the job summary lists the charts that were
  not written.
- **Token**: `METRICS_TOKEN` if the secret exists, otherwise the Actions
  `GITHUB_TOKEN`. The Actions token reads public repositories but is limited to
  about 1000 core requests per hour. A full run needs about 1400 core and 200
  search requests, so with that token it waits for the hourly reset (up to an
  hour each) and the job's 180-minute timeout leaves room for two. Create a
  `METRICS_TOKEN` secret (5000 requests per hour) to finish in about 19
  minutes. Use a fine-grained personal access token with "Public
  repositories (read-only)" access and no permissions, or a classic token with
  no scopes. Do not use the `public_repo` scope, it grants write access to
  every public repository.
- **Clone**: the drift chart clones opentelemetry.io anonymously over HTTPS
  (no token) into `data/.cache/`, which takes about 11 s and 37 MB. The runner
  image's git (2.55 on `ubuntu-24.04`) meets the 2.44 minimum. The clone is not
  uploaded: the artifact holds `data/*.csv` only.

## Output

The `plot.py` script generates a presentation-ready graph:

- Grafana-style dark theme (`#282828` background)
- Step-style lines with semi-transparent area fills
- Large fonts optimized for presentations (1k+ viewers)
- Accumulated contributions over time per language
- Translation coverage as percentages: a plain line per language across the
  release months, or one bar per language ranked from most to least covered
- PR flow: a marked line per language across the months, breaking where a
  language has no value (no PR merged that month)
- Contributors: a marked line per language for the unique contributors of each
  month, and bars stacked by language, with the total on top, for the new ones
- Translation drift: a 100% horizontal bar per language split by page status,
  each segment wide enough labeled with its share
- End-of-line values on line charts: labels that would overlap are nudged apart
  vertically (the lines and points do not move), labels that do not overlap
  stay put
- Legend outside the plot area
- Opens in a matplotlib window (zoom and pan with its toolbar), or saves a PNG
  with `OUTPUT=` / `--output`

## Troubleshooting

Errors exit with status 1 and an `Error:` message, so `make` never goes on to
plot empty or zero data:

- **Fetch step**: failed GitHub requests, exhausted rate limits and retries,
  incomplete search results, a truncated git tree, and for the drift pipeline a
  failed clone or git command, git older than 2.44 or a `CLONE_DIR` it did not
  create. The script stops before writing, so data from an earlier run stays
  untouched.
- **CSV and plot steps**: a missing, unreadable or empty JSON/CSV file, no
  records for the requested `YEAR` or `TYPE` (this is also how a fetch that
  found nothing, such as no releases for the year, is caught), and an invalid
  `YEAR` or `TYPE`.

### "Error: GITHUB_TOKEN is not set"

Make sure:

1. `GITHUB_TOKEN` is exported in your shell, or a `.env` file in the project
   root contains `GITHUB_TOKEN=your_token_here`
2. Token can read public repositories (a fine-grained token with "Public
   repositories (read-only)" access, or a classic token with no scopes)

### "git 2.44 or newer is required"

The drift pipeline needs git 2.44+. Check with `git --version` and upgrade git,
or skip the drift chart by running the other pipelines on their own.

### "... exists but is not a git clone" or "... is a git clone this script did not create"

`fetch-drift` keeps its clone in `CLONE_DIR` (default
`data/.cache/opentelemetry.io`) and refuses any other folder there, so it never
resets your own work. Point `CLONE_DIR` at an empty or missing folder, or
remove the folder yourself.

### "ModuleNotFoundError: No module named 'pandas'"

Install Python dependencies:

```bash
pip install -r requirements.txt
```

If using a virtual environment, make sure it's activated:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Python script can't find files

Make sure to run scripts from project root. `config.yaml` is located relative to
the script, but the `data/` JSON and CSV paths are relative to the current
directory (the fetch scripts would also write `data/` there):

```bash
# Correct
python3 scripts/processing/plot.py

# Wrong (if in scripts/ or scripts/processing/ directory)
python3 plot.py  # Error: data/lang_accumulated.csv not found. Run 'make fetch-lang-contributions' first.
```

### GitHub API Rate Limit

The fetch scripts wait and retry when GitHub rate limits a request (up to 5
attempts, honoring `retry-after` and the limit reset time) and print
`⚠️ ... Retrying in Ns`. If the request still fails, the script exits with
status 1. You can:

1. Wait for the reset time and run it again
2. Use a different GitHub token
3. Reduce the number of languages fetched with `LANGS=pt,es`

## Available Languages

- `bn` - Bengali
- `es` - Spanish
- `fr` - French
- `ja` - Japanese
- `ko` - Korean
- `pl` - Polish
- `pt` - Portuguese
- `ro` - Romanian
- `uk` - Ukrainian
- `zh` - Chinese

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details
