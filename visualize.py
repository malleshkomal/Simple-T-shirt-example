"""STEP 4 - ANIMATED VISUALISATION (matplotlib -> GIF)
Reads data/processed/lca_summary.json and writes three animated charts to output/.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

ROOT = Path(__file__).parent
S = json.loads((ROOT / "data/processed/lca_summary.json").read_text())
OUT = ROOT / "output"
PRODUCTS, STAGES, MONTHS = S["products"], S["stages"], S["months"]
PIDS = list(S["per_unit_by_stage"])
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # fixed categorical order
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
STAGE_LABEL = {s: s.replace("_", " ").capitalize() for s in STAGES}

plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False})


def ease(t):                      # smooth ease-in-out, 0..1
    return t * t * (3 - 2 * t)


def stacked_build():
    """Stages stack up one after another for each product."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.subplots_adjust(left=0.18, right=0.97, top=0.82, bottom=0.14)
    names = [PRODUCTS[p] for p in PIDS]
    totals = [sum(S["per_unit_by_stage"][p].values()) for p in PIDS]
    steps_per_stage, hold = 12, 20
    frames = steps_per_stage * len(STAGES) + hold

    def draw(f):
        ax.clear()
        ax.set_xlim(0, max(totals) * 1.18)
        ax.set_title("Carbon footprint per product, built stage by stage", loc="left", color=INK, fontsize=12, pad=28)
        ax.set_xlabel("kg CO2e per unit")
        ax.grid(axis="x", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
        left = [0.0] * len(PIDS)
        for i, stage in enumerate(STAGES):
            t = ease(min(max((f - i * steps_per_stage) / steps_per_stage, 0), 1))
            vals = [S["per_unit_by_stage"][p][stage] * t for p in PIDS]
            ax.barh(names, vals, left=left, color=SERIES[i], height=0.55,
                    edgecolor=SURFACE, linewidth=2, label=STAGE_LABEL[stage])
            left = [l + v for l, v in zip(left, vals)]
        for y, v in enumerate(left):
            ax.text(v + 0.15, y, f"{v:.2f}", va="center", color=INK, fontsize=10)
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=5, frameon=False, fontsize=8)

    FuncAnimation(fig, draw, frames=frames).save(OUT / "1_stacked_build.gif", writer=PillowWriter(fps=24))
    plt.close(fig)


def monthly_lines():
    """Monthly emissions drawn month by month, with a moving end-point label."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.13)
    sub = 6                                         # interpolation frames between months
    frames = (len(MONTHS) - 1) * sub + 24
    ymax = max(max(S["monthly_tonnes"][p].values()) for p in PIDS) * 1.15

    def draw(f):
        ax.clear()
        ax.set_xlim(-0.3, len(MONTHS) - 1 + 2.2); ax.set_ylim(0, ymax)
        ax.set_xticks(range(len(MONTHS)), [m[5:] for m in MONTHS])
        ax.set_xlabel("Month (2025)"); ax.set_ylabel("t CO2e")
        ax.set_title("Monthly emissions by product", loc="left", color=INK, fontsize=12)
        ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
        pos = min(f / sub, len(MONTHS) - 1)
        for i, p in enumerate(PIDS):
            ys = [S["monthly_tonnes"][p][m] for m in MONTHS]
            k = int(pos)
            xs, yv = list(range(k + 1)), ys[:k + 1]
            if k < len(MONTHS) - 1:
                frac = pos - k
                xs.append(pos); yv.append(ys[k] + (ys[k + 1] - ys[k]) * frac)
            ax.plot(xs, yv, color=SERIES[i], linewidth=2)
            ax.scatter(xs[-1], yv[-1], s=40, color=SERIES[i], edgecolor=SURFACE, linewidth=2, zorder=3)
            ax.text(xs[-1] + 0.2, yv[-1], f"{PRODUCTS[p]}  {yv[-1]:.0f} t", va="center", fontsize=8, color=INK)
        ax.axvline(6, color=MUTED, linestyle=":", linewidth=1)
        ax.text(6.1, ymax * 0.95, "Efficiency program starts", fontsize=8, color=MUTED)

    FuncAnimation(fig, draw, frames=frames).save(OUT / "2_monthly_lines.gif", writer=PillowWriter(fps=20))
    plt.close(fig)


def cumulative_race():
    """Horizontal bars race to the year's cumulative total; bars re-sort as they grow."""
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.subplots_adjust(left=0.18, right=0.97, top=0.9, bottom=0.15)
    sub = 8
    frames = len(MONTHS) * sub + 20
    cum = {p: [] for p in PIDS}
    for p in PIDS:
        run = 0
        for m in MONTHS:
            run += S["monthly_tonnes"][p][m]; cum[p].append(run)
    xmax = max(c[-1] for c in cum.values()) * 1.2

    def draw(f):
        ax.clear()
        pos = min(f / sub, len(MONTHS))
        k = int(pos)
        vals = {}
        for p in PIDS:
            prev = cum[p][k - 1] if k > 0 else 0
            nxt = cum[p][min(k, len(MONTHS) - 1)]
            vals[p] = prev + (nxt - prev) * (pos - k) if k < len(MONTHS) else cum[p][-1]
        order = sorted(PIDS, key=lambda p: vals[p])
        ax.barh([PRODUCTS[p] for p in order], [vals[p] for p in order],
                color=[SERIES[PIDS.index(p)] for p in order], height=0.55)
        for y, p in enumerate(order):
            ax.text(vals[p] + xmax * 0.01, y, f"{vals[p]:,.0f} t", va="center", fontsize=10, color=INK)
        ax.set_xlim(0, xmax)
        ax.grid(axis="x", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
        label = MONTHS[min(max(k - 1, 0) if pos >= len(MONTHS) else k, 11)]
        ax.set_title(f"Cumulative emissions, through {label}", loc="left", color=INK, fontsize=12)
        ax.set_xlabel("t CO2e")

    FuncAnimation(fig, draw, frames=frames).save(OUT / "3_cumulative_race.gif", writer=PillowWriter(fps=20))
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    stacked_build(); monthly_lines(); cumulative_race()
    print("Wrote", sorted(p.name for p in OUT.glob("*.gif")))
