"""
TD2310 - Introduction to Data Visualization
Fundamental Chart Types and Chart Selection - Applied EDA

Dataset:
    data/transactions.csv
    data/customers.csv
    data/locations.csv

Required packages:
    pip install pandas matplotlib numpy

This script follows FundamentalChartTypesandSelection.py and applies the same
15 chart types to the Brunei digital-payment dataset. Each section starts with
the analytical question and the chart-selection principle it demonstrates.

The examples reinforce the chart-selection principles:
- Start with the analytical question.
- Identify the type of data.
- Match the chart to the task.
- Keep the visual simple.
- Avoid misleading design.

All charts are saved as PNG files, then shown in a single window with
< Previous / Next > buttons (or the left/right arrow keys), so you can change
charts without clicking the X button on a separate window each time.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import numpy as np
import pandas as pd


# ============================================================
# 1. FILE SETTINGS
# ============================================================

# Keep the CSV dataset in the same folder structure as this script.
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

OUTPUT_DIR = BASE_DIR / "EDA_ChartSelection_Output"
OUTPUT_DIR.mkdir(exist_ok=True)

SEGMENT_ORDER = [
    "Tech Savvy", "Young Professionals", "Working Adults",
    "Traditional Users", "Senior Citizens",
]
CHANNEL_ORDER = [
    "Mobile Wallet", "QR Payment", "Debit Card",
    "Credit Card", "Online Banking", "Bank Transfer",
]
STATUS_ORDER = ["Successful", "Failed", "Pending"]

BLUE = "#4C72B0"
GREEN = "#55A868"
ORANGE = "#DD8452"
RED = "#C44E52"


# ============================================================
# 2. LOAD DATA
# ============================================================

transactions = pd.read_csv(
    DATA_DIR / "transactions.csv",
    parse_dates=["transaction_datetime", "transaction_date"],
)
customers = pd.read_csv(DATA_DIR / "customers.csv")
locations = pd.read_csv(DATA_DIR / "locations.csv")

df = transactions.merge(
    customers[[
        "customer_id", "age", "gender", "monthly_income_bnd",
        "digital_payment_frequency",
    ]],
    on="customer_id",
    how="left",
)
df = df.merge(
    locations[["location_id", "district", "urbanity"]],
    on="location_id",
    how="left",
)

# A single datetime column keeps the time-based charts simple.
df["Month"] = df["transaction_date"].dt.to_period("M").dt.to_timestamp()

print("Dataset loaded successfully.")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Date range:", df["transaction_date"].min().date(),
      "to", df["transaction_date"].max().date())


# ============================================================
# 3. HELPER FUNCTION
# ============================================================

CHART_FILES = []
CHART_TITLES = []


def finish_chart(filename):
    """
    Save the current figure as a PNG file, record it for the
    interactive viewer, then close it.
    """
    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / filename,
        dpi=200,
        bbox_inches="tight"
    )
    CHART_FILES.append(filename)
    CHART_TITLES.append(plt.gca().get_title())
    plt.close()


# ============================================================
# CHART 1: BAR CHART
# ============================================================
# Best for:
# Comparing values across categories.
#
# Question:
# Which payment channel has the highest average transaction value?
# ============================================================

channel_value = (
    df.groupby("payment_channel")["transaction_value_bnd"]
      .mean()
      .sort_values(ascending=False)
)

plt.figure(figsize=(9, 5))
channel_value.plot(kind="bar", color=BLUE)

plt.title("1. Bar Chart: Average Transaction Value by Payment Channel")
plt.xlabel("Payment channel")
plt.ylabel("Average value (BND)")
plt.xticks(rotation=30, ha="right")
plt.grid(axis="y", alpha=0.3)

finish_chart("01_bar_chart.png")


# ============================================================
# CHART 2: GROUPED BAR CHART
# ============================================================
# Best for:
# Comparing subcategories across larger categories.
#
# Question:
# How does average transaction value differ by segment and channel?
# ============================================================

grouped_data = (
    df.groupby(["customer_segment", "payment_channel"])["transaction_value_bnd"]
      .mean()
      .unstack()
      .reindex(index=SEGMENT_ORDER, columns=CHANNEL_ORDER)
)

plt.figure(figsize=(10, 5))
grouped_data.plot(
    kind="bar",
    ax=plt.gca()
)

plt.title("2. Grouped Bar Chart: Value by Segment and Payment Channel")
plt.xlabel("Customer segment")
plt.ylabel("Average value (BND)")
plt.xticks(rotation=25, ha="right")
plt.legend(title="Payment channel", fontsize=8)

finish_chart("02_grouped_bar_chart.png")


# ============================================================
# CHART 3: STACKED BAR CHART
# ============================================================
# Best for:
# Showing composition within categories.
#
# Question:
# How many transactions of each status occur in each month?
# ============================================================

stacked_data = (
    df.groupby(["Month", "transaction_status"])
      .size()
      .unstack(fill_value=0)
      .reindex(columns=STATUS_ORDER, fill_value=0)
)

# Convert datetime index into simple month labels.
stacked_data.index = stacked_data.index.strftime("%b")

plt.figure(figsize=(9, 5))

stacked_data.plot(
    kind="bar",
    stacked=True,
    ax=plt.gca(),
    color=[GREEN, RED, ORANGE]
)

plt.title("3. Stacked Bar Chart: Transaction Status by Month")
plt.xlabel("Month")
plt.ylabel("Number of transactions")
plt.xticks(rotation=0)
plt.legend(title="Status")

finish_chart("03_stacked_bar_chart.png")


# ============================================================
# CHART 4: LINE CHART
# ============================================================
# Best for:
# Showing change over time.
#
# Question:
# How does average transaction value change during 2025?
# ============================================================

monthly_value = (
    df.groupby("Month")["transaction_value_bnd"]
      .mean()
      .sort_index()
)

plt.figure(figsize=(8, 5))

plt.plot(
    monthly_value.index,
    monthly_value.values,
    marker="o",
    color=BLUE
)

plt.title("4. Line Chart: Average Transaction Value Over Time")
plt.xlabel("Month")
plt.ylabel("Average value (BND)")
plt.xticks(
    monthly_value.index,
    [d.strftime("%b") for d in monthly_value.index],
    rotation=30
)
plt.grid(axis="y", alpha=0.3)

finish_chart("04_line_chart.png")


# ============================================================
# CHART 5: AREA CHART
# ============================================================
# Best for:
# Showing trend while emphasizing magnitude over time.
#
# Question:
# How does monthly transaction volume change over the year?
# ============================================================

monthly_volume = (
    df.groupby("Month")
      .size()
      .sort_index()
)

plt.figure(figsize=(8, 5))

plt.fill_between(
    monthly_volume.index,
    monthly_volume.values,
    alpha=0.5,
    color=ORANGE
)

plt.plot(
    monthly_volume.index,
    monthly_volume.values,
    marker="o",
    color=ORANGE
)

plt.title("5. Area Chart: Monthly Transaction Volume")
plt.xlabel("Month")
plt.ylabel("Number of transactions")
plt.xticks(
    monthly_volume.index,
    [d.strftime("%b") for d in monthly_volume.index],
    rotation=30
)

finish_chart("05_area_chart.png")


# ============================================================
# CHART 6: PIE CHART
# ============================================================
# Best for:
# Showing simple part-to-whole composition
# when there are only a few categories.
#
# Question:
# What share of payments comes from each device type?
# ============================================================

device_counts = df["device_type"].value_counts()

plt.figure(figsize=(7, 7))

plt.pie(
    device_counts.values,
    labels=device_counts.index,
    autopct="%1.1f%%",
    startangle=90
)

plt.title("6. Pie Chart: Payments by Device Type")

finish_chart("06_pie_chart.png")


# ============================================================
# CHART 7: DOUGHNUT CHART
# ============================================================
# Best for:
# Similar use to a pie chart, with a central space.
#
# Question:
# What share of transactions is successful, failed or pending?
# ============================================================

status_counts = (
    df["transaction_status"]
      .value_counts()
      .reindex(STATUS_ORDER)
)

plt.figure(figsize=(7, 7))

plt.pie(
    status_counts.values,
    labels=status_counts.index,
    autopct="%1.1f%%",
    startangle=90,
    wedgeprops={"width": 0.4},
    colors=[GREEN, RED, ORANGE]
)

plt.title("7. Doughnut Chart: Transaction Outcome Composition")

finish_chart("07_doughnut_chart.png")


# ============================================================
# CHART 8: DOT PLOT
# ============================================================
# Best for:
# Comparing values across categories with less visual ink
# than a traditional bar chart.
#
# Question:
# How do customer segments compare in average payment value?
# ============================================================

segment_value = (
    df.groupby("customer_segment")["transaction_value_bnd"]
      .mean()
      .sort_values()
)

plt.figure(figsize=(8, 5))

y = np.arange(len(segment_value))

plt.scatter(
    segment_value.values,
    y,
    color=BLUE,
    s=70
)

plt.yticks(y, segment_value.index)
plt.title("8. Dot Plot: Average Payment Value by Segment")
plt.xlabel("Average value (BND)")
plt.ylabel("Customer segment")
plt.grid(axis="x", alpha=0.3)

finish_chart("08_dot_plot.png")


# ============================================================
# CHART 9: LOLLIPOP CHART
# ============================================================
# Best for:
# Comparing categorical values with a lighter visual style.
#
# Question:
# How do customer segments compare in adoption tenure?
# ============================================================

segment_tenure = (
    df.groupby("customer_segment")["adoption_tenure_months"]
      .mean()
      .sort_values()
)

plt.figure(figsize=(8, 5))

y = np.arange(len(segment_tenure))

plt.hlines(
    y=y,
    xmin=0,
    xmax=segment_tenure.values,
    color=GREEN
)

plt.plot(
    segment_tenure.values,
    y,
    "o",
    color=GREEN
)

plt.yticks(y, segment_tenure.index)
plt.xlim(0, 60)

plt.title("9. Lollipop Chart: Adoption Tenure by Segment")
plt.xlabel("Average adoption tenure (months)")
plt.ylabel("Customer segment")

finish_chart("09_lollipop_chart.png")


# ============================================================
# CHART 10: HISTOGRAM
# ============================================================
# Best for:
# Showing the distribution of one continuous numerical variable.
#
# Question:
# How are transaction values distributed?
# ============================================================

plt.figure(figsize=(8, 5))

plt.hist(
    df["transaction_value_bnd"],
    bins=30,
    edgecolor="black",
    color=BLUE
)

plt.title("10. Histogram: Distribution of Transaction Value")
plt.xlabel("Transaction value (BND)")
plt.ylabel("Frequency")

finish_chart("10_histogram.png")


# ============================================================
# CHART 11: BOX PLOT
# ============================================================
# Best for:
# Summarising distribution, median, spread and possible outliers.
#
# Question:
# How does transaction value differ across merchant categories?
# ============================================================

categories = df["merchant_category"].unique()

box_data = [
    df.loc[df["merchant_category"] == category, "transaction_value_bnd"]
    for category in categories
]

plt.figure(figsize=(10, 5))

plt.boxplot(
    box_data,
    tick_labels=categories
)

plt.title("11. Box Plot: Transaction Value by Merchant Category")
plt.xlabel("Merchant category")
plt.ylabel("Value (BND)")
plt.xticks(rotation=35, ha="right")

finish_chart("11_box_plot.png")


# ============================================================
# CHART 12: SCATTER PLOT
# ============================================================
# Best for:
# Examining the relationship between two numerical variables.
#
# Question:
# Is income band related to payment value?
# ============================================================

plt.figure(figsize=(8, 5))

plt.scatter(
    df["monthly_income_bnd"],
    df["transaction_value_bnd"],
    alpha=0.25,
    s=14,
    color=BLUE
)

plt.title("12. Scatter Plot: Income Band vs Payment Value")
plt.xlabel("Monthly income (BND)")
plt.ylabel("Transaction value (BND)")
plt.grid(alpha=0.3)

finish_chart("12_scatter_plot.png")


# ============================================================
# CHART 13: BUBBLE CHART
# ============================================================
# Best for:
# Showing the relationship between two numerical variables
# while using bubble size for a third variable.
#
# Question:
# How do income, payment value and adoption tenure interact?
# ============================================================

plt.figure(figsize=(8, 5))

plt.scatter(
    df["monthly_income_bnd"],
    df["transaction_value_bnd"],
    s=df["adoption_tenure_months"] * 3,
    alpha=0.4,
    color=ORANGE
)

plt.title("13. Bubble Chart: Income, Value and Adoption Tenure")
plt.xlabel("Monthly income (BND)")
plt.ylabel("Transaction value (BND)")
plt.grid(alpha=0.3)

finish_chart("13_bubble_chart.png")


# ============================================================
# CHART 14: HEATMAP
# ============================================================
# Best for:
# Showing intensity or patterns across a matrix.
#
# Question:
# How does average payment value vary by segment and channel?
#
# Note:
# This example uses matplotlib directly, not seaborn.
# ============================================================

heatmap_data = (
    df.pivot_table(
        index="customer_segment",
        columns="payment_channel",
        values="transaction_value_bnd",
        aggfunc="mean"
    )
    .reindex(index=SEGMENT_ORDER, columns=CHANNEL_ORDER)
)

plt.figure(figsize=(10, 5))

plt.imshow(
    heatmap_data.values,
    aspect="auto",
    cmap="Blues"
)

plt.colorbar(label="Average value (BND)")

plt.xticks(
    range(len(heatmap_data.columns)),
    heatmap_data.columns,
    rotation=35,
    ha="right"
)

plt.yticks(
    range(len(heatmap_data.index)),
    heatmap_data.index
)

# Add values inside cells.
for i in range(len(heatmap_data.index)):
    for j in range(len(heatmap_data.columns)):
        plt.text(
            j,
            i,
            f"{heatmap_data.iloc[i, j]:.0f}",
            ha="center",
            va="center",
            fontsize=8
        )

plt.title("14. Heatmap: Average Value by Segment and Channel")
plt.xlabel("Payment channel")
plt.ylabel("Customer segment")

finish_chart("14_heatmap.png")


# ============================================================
# CHART 15: TABLE
# ============================================================
# Best for:
# Presenting exact values when precision is more important
# than showing patterns.
#
# Question:
# What are the exact average values, incomes and tenure
# figures for each customer segment?
# ============================================================

summary_table = (
    df.groupby("customer_segment")
      .agg(
          Transactions=("transaction_id", "size"),
          Average_Value=("transaction_value_bnd", "mean"),
          Average_Income=("monthly_income_bnd", "mean"),
          Average_Tenure=("adoption_tenure_months", "mean")
      )
      .round(1)
      .reset_index()
)

plt.figure(figsize=(10, 4))
plt.axis("off")

table = plt.table(
    cellText=summary_table.values,
    colLabels=summary_table.columns,
    loc="center",
    cellLoc="center"
)

table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 1.7)

plt.title("15. Table: Exact Segment Summary Values")

finish_chart("15_table.png")


# ============================================================
# INTERACTIVE VIEWER: LEFT / RIGHT BUTTONS
# ============================================================
# Best for:
# Browsing several charts in one window instead of closing each
# chart window with the X button.
#
# Question:
# How can I move between charts without closing the current one?
# ============================================================

def show_chart_gallery():
    """Display the saved charts in one window with previous/next buttons."""
    images = [plt.imread(OUTPUT_DIR / name) for name in CHART_FILES]

    current_index = 0
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.subplots_adjust(bottom=0.14)

    if fig.canvas.manager is not None:
        fig.canvas.manager.set_window_title("EDA chart gallery")

    status = fig.text(0.5, 0.02, "", ha="center", fontsize=10)

    def draw_current():
        ax.clear()
        ax.imshow(images[current_index])
        ax.axis("off")
        status.set_text(
            f"{current_index + 1} / {len(images)} - "
            f"{CHART_TITLES[current_index]}"
        )
        fig.canvas.draw_idle()

    def go_previous(_event=None):
        nonlocal current_index
        current_index = (current_index - 1) % len(images)
        draw_current()

    def go_next(_event=None):
        nonlocal current_index
        current_index = (current_index + 1) % len(images)
        draw_current()

    def on_key(event):
        if event.key in ("left", "arrowleft"):
            go_previous()
        elif event.key in ("right", "arrowright"):
            go_next()

    previous_axis = fig.add_axes([0.36, 0.04, 0.12, 0.06])
    next_axis = fig.add_axes([0.52, 0.04, 0.12, 0.06])

    button_previous = Button(previous_axis, "< Previous")
    button_next = Button(next_axis, "Next >")
    button_previous.on_clicked(go_previous)
    button_next.on_clicked(go_next)

    fig.canvas.mpl_connect("key_press_event", on_key)
    draw_current()
    plt.show()


# ============================================================
# CHART-SELECTION SUMMARY
# ============================================================

print()
print("==================================================")
print("CHART-SELECTION SUMMARY")
print("==================================================")

print("""
Analytical Question              Suitable Chart
------------------------------------------------------------
Compare categories               Bar chart
Compare subcategories            Grouped bar chart
Show composition by category     Stacked bar chart
Show change over time            Line chart
Show magnitude over time         Area chart
Show simple part-to-whole        Pie / doughnut chart
Compare values simply            Dot / lollipop chart
Show numerical distribution      Histogram
Summarise spread and outliers    Box plot
Show relationship                Scatter plot
Add a third numerical variable   Bubble chart
Show matrix patterns             Heatmap
Show exact values                Table
""")

print("Chart-selection principles:")
print("1. Start with the question.")
print("2. Identify the data type.")
print("3. Match the chart to the analytical task.")
print("4. Keep the visual simple and readable.")
print("5. Avoid misleading design.")
print("6. Prefer clarity over decoration.")

print()
print("All fundamental chart examples have been generated.")
print("Output folder:")
print(OUTPUT_DIR.resolve())

print()
print("Use < Previous / Next > or the left/right arrow keys in the")
print("gallery window to change charts. Close that window when finished.")
print()

show_chart_gallery()
