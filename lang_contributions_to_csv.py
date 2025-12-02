import pandas as pd

df = pd.read_json("lang_contributions.json")

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

df_accum.to_csv("lang_accumulated.csv", index=False)
print(df_accum)