import pandas as pd
import sys
from pathlib import Path

# Check if input file exists
input_file = Path("data/release_metrics.json")
if not input_file.exists():
    print(f"Error: {input_file} not found. Run 'make fetch-releases' first.")
    sys.exit(1)

# Read JSON with error handling
try:
    df = pd.read_json(input_file)
except Exception as e:
    print(f"Error reading JSON: {e}")
    sys.exit(1)

if df.empty:
    print("Warning: No data found in release_metrics.json")
    sys.exit(0)

# Sort by language and month
df = df.sort_values(["lang", "month"])

# Calculate accumulated totals per language
df["total_lines"] = df.groupby("lang")["lines_added"].cumsum()
df["total_pages"] = df.groupby("lang")["pages_added"].cumsum()

# Calculate month-over-month coverage change
df["coverage_change"] = df.groupby("lang")["coverage_pct"].diff()

# Fill NaN coverage_change for first month of each language with 0
df["coverage_change"] = df["coverage_change"].fillna(0)

# Round coverage_change to 1 decimal place
df["coverage_change"] = df["coverage_change"].round(1)

# Write output
output_file = Path("data/release_metrics_accumulated.csv")
df.to_csv(output_file, index=False)

print(f"✓ Successfully converted {len(df)} records to accumulated CSV")
print(f"  Output: {output_file}")
print(f"  Languages: {', '.join(sorted(df['lang'].unique()))}")
print(f"  Months: {df['month'].min()} to {df['month'].max()}")
