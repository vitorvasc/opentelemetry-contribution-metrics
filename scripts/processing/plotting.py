import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.ticker import MaxNLocator, NullLocator, PercentFormatter

# Grafana-style dark theme configuration
BACKGROUND_COLOR = "#282828"
GRID_COLOR = "#3a3a3a"
TEXT_COLOR = "#cccccc"
# Text drawn on a colored bar segment, whichever contrasts more with it
DARK_TEXT_COLOR = "#0b0b0b"
LIGHT_TEXT_COLOR = "#ffffff"

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

    A missing value in `y` leaves a gap in the line.

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

    # A gap at the end leaves the label on the last point that has a value
    last = y.last_valid_index()
    if annotate and last is not None:
        ax.annotate(
            value_format.format(y.loc[last]),
            xy=(x.loc[last], y.loc[last]),
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


def draw_stacked_bars(
    ax, df, date_column, value_column, colors, annotate=False, value_format="{:.0f}"
):
    """One bar per date, with a segment per language stacked in the language's color.

    The language with the most overall is at the bottom. A language without a
    positive value is left out, and a date without one for a language has no
    segment of it. With `annotate`, each bar is labeled with its total. The y axis
    ticks whole counts and the grid stays behind the bars.
    """
    ax.set_axisbelow(True)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    values = df.pivot_table(
        index=date_column, columns="lang", values=value_column, aggfunc="sum", fill_value=0
    )
    langs = values.sum().sort_values(ascending=False, kind="stable").index
    bottom = pd.Series(0, index=values.index)

    for lang in langs:
        present = values[lang] > 0
        if not present.any():
            continue

        color = colors.get(lang)
        ax.bar(
            values.index[present],
            values.loc[present, lang],
            bottom=bottom[present],
            width=20,
            label=lang.upper(),
            color=color,
            alpha=0.8,
            edgecolor=color,
            linewidth=1,
        )
        bottom = bottom + values[lang]

    if annotate:
        for x, total in bottom[bottom > 0].items():
            ax.annotate(
                value_format.format(total),
                xy=(x, total),
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


def relative_luminance(color):
    """WCAG relative luminance of a matplotlib color."""
    channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(color)]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrasting_text(color):
    """The dark or light text color, whichever has the higher contrast ratio on `color`."""
    fill = relative_luminance(color)
    dark = (fill + 0.05) / (relative_luminance(DARK_TEXT_COLOR) + 0.05)
    light = (relative_luminance(LIGHT_TEXT_COLOR) + 0.05) / (fill + 0.05)
    return DARK_TEXT_COLOR if dark >= light else LIGHT_TEXT_COLOR


# Narrower segments are left unlabeled, their share would not fit
MIN_LABELED_SHARE = 3


def draw_share_bars(ax, df, columns, colors, annotate=False, value_format="{:.0f}%"):
    """One horizontal bar per language spanning 100%, split into the share of each of `columns`.

    Bars follow the row order of `df` from the top, and each tick names the
    language and its total. A language whose columns sum to zero has no bar. A
    column that is zero for every language is left out, so the legend lists only
    the segments drawn, in the order of `columns`. Segments are drawn in the
    column's color and separated by a gap of background. With `annotate`, each
    segment of at least MIN_LABELED_SHARE percent is labeled with its share.
    """
    totals = df[columns].sum(axis=1)
    rows = df[totals > 0].reset_index(drop=True)
    totals = totals[totals > 0].reset_index(drop=True)
    shares = rows[columns].div(totals, axis=0) * 100
    positions = pd.Series(range(len(rows) - 1, -1, -1), dtype=float)
    left = pd.Series(0.0, index=rows.index)

    ax.set_axisbelow(True)
    for column in columns:
        present = shares[column] > 0
        if not present.any():
            continue

        color = colors.get(column)
        bars = ax.barh(
            positions[present],
            shares.loc[present, column],
            left=left[present],
            height=0.7,
            label=column.replace("_", " ").capitalize(),
            color=color,
            edgecolor=BACKGROUND_COLOR,
            linewidth=1.5,
        )

        if annotate:
            text_color = contrasting_text(bars.patches[0].get_facecolor())
            for y, start, share in zip(
                positions[present], left[present], shares.loc[present, column], strict=True
            ):
                if share >= MIN_LABELED_SHARE:
                    ax.text(
                        start + share / 2,
                        y,
                        value_format.format(share),
                        fontsize=TICK_FONTSIZE - 2,
                        fontweight="bold",
                        color=text_color,
                        ha="center",
                        va="center",
                    )
        left = left + shares[column]

    ax.set_yticks(
        positions,
        labels=[
            f"{lang.upper()} ({total})" for lang, total in zip(rows["lang"], totals, strict=True)
        ],
    )
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))


