import pandas as pd
import sys
import os
from pathlib import Path

# Check if input file exists
input_file = Path("data/merged_prs.json")
if not input_file.exists():
    print(f"Error: {input_file} not found. Run 'make fetch-merged-prs' first.")
    sys.exit(1)

# Read JSON with error handling
try:
    df = pd.read_json(input_file)
except Exception as e:
    print(f"Error reading JSON: {e}")
    sys.exit(1)

if df.empty:
    print("Warning: No data found in merged_prs.json")
    sys.exit(0)

# Extract month from merged_at
df["month"] = pd.to_datetime(df["merged_at"]).dt.to_period("M").astype(str)

# Group by month and count PRs
monthly_counts = df.groupby("month").size().reset_index(name="count")

# Get YEAR from environment variable for filling missing months
year = os.environ.get("YEAR", str(pd.Timestamp.now().year))

# Generate all months for the year
all_months = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]

# Create a dataframe with all months
all_months_df = pd.DataFrame({"month": all_months})

# Merge to include months with zero PRs
monthly_counts = all_months_df.merge(monthly_counts, on="month", how="left")
monthly_counts["count"] = monthly_counts["count"].fillna(0).astype(int)

# Calculate cumulative total
monthly_counts["total"] = monthly_counts["count"].cumsum()

# Write output
output_file = Path("data/merged_prs_accumulated.csv")
monthly_counts.to_csv(output_file, index=False)

print(f"✓ Successfully converted {len(df)} merged PRs to accumulated CSV")
print(f"  Output: {output_file}")
print(f"  Year: {year}")
print(f"  Total merged PRs: {monthly_counts['total'].iloc[-1]}")
