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


def _clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_axisbelow(True)
    return ax


def reliability_curve(points=None):
    """Predicted probability vs observed frequency. Diagonal = perfect."""
    points = points or []
    conf = [p.get("confidence", p.get("mean_predicted")) for p in points]
    obs = [p.get("accuracy", p.get("observed_resistant_fraction")) for p in points]
    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    _clean(ax)
    ax.grid(color=LINE, linewidth=0.7)
    ax.plot([0.5, 1], [0.5, 1], "--", color=MUTED, lw=1.4, label="Perfect calibration")
    if conf:
        ax.plot(conf, obs, "-o", color=INK, lw=1.8, markersize=6, label="Model")
    ax.set_xlim(0.5, 1); ax.set_ylim(0.5, 1)
    ax.set_xlabel("Predicted confidence"); ax.set_ylabel("Observed accuracy")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def auroc_bars(metrics):
    """Per-drug AUROC (threshold-free discrimination), sorted, with a 0.5 = random line."""
    ms = sorted(metrics, key=lambda m: m.auroc)
    drugs = [m.drug for m in ms]; vals = [m.auroc for m in ms]
    fig, ax = plt.subplots(figsize=(5.2, 0.42 * len(drugs) + 0.9))
    _clean(ax)
    ax.axvline(0.5, color=MUTED, lw=1.2, ls="--")
    ax.text(0.5, len(drugs) - 0.35, " random", color=MUTED, fontsize=8, va="center")
    ax.barh(drugs, vals, color=INK, height=0.6)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:.2f}", (v, i), textcoords="offset points", xytext=(5, 0),
                    va="center", color=INK, fontsize=9, fontweight="bold")
    ax.set_xlim(0.5, 1.0); ax.set_xlabel("AUROC (held-out, grouped split)")
    fig.tight_layout()
    return fig


def honesty_dumbbell(metrics):
    """Random split (inflated, open) vs grouped split (honest, filled). Monochrome."""
    drugs = [m.drug for m in metrics]
    rnd = [m.balanced_acc_random for m in metrics]
    grp = [m.balanced_acc_grouped for m in metrics]
    y = range(len(drugs))
    fig, ax = plt.subplots(figsize=(5.2, 0.48 * len(drugs) + 1.0))
    _clean(ax)
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
