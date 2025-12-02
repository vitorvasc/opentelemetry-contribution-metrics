# OpenTelemetry Contribution Metrics

Visualization tool for tracking accumulated contributions to OpenTelemetry projects by language (Portuguese and Spanish translations).

## Prerequisites

- **Python 3.8+**
- **Node.js** (for fetching GitHub data)
- **GitHub Token** with read access to the repository

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Node.js dependencies

```bash
npm install
```

### 3. Set up GitHub Token

Export your GitHub token before running the fetch command:

```bash
export GITHUB_TOKEN=your_token_here
```

## Usage

The project uses a Makefile for easy execution:

### Run the full pipeline

```bash
make all
```

This executes: `fetch` → `csv` → `plot`

### Individual commands

| Command | Description |
|---------|-------------|
| `make fetch` | Fetch issues/PRs with `lang:*` labels from GitHub |
| `make csv` | Convert JSON data to accumulated CSV |
| `make plot` | Generate the Grafana-style contribution graph |
| `make clean` | Remove generated JSON and CSV files |
| `make help` | Show available commands |

## Output

The `plot.py` script generates a Grafana-style graph showing accumulated contributions over time:

- Dark theme with `#282828` background
- Step-style lines with semi-transparent area fills
- Presentation-ready with large fonts (optimized for 1k+ viewers)
- Languages displayed: PT (Portuguese) and ES (Spanish)

## Project Structure

```
opentelemetry-contrib-metrics/
├── fetch_lang_issues.js      # Fetches data from GitHub API
├── lang_contributions_to_csv.py  # Converts JSON to accumulated CSV
├── plot.py                   # Generates the visualization
├── Makefile                  # Build automation
├── requirements.txt          # Python dependencies
├── package.json              # Node.js dependencies
└── README.md                 # This file
```

## Generated Files

- `lang_contributions.json` - Raw contribution data from GitHub
- `lang_accumulated.csv` - Processed accumulated data for plotting

