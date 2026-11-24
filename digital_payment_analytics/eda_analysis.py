"""
Stage 3 — Exploratory Data Analysis (EDA)
=========================================

Loads the Stage 2 synthetic digital-payment dataset, calculates descriptive
statistics, and produces univariate, bivariate and multivariate visualisations.

Library choice: pandas + numpy + matplotlib, with seaborn 0.13 for the
statistical plot conventions (count/box/strip plots and annotated heatmaps).
The descriptive statistics are unchanged; seaborn replaces the hand-built
bar, box, scatter and heatmap code so the plots are shorter and easier to read.

Outputs
-------
eda_outputs/summary_statistics.txt   Tabular descriptive statistics
eda_outputs/01_...png ... 12_...png   Figure gallery
eda_outputs/figure_index.txt          List of generated figures

The script is descriptive only. Any association reported below is not a claim
of causation.

Run::

    python eda_analysis.py
"""

import os

import matplotlib

matplotlib.use("Agg")  # headless rendering

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# 0. Configuration
# ---------------------------------------------------------------------------

sns.set_theme(style="whitegrid", context="notebook", palette="deep")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "eda_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

BLUE = "#4C72B0"
ORANGE = "#DD8452"
GREEN = "#55A868"
RED = "#C44E52"
PURPLE = "#8172B3"
GREY = "#8C8C8C"
PALETTE = [BLUE, ORANGE, GREEN, RED, PURPLE, GREY]

SEGMENT_ORDER = [
    "Tech Savvy", "Young Professionals", "Working Adults",
    "Traditional Users", "Senior Citizens",
]
CHANNEL_ORDER = [
    "Mobile Wallet", "QR Payment", "Debit Card",
    "Credit Card", "Online Banking", "Bank Transfer",
]
CHANNEL_COLORS = dict(zip(CHANNEL_ORDER, PALETTE))
STATUS_COLORS = {"Successful": GREEN, "Failed": RED, "Pending": ORANGE}
ADOPTION_ORDER = ["Low", "Medium", "High"]
ADOPTION_COLORS = dict(zip(ADOPTION_ORDER, [RED, ORANGE, GREEN]))


def save_figure(fig, filename):
    """Save a matplotlib figure into eda_outputs and close it."""
    path = os.path.join(OUT_DIR, filename)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def annotate_bars(ax, fmt="{:.0f}", offset=3):
    """Attach value labels to every non-empty bar container on an axis.

    Seaborn creates one container per hue level, so all containers are walked
    here; zero-height placeholders are skipped to avoid overlapping labels.
    """
    for container in ax.containers:
        for bar in container:
            height = bar.get_height()
            if not np.isfinite(height) or height == 0:
                continue
            ax.annotate(
                fmt.format(height),
                (bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, offset),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )


# ---------------------------------------------------------------------------
# 1. Load and enrich
# ---------------------------------------------------------------------------

tx = pd.read_csv(
    os.path.join(DATA_DIR, "transactions.csv"),
    parse_dates=["transaction_datetime", "transaction_date"],
)
customers = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
locations = pd.read_csv(os.path.join(DATA_DIR, "locations.csv"))

customer_extra = customers[[
    "customer_id", "age", "gender", "occupation", "monthly_income_bnd",
    "primary_payment_channel", "digital_payment_frequency",
]]
location_extra = locations[[
    "location_id", "district", "urbanity", "latitude", "longitude",
]]

df = tx.merge(customer_extra, on="customer_id", how="left")
df = df.merge(location_extra, on="location_id", how="left")

df["month"] = df["transaction_date"].dt.month
df["month_name"] = df["transaction_date"].dt.strftime("%b")
df["cross_border_flag"] = (df["is_cross_border"] == "Yes").astype(int)

NUMERIC_COLS = [
    "transaction_value_bnd", "transaction_hour", "adoption_tenure_months",
    "age", "monthly_income_bnd", "latitude", "longitude", "cross_border_flag",
]

figure_index = []


# ---------------------------------------------------------------------------
# 2. Descriptive statistics (written to text)
# ---------------------------------------------------------------------------

lines = []
lines.append("STAGE 3 - DESCRIPTIVE STATISTICS")
lines.append("=" * 72)
lines.append("")
lines.append(f"Transaction fact rows : {len(tx):,}")
lines.append(f"Customer dimension rows: {len(customers):,}")
lines.append(f"Location dimension rows: {len(locations):,}")
lines.append(f"Merged analysis frame  : {df.shape[0]:,} rows x {df.shape[1]} columns")
lines.append(f"Date range             : {df['transaction_date'].min().date()} "
             f"to {df['transaction_date'].max().date()}")