def draw_by_language(
    ax, df, date_column, value_column, colors, annotate=False, value_format="{:.0f}", area=True
):
    """One series per language, from the `lang` column of `df`.

    A language without a single value is left out.
    """
    # Sort languages by max value (descending) so larger areas are drawn first
    langs_sorted = df.groupby("lang")[value_column].max().sort_values(ascending=False).index

    # Latest date across all languages
    max_date = df[date_column].max()

    for lang in langs_sorted:
        subset = df[df["lang"] == lang].sort_values(date_column)
        x = subset[date_column]
        y = subset[value_column]
        if y.isna().all():
            continue

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


def set_symlog_axis(ax, ticks):
    """Symmetric log y axis from zero, labeled at `ticks`.

    It is linear up to the first positive tick and logarithmic above it, so small
    values stay readable next to large ones. The axis ends on the first tick that
    covers the data.
    """
    top = ax.get_ylim()[1]
    top = next((tick for tick in ticks if tick >= top), top)

    ax.set_yscale("symlog", linthresh=min(tick for tick in ticks if tick > 0))
    ax.set_ylim(0, top)
    shown = [tick for tick in ticks if tick <= top]
    ax.set_yticks(shown, labels=[f"{tick:g}" for tick in shown])
    ax.yaxis.set_minor_locator(NullLocator())


def spread_labels(ax, labels, min_gap=1.2 * LEGEND_FONTSIZE):
    """Nudge the value labels at the same x apart vertically so none overlaps another.

    Each label stays as close as it can to the point it labels, in the same order
    and inside the axes. `min_gap` is the least distance between the centers of two
    labels, in points. Only the text moves, never the point. Call it once the layout
    is final, since the distance is measured on the screen.
    """
    scale = ax.figure.dpi / 72
    gap = min_gap * scale
    columns = {}
    for label in labels:
        columns.setdefault(label.xy[0], []).append(label)

    for column in columns.values():
        column.sort(key=lambda label: label.xy[1])
        anchors = [ax.transData.transform((0, label.xy[1]))[1] for label in column]

        # Least-squares positions that keep each label `gap` above the one below:
        # pool neighbors that collide into a block that shares one position
        blocks = []
        for i, anchor in enumerate(anchors):
            blocks.append([anchor - i * gap, 1])
            while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
                total, count = blocks.pop()
                blocks[-1][0] += total
                blocks[-1][1] += count
        bottoms = [total / count for total, count in blocks for _ in range(count)]

        low, high = ax.bbox.y0, ax.bbox.y1 - (len(column) - 1) * gap
        for i, (label, anchor, bottom) in enumerate(zip(column, anchors, bottoms, strict=True)):
            shift = min(max(bottom, low), high) + i * gap - anchor
            if abs(shift) > 0.01:
                dx, dy = label.xyann
                label.xyann = (dx, dy + shift / scale)


def style_legend(ax, title=None, reverse=False):
    """Legend outside the plot area to avoid overlap.

    With `reverse` the entries are listed last drawn first, which is top to
    bottom for a stack drawn from the bottom up.
    """
    handles, labels = ax.get_legend_handles_labels()
    if reverse:
        handles, labels = handles[::-1], labels[::-1]
    legend = ax.legend(
        handles,
        labels,
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
