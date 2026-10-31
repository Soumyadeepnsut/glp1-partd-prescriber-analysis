"""Build the README charts from outputs/tables/*.csv (run src/run_analysis.py first).

Usage (from the repo root):  python src/make_charts.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / "outputs" / "tables"
OUT = ROOT / "outputs" / "charts"
OUT.mkdir(parents=True, exist_ok=True)

# Palette: one fixed colour per molecule, everything else neutral
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
MOL_COLOR = {"Semaglutide": "#2a78d6", "Tirzepatide": "#eb6834", "Dulaglutide": "#1baf7a", "Other": "#b9b8b2"}
MOL_LABEL = {"Semaglutide": "Semaglutide (Ozempic, Rybelsus)", "Tirzepatide": "Tirzepatide (Mounjaro)",
             "Dulaglutide": "Dulaglutide (Trulicity)", "Other": "Liraglutide + exenatide"}
BLUE = "#2a78d6"
SOURCE = "Source: CMS Medicare Part D Prescribers by Provider and Drug, 2023-2024. Claims, not patients."

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
})


def finish(fig, title, subtitle, name):
    fig.text(0.01, 0.97, title, fontsize=14, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.905, subtitle, fontsize=10, color=INK2, ha="left", va="top")
    fig.text(0.01, 0.015, SOURCE, fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)
    print("saved", name)


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


# 1. Molecule share shift ----------------------------------------------------
ms = pd.read_csv(TAB / "molecule_share.csv")
ms["mol"] = ms.molecule.where(ms.molecule.isin(["Semaglutide", "Tirzepatide", "Dulaglutide"]), "Other")
sh = ms.groupby(["yr", "mol"]).claim_share.sum().unstack().loc[:, ["Semaglutide", "Tirzepatide", "Dulaglutide", "Other"]]
tot = pd.read_csv(TAB / "market_size.csv").set_index("yr")

fig, ax = plt.subplots(figsize=(10, 3.9))
fig.subplots_adjust(left=0.17, right=0.98, top=0.66, bottom=0.2)
for i, yr in enumerate([2024, 2023]):
    left = 0
    for mol in sh.columns:
        v = sh.loc[yr, mol]
        ax.barh(i, v, left=left, height=0.6, color=MOL_COLOR[mol], edgecolor=SURFACE, linewidth=2)
        if v > 0.05:
            ax.text(left + v / 2, i, pct(v), ha="center", va="center", color="white", fontsize=10, fontweight="bold")
        left += v
ax.set_yticks([0, 1], [f"2024\n{tot.loc[2024, 'claims'] / 1e6:.1f}M claims", f"2023\n{tot.loc[2023, 'claims'] / 1e6:.1f}M claims"])
ax.set_xlim(0, 1)
ax.xaxis.set_major_formatter(mt.PercentFormatter(1.0))
ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False)
handles = [plt.Rectangle((0, 0), 1, 1, color=MOL_COLOR[m]) for m in sh.columns]
fig.legend(handles, [MOL_LABEL[m] for m in sh.columns], loc="upper left", bbox_to_anchor=(0.01, 0.82),
           ncol=4, frameon=False, fontsize=9, handlelength=1, columnspacing=1.4)
finish(fig, "Mounjaro more than doubled its share of GLP-1 claims in one year",
       "Share of Medicare Part D GLP-1 claims by molecule. Trulicity lost the most ground.", "01_molecule_share.png")

# 2. Specialty mix: share of claims vs claims per prescriber (two panels, one axis each)
sp = pd.read_csv(TAB / "specialty_mix_2024.csv").head(7).iloc[::-1]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
fig.subplots_adjust(left=0.17, right=0.97, top=0.76, bottom=0.12, wspace=0.12)
a1.barh(sp.specialty, sp.claim_share, color=BLUE, height=0.62)
a2.barh(sp.specialty, sp.claims_per_prescriber, color=[("#eb6834" if s == "Endocrinology" else BLUE) for s in sp.specialty], height=0.62)
for y, v in zip(sp.specialty, sp.claim_share):
    a1.text(v + 0.005, y, pct(v, 1), va="center", fontsize=9, color=INK2)
for y, v in zip(sp.specialty, sp.claims_per_prescriber):
    a2.text(v + 6, y, f"{v:.0f}", va="center", fontsize=9, color=INK2)
a1.set_title("Share of all GLP-1 claims", fontsize=10, loc="left", color=INK2)
a2.set_title("Claims per prescriber", fontsize=10, loc="left", color=INK2)
a1.xaxis.set_major_formatter(mt.PercentFormatter(1.0, decimals=0))
a1.set_xlim(0, 0.36); a2.set_xlim(0, 500)
for a in (a1, a2):
    a.tick_params(axis="y", length=0); a.spines["left"].set_visible(False)
    a.grid(axis="x", color=GRID, linewidth=0.8); a.set_axisbelow(True)
finish(fig, "Primary care writes most GLP-1 claims; endocrinologists write the most per head",
       "2024. Family/internal medicine, NPs and PAs = 82% of claims. 5,879 endocrinologists average 4.7x a family physician.",
       "02_specialty_mix.png")

# 3. Prescriber concentration (cumulative share curve) ------------------------
dec = pd.read_csv(TAB / "prescriber_deciles_2024.csv")
cum = dec.claim_share.cumsum()
x = [0] + list(dec.decile / 10)
y = [0] + list(cum)
fig, ax = plt.subplots(figsize=(10, 4.4))
fig.subplots_adjust(left=0.09, right=0.97, top=0.76, bottom=0.17)
ax.plot(x, y, color=BLUE, linewidth=2, marker="o", markersize=5)
ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--")
ax.text(0.62, 0.55, "if every prescriber wrote equally", color=MUTED, fontsize=9, rotation=0)
ax.annotate(f"Top 10% of prescribers\n= {pct(cum[0])} of claims", (0.1, cum[0]), xytext=(0.015, 0.66),
            fontsize=9, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
ax.annotate(f"Top 20% = {pct(cum[1])}", (0.2, cum[1]), xytext=(0.27, 0.45),
            fontsize=9, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
ax.xaxis.set_major_formatter(mt.PercentFormatter(1.0)); ax.yaxis.set_major_formatter(mt.PercentFormatter(1.0))
ax.set_xlabel("Prescribers, ranked from highest GLP-1 volume"); ax.set_ylabel("Cumulative share of claims")
ax.grid(color=GRID, linewidth=0.8); ax.set_axisbelow(True)
finish(fig, "A small group of prescribers drives most of the volume",
       "2024. Roughly 20,000 prescribers write 41% of GLP-1 claims; 14% of prescribers write half.",
       "03_prescriber_concentration.png")

# 4. Mounjaro share by state ---------------------------------------------------
st = pd.read_csv(TAB / "mounjaro_share_by_state_2024.csv").sort_values("mounjaro_share")
nat = float(ms[(ms.yr == 2024) & (ms.molecule == "Tirzepatide")].claim_share.iloc[0])
fig, ax = plt.subplots(figsize=(10, 4.6))
fig.subplots_adjust(left=0.07, right=0.98, top=0.78, bottom=0.17)
cols = ["#eb6834" if v >= nat else "#f4b293" for v in st.mounjaro_share]
ax.bar(st.state, st.mounjaro_share, color=cols, width=0.72)
ax.axhline(nat, color=INK2, linewidth=1, linestyle="--")
ax.text(0.3, nat + 0.008, f"US average {pct(nat, 1)}", fontsize=9, color=INK2)
for _, r in pd.concat([st.head(1), st.tail(1)]).iterrows():
    ax.text(r.state, r.mounjaro_share + 0.006, pct(r.mounjaro_share), ha="center", fontsize=9, color=INK)
ax.yaxis.set_major_formatter(mt.PercentFormatter(1.0, decimals=0)); ax.set_ylim(0, 0.42)
ax.tick_params(axis="x", labelsize=7, rotation=90, length=0)
ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
finish(fig, "Mounjaro uptake varies more than 3x across states",
       "2024 Mounjaro share of GLP-1 claims by prescriber state. Darker bars are above the US average.",
       "04_mounjaro_share_by_state.png")

# 5. Whitespace: prescribers without Mounjaro, by GLP-1 volume quintile ------
ws = pd.read_csv(TAB / "whitespace_2024.csv")
labels = ["Top 20%", "20-40%", "40-60%", "60-80%", "Bottom 20%"]
fig, ax = plt.subplots(figsize=(10, 4.4))
fig.subplots_adjust(left=0.09, right=0.97, top=0.76, bottom=0.17)
ax.bar(labels, ws.share_no_mounjaro, color=[("#eb6834" if q == 1 else BLUE) for q in ws.quintile], width=0.6)
for lab, r in zip(labels, ws.itertuples()):
    ax.text(lab, r.share_no_mounjaro + 0.02, f"{pct(r.share_no_mounjaro)}\n{r.no_mounjaro:,} prescribers",
            ha="center", fontsize=9, color=INK)
ax.yaxis.set_major_formatter(mt.PercentFormatter(1.0)); ax.set_ylim(0, 1.05)
ax.set_xlabel("Prescribers grouped by 2024 GLP-1 claim volume"); ax.set_ylabel("Share with no Mounjaro")
ax.tick_params(axis="x", length=0)
ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
top = ws.iloc[0]
n_top, c_top = int(top.no_mounjaro), int(top.glp1_claims_of_no_mounjaro)
finish(fig, f"{n_top:,} high-volume GLP-1 prescribers still write no Mounjaro",
       f"2024. Those {n_top:,} top-quintile prescribers wrote {c_top / 1e3:.0f}K GLP-1 claims, all on other molecules.",
       "05_mounjaro_whitespace.png")