lines.append("")
lines.append("Missing values per column (merged frame):")
lines.append(df.isna().sum().to_string())
lines.append("")
lines.append("-" * 72)
lines.append("NUMERIC DESCRIBE - transaction-level variables")
lines.append("-" * 72)
lines.append(tx[[
    "transaction_hour", "transaction_value_bnd", "adoption_tenure_months",
]].describe().T.to_string())
lines.append("")
lines.append("-" * 72)
lines.append("NUMERIC DESCRIBE - customer/location variables")
lines.append("-" * 72)
lines.append(df[[
    "age", "monthly_income_bnd", "latitude", "longitude",
]].describe().T.to_string())
lines.append("")
lines.append("-" * 72)
lines.append("CATEGORICAL FREQUENCIES (count and share of 5,000 transactions)")
lines.append("-" * 72)

cat_cols = [
    "payment_channel", "merchant_category", "transaction_status",
    "device_type", "customer_segment", "adoption_level",
    "digital_payment_frequency", "is_cross_border", "district",
    "urbanity", "day_of_week",
]
for col in cat_cols:
    vc = df[col].value_counts()
    pct = (vc / len(df) * 100).round(2)
    lines.append(f"\n[{col}]")
    lines.append(
        pd.DataFrame({"count": vc, "percent": pct}).to_string()
    )

lines.append("")
lines.append("-" * 72)
lines.append("TRANSACTION VALUE - GROUPED SUMMARY (BND)")
lines.append("-" * 72)
for col in [
    "merchant_category", "payment_channel", "customer_segment",
    "adoption_level", "urbanity", "transaction_status", "district",
]:
    grouped = df.groupby(col)["transaction_value_bnd"].agg(
        ["count", "mean", "median", "std", "min", "max"]
    ).round(2).sort_values("median", ascending=False)
    lines.append(f"\n[{col}]")
    lines.append(grouped.to_string())

lines.append("")
lines.append("-" * 72)
lines.append("CROSS-TABULATIONS")
lines.append("-" * 72)
lines.append("\n[Segment x Channel - row percentages]")
lines.append(
    (pd.crosstab(df["customer_segment"], df["payment_channel"],
                 normalize="index") * 100).round(1).reindex(SEGMENT_ORDER).to_string()
)
lines.append("\n[Channel x Status - row percentages]")
lines.append(
    (pd.crosstab(df["payment_channel"], df["transaction_status"],
                 normalize="index") * 100).round(2).reindex(CHANNEL_ORDER).to_string()
)
lines.append("\n[Adoption x Urbanity - mean transaction value]")
lines.append(
    df.pivot_table(index="adoption_level", columns="urbanity",
                   values="transaction_value_bnd", aggfunc="mean")
    .round(2).to_string()
)
lines.append("\n[Segment x Urbanity - transaction counts]")
lines.append(
    pd.crosstab(df["customer_segment"], df["urbanity"])
    .reindex(SEGMENT_ORDER).to_string()
)

lines.append("")
lines.append("-" * 72)
lines.append("CORRELATION MATRIX (Pearson) - numeric variables")
lines.append("-" * 72)
corr = df[NUMERIC_COLS].corr()
lines.append(corr.round(3).to_string())
lines.append("")
pearson = df["monthly_income_bnd"].corr(df["transaction_value_bnd"])
spearman = df["monthly_income_bnd"].corr(
    df["transaction_value_bnd"], method="spearman"
)
lines.append(f"Income vs value  Pearson r  = {pearson:.3f}")
lines.append(f"Income vs value  Spearman rho = {spearman:.3f}")
lines.append(
    "Interpretation: association only. The generator scales amount by income, "
    "so a positive association is expected by design and is not causal evidence "
    "about real-world behaviour."
)

