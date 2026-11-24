"""
Stage 6 — Visualisation and communication
=========================================

Creates a coherent set of six question-led charts plus a compact dashboard.
Every chart has: a clear question title, labelled axes (with units where
applicable) and a short interpretation printed beneath the plot.

No decorative charts are produced: each figure answers one analytical
question derived from Stages 3–5.

Run::

    python stage6_dashboard.py
"""

import os

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# 0. Configuration and data
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "stage6_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    plt.style.use("ggplot")

BLUE = "#4C72B0"
ORANGE = "#DD8452"
GREEN = "#55A868"
RED = "#C44E52"
PURPLE = "#8172B3"
GREY = "#8C8C8C"
PALETTE = [BLUE, ORANGE, GREEN, RED, PURPLE, GREY]

tx = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"))
cust = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
loc = pd.read_csv(os.path.join(DATA_DIR, "locations.csv"))

success = tx[tx["transaction_status"] == "Successful"].copy()

# Pre-computed values used in annotations / interpretations.
n = len(tx)
q1, q3 = tx["transaction_value_bnd"].quantile([0.25, 0.75])
upper_fence = q3 + 1.5 * (q3 - q1)
n_out = (tx["transaction_value_bnd"] > upper_fence).sum()
outliers = tx[tx["transaction_value_bnd"] > upper_fence]


# ---------------------------------------------------------------------------
# 1. Plotting functions — each draws exactly one question on one axis
# ---------------------------------------------------------------------------

def draw_channel(ax):
    counts = tx["payment_channel"].value_counts()
    colors = [CHANNEL_COLORS.get(c, BLUE) for c in counts.index]
    bars = ax.barh(counts.index, counts.values, color=colors)
    for bar in bars:
        value = bar.get_width()
        ax.text(value + 12, bar.get_y() + bar.get_height() / 2,
                f"{int(value):,} ({value / n * 100:.1f}%)",
                va="center", fontsize=8)
    ax.set_xlim(0, counts.max() * 1.22)
    ax.set_xlabel("Number of transactions (share in brackets)")
    ax.set_ylabel("Payment channel")
    ax.set_title("Which payment channels are used most?",
                 fontsize=11, fontweight="bold", loc="left")


CHANNEL_COLORS = {
    "Mobile Wallet": BLUE,
    "QR Payment": GREEN,
    "Debit Card": ORANGE,
    "Credit Card": PURPLE,
    "Online Banking": GREY,
    "Bank Transfer": RED,
}


def draw_category(ax):
    grouped = success.groupby("merchant_category")["transaction_value_bnd"] \
                      .agg(["sum", "count"]).sort_values("sum")
    bars = ax.barh(grouped.index, grouped["sum"], color=BLUE)
    for bar, (_, row) in zip(bars, grouped.iterrows()):
        ax.text(bar.get_width() + 2500,
                bar.get_y() + bar.get_height() / 2,
                f"{row['sum']:,.0f} BND  (n={int(row['count'])})",
                va="center", fontsize=8)
    ax.set_xlim(0, grouped["sum"].max() * 1.28)
    ax.set_xlabel("Successful transaction value (BND)")
    ax.set_ylabel("Merchant category")
    ax.set_title("Which categories generate the most spend?",
                 fontsize=11, fontweight="bold", loc="left")


def draw_segment(ax):
    seg = success.copy()
    seg["digital"] = seg["payment_channel"].isin(
        ["Mobile Wallet", "QR Payment"]
    ).astype(int)
    shares = seg.groupby("customer_segment")["digital"].mean() * 100
    shares = shares.sort_values()
    bars = ax.barh(shares.index, shares.values,
                   color=[GREEN if v >= 40 else ORANGE for v in shares.values])
    for bar in bars:
        ax.text(bar.get_width() + 0.8, bar.get_y() + bar.get_height() / 2,
                f"{bar.get_width():.1f}%", va="center", fontsize=8)
    ax.set_xlim(0, 78)
    ax.set_xlabel("Wallet + QR share of successful payments (%)")
    ax.set_ylabel("Customer segment")
    ax.set_title("Which segments are digital-first?",
                 fontsize=11, fontweight="bold", loc="left")


def draw_outcome(ax):
    ct = pd.crosstab(tx["payment_channel"], tx["transaction_status"],
                     normalize="index").mul(100)
    ct = ct[["Successful", "Failed", "Pending"]]
    colors = [GREEN, RED, ORANGE]
    ct.plot(kind="barh", stacked=True, ax=ax, color=colors, width=0.72)
    ax.set_xlabel("Share of channel transactions (%)")
    ax.set_ylabel("Payment channel")
    ax.set_title("Do outcomes differ by payment channel?",
                 fontsize=11, fontweight="bold", loc="left")
    ax.legend(title="Status", loc="lower right", fontsize=8, title_fontsize=8)


