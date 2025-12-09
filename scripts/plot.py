import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.dates as mdates
import yaml
from pathlib import Path

# Load configuration
config_path = Path(__file__).parent / "config.yaml"
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

# Load data
df = pd.read_csv("lang_accumulated.csv", parse_dates=["date"])

# Grafana-style dark theme configuration
BACKGROUND_COLOR = "#282828"
GRID_COLOR = "#3a3a3a"
TEXT_COLOR = "#cccccc"

# Presentation-ready settings
TITLE_FONTSIZE = 22
LABEL_FONTSIZE = 16
TICK_FONTSIZE = 14
LEGEND_FONTSIZE = 14
LINE_WIDTH = 3.5

# Config options
SHOW_ENDPOINT_VALUES = config.get("show_endpoint_values", False)
COLORS = config.get("colors", {})

# Higher DPI for sharper rendering
fig, ax = plt.subplots(figsize=(14, 6), dpi=120)

# Set background colors
fig.patch.set_facecolor(BACKGROUND_COLOR)
ax.set_facecolor(BACKGROUND_COLOR)

# Sort languages by max count (descending) so larger areas are drawn first
langs_sorted = df.groupby("lang")["count"].max().sort_values(ascending=False).index

# Plot each language line with step-style and area fill
max_date = df["date"].max()  # Get the latest date across all languages

for lang in langs_sorted:
    subset = df[df["lang"] == lang].sort_values("date")
    color = COLORS.get(lang, None)
    
    # Extend to max_date if this language ends earlier
    if subset["date"].iloc[-1] < max_date:
        extension = pd.DataFrame({
            "date": [max_date],
            "count": [subset["count"].iloc[-1]],
            "lang": [lang]
        })
        subset = pd.concat([subset, extension], ignore_index=True)
    
    # Step-style line plot
    ax.plot(
        subset["date"],
        subset["count"],
        label=lang.upper(),
        linewidth=LINE_WIDTH,
        color=color,
        drawstyle='steps-post'
    )
    
    # Semi-transparent area fill
    ax.fill_between(
        subset["date"],
        subset["count"],
        step='post',
        alpha=0.3,
        color=color
    )
    
    # Endpoint annotation (configurable)
    if SHOW_ENDPOINT_VALUES:
        final_date = subset["date"].iloc[-1]
        final_count = subset["count"].iloc[-1]
        ax.annotate(
            f'{int(final_count)}',
            xy=(final_date, final_count),
            xytext=(10, 0),
            textcoords='offset points',
            fontsize=LEGEND_FONTSIZE,
            fontweight='bold',
            color=color,
            va='center'
        )

# Grid styling (Grafana-like)
ax.grid(color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.6)

# Axis styling for dark background with larger fonts
ax.tick_params(colors=TEXT_COLOR, labelsize=TICK_FONTSIZE)
ax.xaxis.label.set_color(TEXT_COLOR)
ax.yaxis.label.set_color(TEXT_COLOR)
ax.title.set_color(TEXT_COLOR)

# Spine colors
for spine in ax.spines.values():
    spine.set_color(GRID_COLOR)

# Cleaner date formatting with MonthLocator
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.xticks(rotation=30, ha="right")

# Labels and title (English, larger fonts)
ax.set_xlabel("Date", fontsize=LABEL_FONTSIZE)
ax.set_ylabel("Accumulated Contributions", fontsize=LABEL_FONTSIZE)
ax.set_title("Accumulated Contributions by Language", fontsize=TITLE_FONTSIZE, fontweight='bold', pad=20)

# Legend (outside plot area to avoid overlap)
legend = ax.legend(
    title="Language",
    fontsize=LEGEND_FONTSIZE,
    title_fontsize=LEGEND_FONTSIZE,
    loc='center left',
    bbox_to_anchor=(1.01, 0.5),
    facecolor=BACKGROUND_COLOR,
    edgecolor=GRID_COLOR
)
legend.get_frame().set_alpha(0.8)
legend.get_title().set_color(TEXT_COLOR)
for text in legend.get_texts():
    text.set_color(TEXT_COLOR)

# Tight layout with extra padding for cleaner look
plt.tight_layout(pad=1.5)

# Show the plot
plt.show()