lines.append("")
lines.append("-" * 72)
lines.append("OUTLIER CHECK (Tukey 1.5 x IQR)")
lines.append("-" * 72)
values = df["transaction_value_bnd"]
q1, q3 = values.quantile([0.25, 0.75])
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
n_out = ((values < lower) | (values > upper)).sum()
lines.append(f"Q1={q1:.2f}  Q3={q3:.2f}  IQR={iqr:.2f}")
lines.append(f"Upper fence={upper:.2f}  Lower fence={lower:.2f}")
lines.append(f"High-value outliers: {n_out:,} ({n_out / len(df) * 100:.2f}%)")
lines.append("\nOutlier count by merchant category:")
lines.append(
    df.assign(outlier=(values > upper))
    .groupby("merchant_category")["outlier"]
    .sum().sort_values(ascending=False).to_string()
)
lines.append("\nTop 10 largest transactions:")
lines.append(
    df.nlargest(10, "transaction_value_bnd")[[
        "transaction_id", "transaction_value_bnd", "merchant_category",
        "payment_channel", "customer_segment", "monthly_income_bnd",
    ]].to_string(index=False)
)

with open(os.path.join(OUT_DIR, "summary_statistics.txt"), "w",
          encoding="utf-8") as handle:
    handle.write("\n".join(lines))


# ---------------------------------------------------------------------------
# 3. UNIVARIATE VISUALISATIONS
# ---------------------------------------------------------------------------

# 01 - distribution of transaction value
fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
sns.histplot(values, bins=50, color=BLUE, edgecolor="white", ax=axes[0])
axes[0].axvline(values.mean(), color=RED, linestyle="--",
                label=f"Mean = {values.mean():.2f}")
axes[0].axvline(values.median(), color=GREEN, linestyle="--",
                label=f"Median = {values.median():.2f}")
axes[0].set(title="Transaction value distribution",
            xlabel="Value (BND)", ylabel="Number of transactions")
axes[0].legend()
sns.boxplot(x=values, color=BLUE, width=0.6, fliersize=4,
            medianprops=dict(color=RED, linewidth=1.5), ax=axes[1])
axes[1].set(title="Transaction value boxplot (right-skewed)",
            xlabel="Value (BND)", yticks=[])
sns.despine(ax=axes[1], left=True)
fig.suptitle("01 | Univariate: transaction value", fontsize=13, fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "01_value_distribution.png"))

# 02 - categorical frequencies
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for ax, col in zip(axes.flat, [
    "payment_channel", "merchant_category", "transaction_status",
    "device_type", "customer_segment", "adoption_level",
]):
    counts = df[col].value_counts().sort_values()
    if col == "payment_channel":
        palette = {c: CHANNEL_COLORS.get(c, GREY) for c in counts.index}
    elif col == "transaction_status":
        palette = {c: STATUS_COLORS.get(c, GREY) for c in counts.index}
    else:
        palette = sns.color_palette("deep", len(counts))
    sns.countplot(data=df, y=col, order=counts.index, hue=col, legend=False,
                  palette=palette, ax=ax)
    ax.set(title=col.replace("_", " ").title(), xlabel="Transactions", ylabel="")
    annotate_bars(ax)
fig.suptitle("02 | Univariate: categorical profiles", fontsize=13,
             fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "02_categorical_counts.png"))

# 03 - temporal patterns
fig, axes = plt.subplots(1, 3, figsize=(16, 4.2))
sns.countplot(data=df, x="transaction_hour", color=BLUE, ax=axes[0])
axes[0].set(title="By hour of day", xlabel="Hour", ylabel="Transactions")
axes[0].set_xticks(range(0, 24, 2))

day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
sns.countplot(data=df, x="day_of_week", order=day_order, color=GREEN, ax=axes[1])
axes[1].set_xticks(range(len(day_order)), [d[:3] for d in day_order])
axes[1].set(title="By day of week", xlabel="", ylabel="Transactions")

month_counts = df.groupby("month").size()
sns.lineplot(x=month_counts.index, y=month_counts.values, marker="o",
             color=ORANGE, linewidth=2, ax=axes[2])
axes[2].set(title="By calendar month (2025)", xlabel="Month",
            ylabel="Transactions")
axes[2].set_xticks(range(1, 13))
fig.suptitle("03 | Univariate: when payments occur", fontsize=13,
             fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "03_temporal_patterns.png"))

# 04 - customer profile
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
sns.histplot(df["age"], bins=20, color=BLUE, edgecolor="white", ax=axes[0, 0])
axes[0, 0].set(title="Customer age (per transaction)",
               xlabel="Age", ylabel="Transactions")

income_order = sorted(df["monthly_income_bnd"].unique())
sns.countplot(data=df, x="monthly_income_bnd", order=income_order,
              color=PURPLE, ax=axes[0, 1])