def draw_geography(ax):
    counts = loc.merge(tx.groupby("location_id").size().rename("n"),
                       on="location_id", how="left") \
                .groupby("district")["n"].sum().sort_values()
    bars = ax.barh(counts.index, counts.values, color=PURPLE)
    for bar in bars:
        value = bar.get_width()
        ax.text(value + 30, bar.get_y() + bar.get_height() / 2,
                f"{int(value):,} ({value / n * 100:.1f}%)",
                va="center", fontsize=8)
    ax.set_xlim(0, counts.max() * 1.25)
    ax.set_xlabel("Number of transactions (share in brackets)")
    ax.set_ylabel("District")
    ax.set_title("Where do payments concentrate?",
                 fontsize=11, fontweight="bold", loc="left")
    means = tx.merge(loc[["location_id", "urbanity"]], on="location_id") \
              .groupby("urbanity")["transaction_value_bnd"].mean()
    note = "Mean value (BND): " + " | ".join(
        f"{k} {v:.2f}" for k, v in means.items()
    )
    ax.text(0.98, 0.04, note, transform=ax.transAxes, ha="right",
            fontsize=7.5, style="italic",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=GREY, alpha=0.9))


def draw_value(ax):
    ax.hist(tx["transaction_value_bnd"], bins=60, color=BLUE,
            edgecolor="white", alpha=0.9)
    ax.axvline(tx["transaction_value_bnd"].median(), color=GREEN,
               linestyle="--", linewidth=1.5,
               label=f"Median {tx['transaction_value_bnd'].median():.2f} BND")
    ax.axvline(upper_fence, color=RED, linestyle="--", linewidth=1.5,
               label=f"Tukey fence {upper_fence:.2f} BND")
    ax.set_xlabel("Transaction value (BND)")
    ax.set_ylabel("Number of transactions")
    ax.set_title("Are there extreme payment values?",
                 fontsize=11, fontweight="bold", loc="left")
    ax.legend(fontsize=8)
    top_cat = outliers["merchant_category"].value_counts().idxmax()
    top_n = outliers["merchant_category"].value_counts().max()
    ax.text(0.97, 0.95,
            f"{n_out} payments ({n_out / n * 100:.1f}%) above the fence\n"
            f"{top_n} of them are {top_cat}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=RED, alpha=0.9))


# ---------------------------------------------------------------------------
# 2. Interpretations (short, question-answering)
# ---------------------------------------------------------------------------

INTERPRETATIONS = {
    1: "Debit Card is the single most used rail (20.1%); wallet + QR together "
       "reach 38.0%, so no channel dominates the mix.",
    2: "Restaurant and Grocery lead by count, but Retail (200.7k BND) and "
       "Travel (133.4k BND from only 174 payments) drive value.",
    3: "Tech Savvy customers use wallet/QR for 66.2% of payments versus 13.3% "
       "for Senior Citizens - a segment gradient, not an income effect.",
    4: "Success stays within 93.2-95.4% across channels; the small spread is "
       "consistent with sampling variation, not a channel performance effect.",
    5: "Brunei-Muara accounts for 68.4% of payments, while mean values by "
       "urbanity are similar (160-176 BND): volume is concentrated, amounts are not.",
    6: "225 payments (4.5%) exceed 491.54 BND and 122 are Travel - an expected "
       "tail from wide Travel value ranges, not necessarily data errors.",
}

QUESTIONS = {
    1: "Q1 | Which payment channels are used most?",
    2: "Q2 | Which categories generate the most spend?",
    3: "Q3 | Which segments are digital-first?",
    4: "Q4 | Do outcomes differ by payment channel?",
    5: "Q5 | Where do payments concentrate?",
    6: "Q6 | Are there extreme payment values?",
}

DRAWERS = {
    1: draw_channel,
    2: draw_category,
    3: draw_segment,
    4: draw_outcome,
    5: draw_geography,
    6: draw_value,
}

FILENAMES = {
    1: "01_channel_usage.png",
    2: "02_category_spend.png",
    3: "03_segment_digital.png",
    4: "04_channel_outcomes.png",
    5: "05_geography.png",
    6: "06_value_outliers.png",
}


def save_single(index):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    DRAWERS[index](ax)
    fig.suptitle(QUESTIONS[index], fontsize=13, fontweight="bold", x=0.06,
                 ha="left", y=0.99)
    fig.text(0.5, 0.015,
             "Interpretation: " + INTERPRETATIONS[index],
             ha="center", fontsize=9, style="italic", color="#333333")
    fig.subplots_adjust(bottom=0.22, top=0.84, left=0.16)
    path = os.path.join(OUT_DIR, FILENAMES[index])
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


paths = [save_single(i) for i in range(1, 7)]

# ---------------------------------------------------------------------------
# 3. Compact dashboard (3 x 2)
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(3, 2, figsize=(18, 15))
fig.suptitle("Digital Payment Analytics - Main Findings (2025)",
             fontsize=18, fontweight="bold", y=0.995)

for index, ax in zip(range(1, 7), axes.flat):
    DRAWERS[index](ax)
    ax.text(0.5, -0.24, "Interpretation: " + INTERPRETATIONS[index],
            transform=ax.transAxes, ha="center", va="top", fontsize=8.5,
            style="italic", color="#333333", wrap=True)

fig.subplots_adjust(hspace=0.62, wspace=0.32, top=0.94, bottom=0.06)
dashboard_path = os.path.join(OUT_DIR, "00_dashboard.png")
fig.savefig(dashboard_path, dpi=140, bbox_inches="tight")
plt.close(fig)

with open(os.path.join(OUT_DIR, "chart_index.txt"), "w",
          encoding="utf-8") as handle:
    handle.write("\n".join(
        [os.path.basename(dashboard_path)] +
        [os.path.basename(p) for p in paths]
    ))

print("Stage 6 visualisations complete.")
for path in [dashboard_path] + paths:
    print(" -", path)
