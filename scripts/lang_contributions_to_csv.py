import pandas as pd
import sys
from pathlib import Path

# Check if input file exists
input_file = Path("data/lang_contributions.json")
if not input_file.exists():
    print(f"Error: {input_file} not found. Run 'make fetch' first.")
    sys.exit(1)

# Read JSON with error handling
try:
    df = pd.read_json(input_file)
except Exception as e:
    print(f"Error reading JSON: {e}")
    sys.exit(1)

# Filter PRs only (exclude issues)
df = df[df["url"].str.contains("/pull/")]

# usar created_at como data
df["date"] = pd.to_datetime(df["created_at"])

# ordenar
df = df.sort_values("date")

# contador = cada linha vale 1 para aquele idioma
df["count"] = 1

# acumular por idioma
df_accum = df.groupby(["lang", "date"])["count"].sum().groupby(level=0).cumsum()

df_accum = df_accum.reset_index()

# Write output
output_file = Path("data/lang_accumulated.csv")
df_accum.to_csv(output_file, index=False)

print(f"✓ Successfully converted {len(df)} PRs to accumulated CSV")
print(f"  Output: {output_file}")
print(f"  Languages: {', '.join(sorted(df['lang'].unique()))}")