axes[0, 1].set(title="Monthly income band (BND)",
               xlabel="Income band", ylabel="Transactions")
axes[0, 1].tick_params(axis="x", rotation=45)

sns.histplot(df["adoption_tenure_months"], bins=20, color=GREEN,
             edgecolor="white", ax=axes[1, 0])
axes[1, 0].set(title="Adoption tenure", xlabel="Months",
               ylabel="Transactions")

sns.countplot(data=df, x="digital_payment_frequency", color=ORANGE,
              ax=axes[1, 1])
axes[1, 1].set(title="Self-reported digital frequency",
               xlabel="Frequency", ylabel="Transactions")
fig.suptitle("04 | Univariate: customer profile attached to each payment",
             fontsize=13, fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "04_customer_profile.png"))


# ---------------------------------------------------------------------------
# 4. BIVARIATE VISUALISATIONS
# ---------------------------------------------------------------------------

# 05 - value by merchant category
order = df.groupby("merchant_category")["transaction_value_bnd"].median() \
           .sort_values().index
fig, ax = plt.subplots(figsize=(12, 5))
sns.boxplot(data=df, x="merchant_category", y="transaction_value_bnd",
            order=order, color=BLUE, width=0.7, fliersize=3,
            medianprops=dict(color=RED, linewidth=1.5),
            flierprops=dict(alpha=0.4), ax=ax)
ax.set(title="Transaction value by merchant category (ordered by median)",
       xlabel="Merchant category", ylabel="Value (BND)")
ax.tick_params(axis="x", rotation=35)
fig.tight_layout()
figure_index.append(save_figure(fig, "05_value_by_category.png"))

# 06 - segment x channel counts heatmap
ct = pd.crosstab(df["customer_segment"], df["payment_channel"]) \
        .reindex(index=SEGMENT_ORDER, columns=CHANNEL_ORDER)
fig, ax = plt.subplots(figsize=(10, 5))
sns.heatmap(ct, annot=True, fmt=",d", cmap="Blues", linewidths=0.5,
            annot_kws={"fontsize": 9},
            cbar_kws={"label": "Number of transactions"}, ax=ax)
ax.set(title="06 | Bivariate: segment x payment channel (counts)",
       xlabel="Payment channel", ylabel="Customer segment")
fig.tight_layout()
figure_index.append(save_figure(fig, "06_segment_channel_heatmap.png"))

# 07 - adoption, tenure and value
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
sns.boxplot(data=df, x="adoption_level", y="transaction_value_bnd",
            order=ADOPTION_ORDER, color=GREEN, width=0.6,
            medianprops=dict(color=RED), ax=axes[0])
axes[0].set(title="Value by adoption level", xlabel="Adoption level",
            ylabel="Value (BND)")

sns.scatterplot(data=df, x="adoption_tenure_months",
                y="transaction_value_bnd", hue="adoption_level",
                hue_order=ADOPTION_ORDER, palette=ADOPTION_COLORS,
                alpha=0.18, s=16, ax=axes[1])
axes[1].set(title="Tenure vs value (coloured by adoption)",
            xlabel="Adoption tenure (months)", ylabel="Value (BND)")
sns.move_legend(axes[1], "upper left", title=None, markerscale=2)
fig.suptitle("07 | Bivariate: adoption, tenure and value", fontsize=13,
             fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "07_adoption_tenure_value.png"))

# 08 - status mix by channel
status_ct = pd.crosstab(df["payment_channel"], df["transaction_status"],
                        normalize="index").mul(100) \
              .reindex(index=CHANNEL_ORDER)
status_ct = status_ct[[c for c in ["Successful", "Failed", "Pending"]
                       if c in status_ct.columns]]
ax = status_ct.plot(kind="barh", stacked=True, figsize=(10, 5),
                    color=[STATUS_COLORS[c] for c in status_ct.columns],
                    width=0.75)
ax.set(title="08 | Bivariate: transaction outcome mix by channel",
       xlabel="Share of channel transactions (%)", ylabel="")
ax.legend(title="Status", loc="lower right")
for container in ax.containers:
    for bar in container:
        width = bar.get_width()
        if width > 1.5:
            ax.annotate(f"{width:.1f}",
                        (bar.get_x() + width / 2, bar.get_y() + bar.get_height() / 2),
                        ha="center", va="center", fontsize=8, color="white")
fig = ax.get_figure()
fig.tight_layout()
figure_index.append(save_figure(fig, "08_status_by_channel.png"))

