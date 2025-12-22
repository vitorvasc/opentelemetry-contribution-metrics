# OpenTelemetry Contribution Metrics

Visualization tool for tracking accumulated contributions — OpenTelemetry.io.

## Features

- Fetches contribution data from GitHub API
- Filters PRs by language labels (bn, es, fr, ja, pt, ro, uk, zh)
- **Two tracking modes**:
  - **PR-based**: Track individual PRs over time
  - **Release-based**: Measure lines/pages translated per monthly release
- Calculates translation coverage percentages
- Generates accumulated contribution metrics over time
- Creates Grafana-style dark theme visualizations
- Configurable colors and display options

## Prerequisites

- **Node.js 18+**
- **Python 3.8+**
- **GitHub Personal Access Token** with `public_repo` scope

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

### 5. Verify setup

```bash
make setup-check
```

This validates that all dependencies are installed and the environment is
configured correctly.

## Usage

### Using Make (Recommended)

The tool provides two automated pipelines - each command fetches data, converts to CSV, and generates visualizations automatically:

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

#### Other Commands

```bash
make setup-check  # Verify environment configuration
make help         # Show all available commands
```

### Parameters

All commands support the following parameters:

| Parameter     | Description                                  | Default | Example          |
| ------------- | -------------------------------------------- | ------- | ---------------- |
| `YEAR=XXXX`   | Filter by year                               | 2025    | `YEAR=2024`      |
| `LANGS=xx,yy` | Filter by languages (comma-separated)        | all     | `LANGS=pt,es,fr` |
| `TYPE=xxx`    | Filter contribution type (prs/issues/both)\* | both    | `TYPE=prs`       |

\* `TYPE` parameter only applies to `fetch-lang-contributions`

### Using npm Scripts

```bash
npm run fetch-lang-contributions  # Language contributions pipeline
npm run fetch-release-metrics     # Release metrics pipeline
npm run clean-lang-contributions  # Clean language data
npm run clean-release-metrics     # Clean release data
npm run setup-check               # Verify setup
```

### Direct Script Execution

```bash
# Language contributions
node scripts/fetch/fetch_lang_issues.js
python3 scripts/processing/lang_contributions_to_csv.py
python3 scripts/processing/plot.py

# Release metrics
node scripts/fetch/fetch_release_metrics.js
python3 scripts/processing/release_metrics_to_csv.py
python3 scripts/processing/plot.py --source=releases
```

## Understanding the Two Pipelines

The tool provides two complementary ways to track OpenTelemetry localization contributions:

### Language Contributions Pipeline

Tracks **individual PR and issue contributions** over time:

- **What it tracks**: Every PR/issue with a `lang:*` label
- **Granularity**: Day-by-day accumulation
- **Use case**: See contribution activity and engagement over time
- **Filters**: Can filter by type (PRs only, issues only, or both)

### Release Metrics Pipeline

Tracks **translation progress by monthly release**:

- **What it tracks**: Lines translated, pages added, coverage % per monthly release (YYYY.MM tags)
- **Granularity**: Month-by-month snapshots aligned with OpenTelemetry releases
- **Use case**: Measure actual translation coverage and progress against English baseline
- **Data source**: https://github.com/open-telemetry/opentelemetry.io/releases

### Metrics Calculated

For each release month and language:

1. **Lines Added**: Total lines of translated content added in `.md` files
2. **Pages Added**: Count of new markdown files in `content/{lang}/`
3. **Coverage %**: Percentage of English content that's been translated
4. **Coverage Change**: Month-over-month improvement in coverage

### Output Files

- `data/release_metrics.json` - Detailed metrics per release/language
- `data/release_metrics_accumulated.csv` - Accumulated totals for visualization

### Example Output

```csv
lang,month,lines_added,pages_added,total_lines,total_pages,coverage_pct,coverage_change,pr_count
pt,2025-01,423,3,423,3,12.5,0.0,8
pt,2025-02,567,5,990,8,18.2,5.7,12
es,2025-01,892,7,892,7,25.3,0.0,15
es,2025-02,654,4,1546,11,28.9,3.6,11
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
  pt: '#A855F7' # Portuguese - purple
  ro: '#EC4899' # Romanian - pink
  uk: '#14B8A6' # Ukrainian - teal
  zh: '#EF4444' # Chinese - red
```

### Environment Variables

`.env` file (required):

```bash
GITHUB_TOKEN=your_token_here
```

Command-line parameters (optional):

```bash
# Filter by languages
make fetch-lang-contributions LANGS=pt,es

# Filter by contribution type
TYPE=prs make fetch-lang-contributions

# Filter by year
YEAR=2024 make fetch-release-metrics
```

## Project Structure

```
opentelemetry-contribution-metrics/
├── scripts/
│   ├── fetch/                         # Data fetching scripts (Node.js)
│   │   ├── fetch_lang_issues.js       # Fetches PR-based data from GitHub API
│   │   └── fetch_release_metrics.js   # Fetches release-based metrics
│   ├── processing/                    # Data processing scripts (Python)
│   │   ├── lang_contributions_to_csv.py   # Converts PR JSON to accumulated CSV
│   │   ├── release_metrics_to_csv.py      # Converts release JSON to accumulated CSV
│   │   └── plot.py                        # Generates visualization (supports both modes)
│   └── check_setup.sh                 # Validates environment setup
├── data/
│   ├── lang_contributions.json        # Raw PR data (generated)
│   ├── lang_accumulated.csv           # Accumulated PR data (generated)
│   ├── release_metrics.json           # Raw release data (generated)
│   └── release_metrics_accumulated.csv # Accumulated release data (generated)
├── config.yaml                        # Plot configuration
├── .env.example                       # Environment template
├── .env                               # Your environment variables (gitignored)
├── .gitignore                         # Git ignore rules
├── Makefile                           # Build automation
├── package.json                       # Node.js dependencies
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

## Output

The `plot.py` script generates a presentation-ready graph:

- Grafana-style dark theme (`#282828` background)
- Step-style lines with semi-transparent area fills
- Large fonts optimized for presentations (1k+ viewers)
- Accumulated contributions over time per language
- Interactive date range and legend

## Troubleshooting

### "Error: GITHUB_TOKEN is not set"

Make sure:

1. `.env` file exists in project root
2. Contains `GITHUB_TOKEN=your_token_here`
3. Token has correct permissions (public_repo scope)

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

Make sure to run scripts from project root:

```bash
# Correct
python3 scripts/processing/plot.py

# Wrong (if in scripts/ or scripts/processing/ directory)
python3 plot.py  # Will fail to find config.yaml
```

### "Error: .env file not found"

Copy the example file and configure it:

```bash
cp .env.example .env
# Edit .env and add your GITHUB_TOKEN
```

### GitHub API Rate Limit

If you see rate limit warnings, the script will display when the limit resets.
You can:

1. Wait for the reset time
2. Use a different GitHub token
3. Reduce the number of languages fetched with `LANGS=pt,es`

## Available Languages

- `bn` - Bengali
- `es` - Spanish
- `fr` - French
- `ja` - Japanese
- `pt` - Portuguese
- `ro` - Romanian
- `uk` - Ukrainian
- `zh` - Chinese

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details
