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

Run the complete pipeline:

```bash
make all
```

Individual commands:

| Command            | Description                                |
| ------------------ | ------------------------------------------ |
| `make fetch`       | Fetch PRs with `lang:*` labels from GitHub |
| `make csv`         | Convert JSON data to accumulated CSV       |
| `make plot`        | Generate the contribution graph            |
| `make clean`       | Remove generated data files                |
| `make setup-check` | Verify environment configuration           |
| `make help`        | Show available commands                    |

Fetch specific languages:

```bash
make fetch LANGS=pt,es
```

### Using npm Scripts

```bash
npm run all          # Run complete pipeline
npm run fetch        # Fetch data only
npm run csv          # Convert to CSV only
npm run plot         # Generate plot only
npm run clean        # Clean generated files
npm run setup-check  # Verify setup
```

### Direct Script Execution

```bash
node scripts/fetch_lang_issues.js
python3 scripts/lang_contributions_to_csv.py
python3 scripts/plot.py
```

## Release-Based Metrics

In addition to PR-based tracking, you can measure localization progress by
monthly releases (using the `YYYY.MM` release tags from
https://github.com/open-telemetry/opentelemetry.io/releases).

### What's Different?

- **PR-based metrics** (above): Tracks individual PRs over time
- **Release-based metrics**: Groups PRs by monthly release, calculates lines
  added, pages translated, and coverage % per month

### Usage

**Using Make:**

```bash
make releases                    # Run complete release pipeline
make fetch-releases              # Fetch release metrics
make fetch-releases SINCE=2024.01  # Only process releases since Jan 2024
make fetch-releases LANGS=pt,es # Only specific languages
make csv-releases                # Convert to CSV
make plot-releases               # Generate visualization
make clean-releases              # Remove generated files
```

**Using npm:**

```bash
npm run releases        # Run complete release pipeline
npm run fetch-releases  # Fetch release metrics
npm run csv-releases    # Convert to CSV
npm run plot-releases   # Generate visualization
npm run clean-releases  # Remove generated files
```

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

Command-line (optional):

```bash
LANGS=pt,es make fetch  # Fetch specific languages only
```

## Project Structure

```
opentelemetry-contribution-metrics/
├── scripts/
│   ├── fetch_lang_issues.js           # Fetches PR-based data from GitHub API
│   ├── fetch_release_metrics.js       # Fetches release-based metrics
│   ├── lang_contributions_to_csv.py   # Converts PR JSON to accumulated CSV
│   ├── release_metrics_to_csv.py      # Converts release JSON to accumulated CSV
│   ├── plot.py                        # Generates visualization (supports both modes)
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
python3 scripts/plot.py

# Wrong (if in scripts/ directory)
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
