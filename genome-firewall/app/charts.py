"""Charts for Genome Firewall — slate, no chart junk (see CLAUDE.md).

Same tokens as app/theme.py. Marks are slate; no color encodes a result here.
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK    = "#0F172A"   # slate-900
LINE   = "#E2E8F0"   # slate-200
MUTED  = "#64748B"   # slate-500
SURF   = "#FFFFFF"

plt.rcParams.update({
    "font.size": 8.5, "axes.edgecolor": "#CBD5E1", "axes.labelcolor": "#475569",
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "figure.facecolor": SURF, "axes.facecolor": SURF,
    "axes.labelsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
})


# The two charts are read side by side, so they share a canvas size and a frame
# treatment. Both are rendered at 2x by Streamlit and displayed at 460px.
FIGSIZE = (4.3, 3.2)
EDGE = "#CBD5E1"   # slate-300


def _frame(ax, sides=("left", "bottom")):
    """Keep the named spines; a chart whose data reaches the plot edge keeps all
    four, so a line running into the corner reads as bounded rather than cut."""
    for name, spine in ax.spines.items():
        spine.set_visible(name in sides)
        spine.set_color(EDGE)
        spine.set_linewidth(0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.8, color=EDGE)
    return ax


def reliability_curve(points=None):
    """Predicted probability vs observed frequency. Diagonal = perfect."""
    points = points or []
    conf = [p.get("confidence", p.get("mean_predicted")) for p in points]
    obs = [p.get("accuracy", p.get("observed_resistant_fraction")) for p in points]
    fig, ax = plt.subplots(figsize=FIGSIZE)
    # All four spines: the diagonal runs corner to corner, so an open top-right
    # made it look clipped. Equal aspect keeps that reference line at a true 45°,
    # which is the whole point of reading a calibration plot.
    _frame(ax, sides=("left", "bottom", "top", "right"))
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color=LINE, linewidth=0.7)
    # clip_on=False so the corner-to-corner line is not shaved by the axes edge.
    ax.plot([0.5, 1], [0.5, 1], "--", color=MUTED, lw=1.3, zorder=2,
            clip_on=False, label="Perfect calibration")
    if conf:
        ax.plot(conf, obs, "-o", color=INK, lw=1.8, markersize=5.5, zorder=3,
                label="Model")
    ax.set_xlim(0.5, 1); ax.set_ylim(0.5, 1)
    ax.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("Predicted confidence"); ax.set_ylabel("Observed accuracy")
    # Lower right: the area under the diagonal is empty, and the old upper-left
    # legend sat on top of the reference line.
    ax.legend(loc="lower right", frameon=False, fontsize=7.5,
              handlelength=1.6, borderpad=0.2, labelspacing=0.35)
    fig.tight_layout(pad=0.6)
    return fig


def auroc_bars(metrics):
    """Per-drug AUROC (threshold-free discrimination), sorted, with a 0.5 = random line."""
    ms = sorted(metrics, key=lambda m: m.auroc)
    drugs = [m.drug for m in ms]; vals = [m.auroc for m in ms]
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _frame(ax)
    ax.grid(axis="x", color=LINE, linewidth=0.7)
    ax.barh(drugs, vals, color=INK, height=0.62, zorder=3)
    # No "random" reference line: the axis starts at 0.5, so every bar already
    # grows from random and a dashed line there would sit under the left spine.
    # Headroom so the value label on the longest bar stays inside the frame.
    ax.set_xlim(0.5, 1.04)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:.2f}", (v, i), textcoords="offset points", xytext=(4, 0),
                    va="center", color=INK, fontsize=8, fontweight="bold")
    ax.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("AUROC — 0.5 = random (held-out, grouped split)")
    ax.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.6)
    return fig


def honesty_dumbbell(metrics):
    """Random split (inflated, open) vs grouped split (honest, filled). Monochrome."""
    drugs = [m.drug for m in metrics]
    rnd = [m.balanced_acc_random for m in metrics]
    grp = [m.balanced_acc_grouped for m in metrics]
    y = range(len(drugs))
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _frame(ax)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LINE, linewidth=0.7)
    for i in y:
        ax.plot([grp[i], rnd[i]], [i, i], color=LINE, lw=2, zorder=1)
    ax.scatter(rnd, list(y), s=70, facecolors=SURF, edgecolors=MUTED, linewidths=1.5,
               zorder=2, label="Random split (inflated)")
    ax.scatter(grp, list(y), s=85, color=INK, zorder=3, label="Grouped split (honest)")
    for i in y:
        ax.annotate(f"{grp[i]:.2f}", (grp[i], i), textcoords="offset points",
                    xytext=(-6, 8), ha="right", color=INK, fontsize=8, fontweight="bold")
        ax.annotate(f"{rnd[i]:.2f}", (rnd[i], i), textcoords="offset points",
                    xytext=(6, 8), ha="left", color=MUTED, fontsize=8)
    ax.set_yticks(list(y)); ax.set_yticklabels(drugs, color=INK, fontsize=9)
    ax.set_xlim(0.5, 1.0); ax.set_xlabel("Balanced accuracy (held-out)")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    fig.tight_layout()
    return fig