# 09 - income vs value
fig, ax = plt.subplots(figsize=(9, 5))
sns.stripplot(data=df, x="monthly_income_bnd", y="transaction_value_bnd",
              hue="adoption_level", hue_order=ADOPTION_ORDER,
              palette=ADOPTION_COLORS, jitter=0.25, alpha=0.25, size=3,
              ax=ax)
ax.set(title=f"09 | Bivariate: income band vs value (r={pearson:.3f}, "
             f"rho={spearman:.3f})",
       xlabel="Monthly income band (BND)",
       ylabel="Transaction value (BND)")
sns.move_legend(ax, "upper left", title=None, markerscale=1.5)
fig.tight_layout()
figure_index.append(save_figure(fig, "09_income_vs_value.png"))

# 10 - geography
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
district_counts = df["district"].value_counts()
sns.countplot(data=df, x="district", order=district_counts.index,
              color=BLUE, ax=axes[0])
axes[0].set(title="Transactions by district", xlabel="",
            ylabel="Transactions")
annotate_bars(axes[0])

urbanity_order = ["Urban", "Suburban", "Rural"]
urbanity_means = df.groupby("urbanity")["transaction_value_bnd"].mean() \
                    .reindex(urbanity_order)
sns.barplot(x=urbanity_means.index, y=urbanity_means.values,
            color=GREEN, ax=axes[1])
axes[1].set(title="Mean value by urbanity", xlabel="",
            ylabel="Mean value (BND)")
annotate_bars(axes[1], fmt="{:.2f}")
fig.suptitle("10 | Bivariate: where payments occur", fontsize=13,
             fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "10_geography.png"))


# ---------------------------------------------------------------------------
# 5. MULTIVARIATE VISUALISATIONS
# ---------------------------------------------------------------------------

# 11 - correlation heatmap
fig, ax = plt.subplots(figsize=(9, 7))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
            vmin=-1, vmax=1, square=True, linewidths=0.5,
            annot_kws={"fontsize": 8},
            xticklabels=[c.replace("_", "\n") for c in NUMERIC_COLS],
            yticklabels=[c.replace("_", " ") for c in NUMERIC_COLS],
            cbar_kws={"label": "Pearson r", "shrink": 0.8}, ax=ax)
ax.set(title="11 | Multivariate: numeric correlation matrix",
       xlabel="", ylabel="")
ax.tick_params(axis="x", rotation=45)
fig.tight_layout()
figure_index.append(save_figure(fig, "11_correlation_heatmap.png"))

# 12 - segment x channel mean value heatmap + top outliers
pivot = df.pivot_table(index="customer_segment", columns="payment_channel",
                       values="transaction_value_bnd", aggfunc="mean") \
          .reindex(index=SEGMENT_ORDER, columns=CHANNEL_ORDER)
top10 = df.nlargest(10, "transaction_value_bnd")

fig, axes = plt.subplots(1, 2, figsize=(15, 5.5),
                         gridspec_kw={"width_ratios": [1.5, 1]})
sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", linewidths=0.5,
            annot_kws={"fontsize": 9},
            cbar_kws={"label": "Mean value (BND)", "shrink": 0.8}, ax=axes[0])
axes[0].set(title="Mean value: segment x channel",
            xlabel="Payment channel", ylabel="Customer segment")

labels = [f"{row.merchant_category}\n{row.transaction_id}"
          for row in top10.itertuples()]
sns.barplot(x=top10["transaction_value_bnd"].values[::-1],
            y=labels[::-1], orient="h", color=RED, ax=axes[1])
axes[1].set(title="Ten largest payments (possible anomalies)",
            xlabel="Value (BND)", ylabel="")
axes[1].tick_params(axis="y", labelsize=8)
fig.suptitle("12 | Multivariate view and outlier inspection", fontsize=13,
             fontweight="bold")
fig.tight_layout()
figure_index.append(save_figure(fig, "12_multivariate_and_outliers.png"))

with open(os.path.join(OUT_DIR, "figure_index.txt"), "w",
          encoding="utf-8") as handle:
    handle.write("\n".join(os.path.basename(p) for p in figure_index))

print("EDA complete.")
print(f"Figures written: {len(figure_index)}")
print(f"Statistics file: {os.path.join(OUT_DIR, 'summary_statistics.txt')}")
print(f"Merged frame: {df.shape[0]:,} rows x {df.shape[1]} columns")
