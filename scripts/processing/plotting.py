import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

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


def create_figure():
    """Figure and axes with the dark background."""
    # Higher DPI for sharper rendering
    fig, ax = plt.subplots(figsize=(14, 6), dpi=120)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    return fig, ax


def draw_series(ax, x, y, label, color=None, annotate=False, value_format="{:.0f}", area=True):
    """Line with an optional endpoint value.

    With `area` (the default) it is a step line over a semi-transparent fill,
    for running totals. Without it, a plain line with a marker at each date,
    for values measured at each date.
    """
    style = {"drawstyle": "steps-post"} if area else {"marker": "o", "markersize": 7}
    (line,) = ax.plot(x, y, label=label, linewidth=LINE_WIDTH, color=color, **style)
    # Reuse the line's color so the fill matches even when no color was configured
    color = line.get_color()

    if area:
        ax.fill_between(x, y, step="post", alpha=0.3, color=color)

    if annotate:
        ax.annotate(
            value_format.format(y.iloc[-1]),
            xy=(x.iloc[-1], y.iloc[-1]),
            xytext=(10, 0),
            textcoords="offset points",
            fontsize=LEGEND_FONTSIZE,
            fontweight="bold",
            color=color,
            va="center",
        )


def draw_bars(ax, x, y, color, annotate=False):
    """Bar chart over dates with an optional value label on top of each bar."""
    ax.bar(x, y, width=20, color=color, alpha=0.8, edgecolor=color, linewidth=1)

    if annotate:
        for bar_x, bar_y in zip(x, y, strict=True):
            ax.annotate(
                f"{int(bar_y)}",
                xy=(bar_x, bar_y),
                xytext=(0, 5),
                textcoords="offset points",
                fontsize=TICK_FONTSIZE,
                fontweight="bold",
                color=TEXT_COLOR,
                ha="center",
                va="bottom",
            )


def draw_ranked_bars(ax, df, value_column, colors, annotate=False, value_format="{:.0f}"):
    """One bar per language, in the row order of `df`, in the language's color."""
    langs = df["lang"]
    values = df[value_column]
    bar_colors = [colors.get(lang, TEXT_COLOR) for lang in langs]

    ax.bar(
        [lang.upper() for lang in langs],
        values,
        width=0.7,
        color=bar_colors,
        alpha=0.8,
        edgecolor=bar_colors,
        linewidth=1,
    )

    if annotate:
        for index, value in enumerate(values):
            ax.annotate(
                value_format.format(value),
                xy=(index, value),
                xytext=(0, 5),
                textcoords="offset points",
                fontsize=TICK_FONTSIZE,
                fontweight="bold",
                color=TEXT_COLOR,
                ha="center",
                va="bottom",
            )


def draw_by_language(
    ax, df, date_column, value_column, colors, annotate=False, value_format="{:.0f}", area=True
):
    """One series per language, from the `lang` column of `df`."""
    # Sort languages by max value (descending) so larger areas are drawn first
    langs_sorted = df.groupby("lang")[value_column].max().sort_values(ascending=False).index

    # Latest date across all languages
    max_date = df[date_column].max()

    for lang in langs_sorted:
        subset = df[df["lang"] == lang].sort_values(date_column)
        x = subset[date_column]
        y = subset[value_column]

        # Extend to max_date if this language ends earlier
        if x.iloc[-1] < max_date:
            x = pd.concat([x, pd.Series([max_date])], ignore_index=True)
            y = pd.concat([y, y.iloc[-1:]], ignore_index=True)

        draw_series(ax, x, y, lang.upper(), colors.get(lang), annotate, value_format, area)


def style_axes(ax, title, xlabel, ylabel, dates=True):
    """Grid, spines, labels and title for the dark background, and date ticks unless `dates` is off."""
    # Grid styling (Grafana-like)
    ax.grid(color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.6)

    ax.tick_params(colors=TEXT_COLOR, labelsize=TICK_FONTSIZE)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)

    if dates:
        # Cleaner date formatting with MonthLocator
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    ax.set_xlabel(xlabel, fontsize=LABEL_FONTSIZE, color=TEXT_COLOR)
    ax.set_ylabel(ylabel, fontsize=LABEL_FONTSIZE, color=TEXT_COLOR)
    ax.set_title(title, fontsize=TITLE_FONTSIZE, fontweight="bold", pad=20, color=TEXT_COLOR)


def style_legend(ax, title=None):
    """Legend outside the plot area to avoid overlap."""
    legend = ax.legend(
        title=title,
        fontsize=LEGEND_FONTSIZE,
        title_fontsize=LEGEND_FONTSIZE,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        facecolor=BACKGROUND_COLOR,
        edgecolor=GRID_COLOR,
    )
    legend.get_title().set_color(TEXT_COLOR)
    legend.get_frame().set_alpha(0.8)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)
