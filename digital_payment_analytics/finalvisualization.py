"""
Final visualisation — the whole project in one Streamlit app.
=============================================================

Combines the interactive Stage 6 dashboard (``streamlit_dashboard.py``) with
the Stage 3 exploratory data analysis (``eda_analysis.py``). One set of shared
sidebar filters applies to every page: the dashboard charts and the EDA
figures are rebuilt from the current selection instead of reading static PNGs.

Pages
-----
* About         — project background, dataset and reading notes.
* GitHub        — QR code for the project repository.
* Overview      — KPI row and the six question-led dashboard charts.
* Data & SQL    — filtered records plus an in-memory SQL console.
* Distributions — univariate EDA figures (value, categories, time, customer).
* Relationships — bivariate EDA figures (category, segment, adoption, income,
                  geography).
* Multivariate  — correlation matrix and outlier inspection.
* Statistics    — descriptive tables and a downloadable summary.

Run::

    python -m streamlit run finalvisualization.py
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

import altair as alt
import matplotlib

matplotlib.use("Agg")  # headless rendering

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

st.set_page_config(
    page_title="Digital payment analytics",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GITHUB_QR_PATH = os.path.join(BASE_DIR, "assets", "github_qr.svg")

DIGITAL_RAILS = ["Mobile Wallet", "QR Payment"]
STATUS_ORDER = ["Successful", "Failed", "Pending"]
SEGMENT_ORDER = [
    "Tech Savvy", "Young Professionals", "Working Adults",
    "Traditional Users", "Senior Citizens",
]
CHANNEL_ORDER = [
    "Mobile Wallet", "QR Payment", "Debit Card",
    "Credit Card", "Online Banking", "Bank Transfer",
]
ADOPTION_ORDER = ["Low", "Medium", "High"]
URBANITY_ORDER = ["Urban", "Suburban", "Rural"]
DAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday",
]

BLUE = "#4C72B0"
ORANGE = "#DD8452"
GREEN = "#55A868"
RED = "#C44E52"
PURPLE = "#8172B3"
GREY = "#8C8C8C"
PALETTE = [BLUE, ORANGE, GREEN, RED, PURPLE, GREY]
CHANNEL_COLORS = dict(zip(CHANNEL_ORDER, PALETTE))
STATUS_COLORS = {"Successful": GREEN, "Failed": RED, "Pending": ORANGE}
ADOPTION_COLORS = dict(zip(ADOPTION_ORDER, [RED, ORANGE, GREEN]))

NUMERIC_COLS = [
    "transaction_value_bnd", "transaction_hour", "adoption_tenure_months",
    "age", "monthly_income_bnd", "latitude", "longitude", "cross_border_flag",
]
CATEGORICAL_COLS = [
    "payment_channel", "merchant_category", "transaction_status",
    "device_type", "customer_segment", "adoption_level",
    "digital_payment_frequency", "is_cross_border", "district",
    "urbanity", "day_of_week",
]
GROUP_COLS = [
    "merchant_category", "payment_channel", "customer_segment",
    "adoption_level", "urbanity", "transaction_status", "district",
]
FILTER_KEYS = ("f_channels", "f_segments", "f_districts", "f_statuses")

sns.set_theme(style="whitegrid", context="notebook", palette="deep")


# ---------------------------------------------------------------------------
# Cached data loading (filters are applied afterwards, outside the cache)
# ---------------------------------------------------------------------------

@st.cache_data(ttl="1h", show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read and join the Stage 2 tables into one analysis frame."""
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
    return df, locations, customers


def numeric_stats(df: pd.DataFrame) -> dict:
    """Values used by both the EDA figures and the statistics page."""
    values = df["transaction_value_bnd"]
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    return {
        "values": values,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower_fence": q1 - 1.5 * iqr,
        "upper_fence": q3 + 1.5 * iqr,
        "corr": df[NUMERIC_COLS].corr(),
        "pearson": df["monthly_income_bnd"].corr(values),
        "spearman": df["monthly_income_bnd"].corr(values, method="spearman"),
    }


# ---------------------------------------------------------------------------
# Shared UI helpers
# ---------------------------------------------------------------------------

def horizontal_bars(
    source: pd.DataFrame,
    category_col: str,
    value_col: str,
    x_title: str,
    tooltips: list[alt.Tooltip],
    *,
    color: str = BLUE,
    x_domain: tuple[float, float] | None = None,
) -> alt.Chart:
    """Sorted horizontal bar chart with one bar per category."""
    x = alt.X(f"{value_col}:Q", title=x_title)
    if x_domain is not None:
        x = x.scale(domain=list(x_domain))
    return (
        alt.Chart(source)
        .mark_bar(color=color, cornerRadiusEnd=3)
        .encode(
            x=x,
            y=alt.Y(f"{category_col}:N", title=None, sort="-x",
                    axis=alt.Axis(labelLimit=170)),
            tooltip=tooltips,
        )
        .properties(height=max(190, 27 * source[category_col].nunique()))
    )


def pills_filter(label: str, options: list[str], key: str) -> list[str]:
    """Visible, individually clickable options with All / Clear shortcuts."""
    def select_all() -> None:
        st.session_state[key] = list(options)

    def clear_all() -> None:
        st.session_state[key] = []

    selected = st.pills(label, options, selection_mode="multi", key=key, wrap=True)
    with st.container(horizontal=True):
        st.button("All", key=f"{key}_all", icon=":material/done_all:",
                  on_click=select_all)
        st.button("Clear", key=f"{key}_clear", icon=":material/close:",
                  on_click=clear_all)
    return selected


def reset_filters() -> None:
    st.session_state.pop("f_dates", None)
    for key in FILTER_KEYS:
        st.session_state[key] = list(
            st.session_state.get("_filter_options", {}).get(key, [])
        )


def apply_filters(df: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    """Render the shared sidebar filters and return the filtered frame."""
    min_date = df["transaction_date"].min().date()
    max_date = df["transaction_date"].max().date()
    channels_all = sorted(df["payment_channel"].dropna().unique())
    segments_all = sorted(df["customer_segment"].dropna().unique())
    districts_all = sorted(locations["district"].dropna().unique())
    statuses_all = [s for s in STATUS_ORDER if s in set(df["transaction_status"])]

    options_by_key = {
        "f_channels": channels_all,
        "f_segments": segments_all,
        "f_districts": districts_all,
        "f_statuses": statuses_all,
    }
    st.session_state["_filter_options"] = options_by_key
    for key, options in options_by_key.items():
        st.session_state.setdefault(key, list(options))

    with st.sidebar:
        st.header("Filters")
        st.caption("Click individual values to toggle them, or use All / Clear.")
        st.button("Reset filters", icon=":material/restart_alt:", on_click=reset_filters)

        dates = st.date_input(
            "Transaction date",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="f_dates",
        )
        selected_channels = pills_filter("Payment channel", channels_all, "f_channels")
        selected_segments = pills_filter("Customer segment", segments_all, "f_segments")
        selected_districts = pills_filter("District", districts_all, "f_districts")
        selected_statuses = pills_filter("Transaction status", statuses_all, "f_statuses")

        st.divider()
        with st.expander("About this data"):
            st.markdown(
                "5,000 synthetic 2025 transactions joined to customer and "
                "location dimensions. All figures are **descriptive**: the "
                "generator programmed the segment/channel and category/value "
                "patterns rediscovered here, so nothing implies causation."
            )

    start_date, end_date = (
        dates if isinstance(dates, tuple) and len(dates) == 2 else (dates, dates)
    )

    if not all([selected_channels, selected_segments, selected_districts, selected_statuses]):
        st.info("Select at least one option in every filter to draw the charts.")
        st.stop()

    filtered = df.loc[
        df["transaction_date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & df["payment_channel"].isin(selected_channels)
        & df["customer_segment"].isin(selected_segments)
        & df["district"].isin(selected_districts)
        & df["transaction_status"].isin(selected_statuses)
    ].copy()

    if filtered.empty:
        st.warning("No transactions match the current filters. Widen the selection or reset.")
        st.stop()
    return filtered


# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------

def page_about() -> None:
    st.title("About")
    st.caption(
        "Background, data and guidance for this interactive analytics app."
    )

    with st.container(border=True):
        st.subheader("Digital payment analytics · Brunei 2025")
        st.markdown(
            "This app brings the Stage 6 question-led dashboard together with "
            "the Stage 3 exploratory analysis. All pages share one set of "
            "sidebar filters: charts, tables and SQL results are rebuilt from "
            "the selected rows instead of reading static PNG files."
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Transactions", f"{len(all_data):,}", border=True)
        with c2:
            st.metric("Customers", f"{len(customers_all):,}", border=True)
        with c3:
            st.metric("Locations", f"{len(locations):,}", border=True)
        with c4:
            st.metric(
                "Merchant categories",
                f"{all_data['merchant_category'].nunique()}",
                border=True,
            )

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Dataset")
            st.markdown(
                "- **Grain:** one synthetic payment attempt per row.\n"
                "- **Period:** 1 Jan – 31 Dec 2025; currency: BND throughout.\n"
                "- **Dimensions:** 300 customers and 100 locations joined to "
                "the transaction fact table.\n"
                "- **Lookups:** 6 payment channels and 10 merchant categories.\n"
                "- **Quality:** no missing values, no duplicate IDs and all "
                "foreign keys resolve.\n"
                "- **Privacy:** no real people, accounts or card details."
            )
    with right:
        with st.container(border=True):
            st.subheader("Project pipeline")
            st.markdown(
                "| Stage | Contribution |\n"
                "| --- | --- |\n"
                "| 2 · Data design | Deterministic synthetic CSVs (seed 42). |\n"
                "| 3 · EDA | Distributions, relationships, correlations and "
                "outliers. |\n"
                "| 4 · MongoDB | Document-store aggregations. |\n"
                "| 5 · Spark | Distributed answers to the six questions. |\n"
                "| 6 · Visualisation | Six question-led charts and "
                "interpretation. |\n"
                "| Final app | This interactive Streamlit view. |"
            )

    with st.container(border=True):
        st.subheader("Where to look")
        st.markdown(
            "- **Overview** — KPIs and the six question-led dashboard charts.\n"
            "- **Data & SQL** — inspect filtered rows and run `SELECT` queries "
            "against an in-memory SQLite table.\n"
            "- **Distributions / Relationships / Multivariate** — the EDA "
            "figures, all driven by the current filters.\n"
            "- **Statistics** — descriptive tables, crosstabs, correlations, "
            "outlier checks and a downloadable summary."
        )

    with st.container(border=True):
        st.subheader("How to read the results")
        st.markdown(
            "Every figure is **descriptive**. The generator deliberately built "
            "in the segment–channel gradient, category value ranges and income "
            "scaling, so rediscovering them is not evidence of real-world "
            "causation. Small success-rate differences are compatible with "
            "sampling variation, and high-value payments are an expected "
            "right tail rather than automatic errors."
        )

    with st.expander("Technical notes and reproduction", icon=":material/code:"):
        st.markdown(
            "Built with Streamlit, pandas, Altair, Matplotlib and Seaborn. "
            "Source CSVs are cached for one hour; filters are applied on each "
            "rerun. The SQL console uses Python's built-in `sqlite3` module.\n\n"
            "Run locally with:"
        )
        st.code(
            "python -m streamlit run finalvisualization.py", language="powershell"
        )
        st.caption(
            "Detailed write-ups are in the `md/` folder; generated outputs are "
            "in `eda_outputs/`, `mongodb_outputs/`, `spark_outputs/` and "
            "`dashboard_outputs/`."
        )


# ---------------------------------------------------------------------------
# GitHub page
# ---------------------------------------------------------------------------

def page_github() -> None:
    st.title("GitHub")
    st.caption("Source code for the Digital Payment Analytics project.")

    left, right = st.columns([1, 2])
    with left:
        with st.container(border=True, horizontal_alignment="center"):
            st.image(
                GITHUB_QR_PATH,
                width=280,
                alt="QR code linking to the project's GitHub repository",
            )
            st.caption("Scan to open the repository on another device.")
    with right:
        with st.container(border=True):
            st.subheader("Project repository")
            st.markdown(
                "The GitHub repository holds the complete project: the "
                "synthetic data generator, Stage 3–6 scripts, this Streamlit "
                "app, and the reports in `md/`."
            )
            st.markdown(
                "- **Data:** `data/*.csv` — 5,000 transactions, 300 customers "
                "and 100 locations.\n"
                "- **Analysis:** `eda_analysis.py`, `mongodb.py`, `spark.py` "
                "and the visualisation scripts.\n"
                "- **App:** `finalvisualization.py` — the interactive view "
                "you are using now.\n"
                "- **Reports:** stage write-ups and output inventories in "
                "`md/`."
            )
        with st.container(border=True):
            st.subheader("Run it locally")
            st.code(
                "python -m streamlit run finalvisualization.py",
                language="powershell",
            )
            st.caption(
                "The repository also documents how to regenerate the CSVs "
                "and all saved outputs."
            )


# ---------------------------------------------------------------------------
# Page 1 — Overview (Stage 6 dashboard)
# ---------------------------------------------------------------------------

def page_overview() -> None:
    st.title("Overview")
    st.caption(
        "Interactive view of 2025 Brunei digital-payment transactions. Six "
        "question-led charts, each with an interpretation that follows the filters."
    )

    tx = frame
    n = len(tx)
    success = tx[tx["transaction_status"] == "Successful"].copy()
    success_value = success["transaction_value_bnd"].sum()
    success_rate = len(success) / n * 100
    digital_share = tx["payment_channel"].isin(DIGITAL_RAILS).mean() * 100

    with st.container(horizontal=True):
        st.metric("Transactions", f"{n:,}", border=True)
        st.metric("Successful value", f"{success_value:,.0f} BND", border=True)
        st.metric("Success rate", f"{success_rate:.1f}%", border=True)
        st.metric("Digital-first share", f"{digital_share:.1f}%", border=True)

    st.caption(
        f"Showing {n:,} of {len(all_data):,} transactions "
        f"({start_date:%d %b %Y} – {end_date:%d %b %Y}). "
        "Digital-first = Mobile Wallet + QR Payment."
    )

    left, right = st.columns(2)

    # Q1 — payment channels
    with left:
        with st.container(border=True):
            st.subheader("Q1 · Which payment channels are used most?")
            channel_counts = (
                tx["payment_channel"].value_counts().rename("transactions")
                .rename_axis("payment_channel").reset_index()
            )
            channel_counts["share"] = channel_counts["transactions"] / n * 100
            st.altair_chart(
                horizontal_bars(
                    channel_counts, "payment_channel", "transactions",
                    "Number of transactions",
                    [
                        alt.Tooltip("payment_channel:N", title="Payment channel"),
                        alt.Tooltip("transactions:Q", title="Transactions", format=","),
                        alt.Tooltip("share:Q", title="Share (%)", format=".1f"),
                    ],
                ),
                alt="Transaction counts by payment channel, sorted from most to least used",
            )
            leader = channel_counts.iloc[0]
            st.caption(
                f"**Interpretation:** {leader['payment_channel']} leads with "
                f"{leader['share']:.1f}% of payments; wallet + QR together account "
                f"for {digital_share:.1f}%, so no single rail dominates."
            )

    # Q2 — merchant-category spend
    with right:
        with st.container(border=True):
            st.subheader("Q2 · Which categories generate the most spend?")
            if success.empty:
                st.info("No successful payments in the current selection.")
            else:
                category_spend = (
                    success.groupby("merchant_category")["transaction_value_bnd"]
                    .agg(successful_value="sum", payments="size")
                    .reset_index()
                )
                st.altair_chart(
                    horizontal_bars(
                        category_spend, "merchant_category", "successful_value",
                        "Successful transaction value (BND)",
                        [
                            alt.Tooltip("merchant_category:N", title="Merchant category"),
                            alt.Tooltip("successful_value:Q", title="Value (BND)", format=",.0f"),
                            alt.Tooltip("payments:Q", title="Payments", format=","),
                        ],
                        color=GREEN,
                    ),
                    alt="Successful transaction value by merchant category, highest first",
                )
                top = category_spend.sort_values("successful_value", ascending=False).iloc[0]
                busiest = category_spend.sort_values("payments", ascending=False).iloc[0]
                st.caption(
                    f"**Interpretation:** {top['merchant_category']} drives the most "
                    f"realised spend ({top['successful_value']:,.0f} BND from "
                    f"{int(top['payments']):,} payments), while {busiest['merchant_category']} "
                    "leads by volume — value and frequency are different stories."
                )

    left, right = st.columns(2)

    # Q3 — digital-first segments
    with left:
        with st.container(border=True):
            st.subheader("Q3 · Which segments are digital-first?")
            if success.empty:
                st.info("No successful payments in the current selection.")
            else:
                seg = success.assign(
                    uses_digital=success["payment_channel"].isin(DIGITAL_RAILS).astype(int)
                ).groupby("customer_segment").agg(
                    digital_share=("uses_digital", lambda s: s.mean() * 100),
                    payments=("uses_digital", "size"),
                ).reset_index()
                st.altair_chart(
                    horizontal_bars(
                        seg, "customer_segment", "digital_share",
                        "Wallet + QR share of successful payments (%)",
                        [
                            alt.Tooltip("customer_segment:N", title="Customer segment"),
                            alt.Tooltip("digital_share:Q", title="Digital-first (%)", format=".1f"),
                            alt.Tooltip("payments:Q", title="Payments", format=","),
                        ],
                        color=PURPLE,
                        x_domain=(0, 100),
                    ),
                    alt="Share of successful payments made with wallet or QR by customer segment",
                )
                top_seg = seg.loc[seg["digital_share"].idxmax()]
                low_seg = seg.loc[seg["digital_share"].idxmin()]
                st.caption(
                    f"**Interpretation:** {top_seg['customer_segment']} use wallet/QR for "
                    f"{top_seg['digital_share']:.1f}% of payments versus "
                    f"{low_seg['digital_share']:.1f}% for {low_seg['customer_segment']} — "
                    "a segment gradient, not an income effect."
                )

    # Q4 — outcomes by channel
    with right:
        with st.container(border=True):
            st.subheader("Q4 · Do outcomes differ by payment channel?")
            outcome = (
                pd.crosstab(tx["payment_channel"], tx["transaction_status"],
                            normalize="index")
                .mul(100)
                .reindex(columns=STATUS_ORDER, fill_value=0)
                .sort_values("Successful", ascending=False)
                .reset_index()
            )
            st.bar_chart(
                outcome,
                x="payment_channel",
                y=STATUS_ORDER,
                horizontal=True,
                stack="normalize",
                sort=False,
                height=max(190, 34 * len(outcome)),
                alt="Share of successful, failed and pending payments for each channel",
            )
            best = outcome.iloc[0]
            worst = outcome.iloc[-1]
            st.caption(
                f"**Interpretation:** success spans {worst['Successful']:.1f}–"
                f"{best['Successful']:.1f}% "
                f"({worst['payment_channel']} to {best['payment_channel']}). A spread "
                "this small is consistent with sampling variation, not channel quality."
            )

    left, right = st.columns(2)

    # Q5 — geography
    with left:
        with st.container(border=True):
            st.subheader("Q5 · Where do payments concentrate?")
            district_counts = (
                tx.groupby("district").size().rename("transactions")
                .rename_axis("district").reset_index()
                .sort_values("transactions", ascending=False)
            )
            district_counts["share"] = district_counts["transactions"] / n * 100
            st.altair_chart(
                horizontal_bars(
                    district_counts, "district", "transactions",
                    "Number of transactions",
                    [
                        alt.Tooltip("district:N", title="District"),
                        alt.Tooltip("transactions:Q", title="Transactions", format=","),
                        alt.Tooltip("share:Q", title="Share (%)", format=".1f"),
                    ],
                    color=ORANGE,
                ),
                alt="Transaction counts by district, showing where payment volume concentrates",
            )
            top_district = district_counts.iloc[0]
            urban_means = tx.groupby("urbanity")["transaction_value_bnd"].mean().sort_values()
            means_text = " | ".join(f"{k} {v:.0f} BND" for k, v in urban_means.items())
            st.caption(
                f"**Interpretation:** {top_district['district']} accounts for "
                f"{top_district['share']:.1f}% of payments, yet mean values by urbanity "
                f"are close ({means_text}): volume is concentrated, amounts are not."
            )

    # Q6 — value distribution and outliers
    with right:
        with st.container(border=True):
            st.subheader("Q6 · Are there extreme payment values?")
            fence = stats["upper_fence"]
            median = stats["values"].median()
            histogram = (
                alt.Chart(tx)
                .mark_bar(color=BLUE, opacity=0.85)
                .encode(
                    x=alt.X("transaction_value_bnd:Q", bin=alt.Bin(maxbins=45),
                            title="Transaction value (BND)"),
                    y=alt.Y("count():Q", title="Number of transactions"),
                )
            )
            lines = (
                alt.Chart(pd.DataFrame({
                    "value": [median, fence],
                    "label": ["Median", "Tukey fence"],
                }))
                .mark_rule(strokeWidth=2, strokeDash=[5, 3])
                .encode(
                    x="value:Q",
                    color=alt.Color("label:N", title=None,
                                    scale=alt.Scale(domain=["Median", "Tukey fence"],
                                                    range=[GREEN, RED])),
                )
            )
            st.altair_chart(
                alt.layer(histogram, lines).properties(height=270),
                alt="Histogram of transaction values with median and Tukey upper fence",
            )
            outliers = tx[tx["transaction_value_bnd"] > fence]
            if outliers.empty:
                detail = "none exceed the Tukey fence"
            else:
                top_cat = outliers["merchant_category"].value_counts()
                detail = f"{int(top_cat.max())} of them are {top_cat.idxmax()}"
            st.caption(
                f"**Interpretation:** {len(outliers):,} payments "
                f"({len(outliers) / n * 100:.1f}%) exceed {fence:,.2f} BND and {detail} "
                "— an expected tail from high-ticket categories, not necessarily errors."
            )


# ---------------------------------------------------------------------------
# Page 2 — Filtered data and SQL console (Stage 6 dashboard)
# ---------------------------------------------------------------------------

EXAMPLE_QUERIES = {
    "Channel volume": (
        "SELECT payment_channel, COUNT(*) AS transactions,\n"
        "       ROUND(100.0 * COUNT(*) /\n"
        "             (SELECT COUNT(*) FROM transactions), 1) AS share_pct\n"
        "FROM transactions\n"
        "GROUP BY payment_channel\n"
        "ORDER BY transactions DESC;"
    ),
    "Spend by category": (
        "SELECT merchant_category, COUNT(*) AS payments,\n"
        "       ROUND(SUM(transaction_value_bnd), 2) AS total_bnd\n"
        "FROM transactions\n"
        "WHERE transaction_status = 'Successful'\n"
        "GROUP BY merchant_category\n"
        "ORDER BY total_bnd DESC;"
    ),
    "High-value payments": (
        "SELECT transaction_date, payment_channel, merchant_category,\n"
        "       district, transaction_value_bnd\n"
        "FROM transactions\n"
        "WHERE transaction_value_bnd >= 500\n"
        "ORDER BY transaction_value_bnd DESC\n"
        "LIMIT 25;"
    ),
    "Digital-first by segment": (
        "SELECT customer_segment,\n"
        "       ROUND(AVG(CASE WHEN payment_channel IN\n"
        "                  ('Mobile Wallet', 'QR Payment')\n"
        "                  THEN 1.0 ELSE 0 END) * 100, 1) AS digital_pct\n"
        "FROM transactions\n"
        "GROUP BY customer_segment\n"
        "ORDER BY digital_pct DESC;"
    ),
}


def use_example() -> None:
    choice = st.session_state.get("sql_example")
    if choice:
        st.session_state["sql_query"] = EXAMPLE_QUERIES[choice]


def page_data_sql() -> None:
    st.title("Data & SQL")
    st.caption(
        "Inspect the filtered rows, or query them with SQL using Python's "
        "built-in SQLite engine — no extra dependency required."
    )

    view = frame[[
        "transaction_date", "payment_channel", "merchant_category",
        "transaction_value_bnd", "transaction_status", "customer_segment",
        "district", "urbanity", "device_type",
    ]]

    with st.expander("Filtered transaction data", icon=":material/table:"):
        st.dataframe(
            view,
            hide_index=True,
            column_config={
                "transaction_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                "transaction_value_bnd": st.column_config.NumberColumn("Value (BND)", format="%.2f"),
            },
            alt="Filtered transaction records",
        )
        st.download_button(
            "Download filtered CSV",
            data=view.to_csv(index=False).encode("utf-8"),
            file_name="filtered_transactions.csv",
            mime="text/csv",
            icon=":material/download:",
        )

    st.divider()
    with st.container(border=True):
        st.subheader("Query the data with SQL")
        st.caption(
            "Run a SELECT query against the filtered `transactions` table. "
            "Columns: transaction_date, payment_channel, merchant_category, "
            "transaction_value_bnd, transaction_status, customer_segment, "
            "district, urbanity, device_type."
        )
        st.pills(
            "Example queries", list(EXAMPLE_QUERIES), selection_mode="single",
            key="sql_example", on_change=use_example, wrap=True,
        )
        query = st.text_area("SQL query", height=170, key="sql_query")

        if st.button("Run query", type="primary", icon=":material/play_arrow:"):
            statement = query.strip().rstrip(";")
            if not statement:
                st.warning("Enter a SQL query first.")
            elif not statement.lower().startswith(("select", "with")):
                st.error("Only SELECT queries are supported.")
            else:
                connection = sqlite3.connect(":memory:")
                try:
                    view.to_sql("transactions", connection, index=False)
                    result = pd.read_sql_query(statement, connection)
                    st.caption(f"Returned {len(result):,} row(s).")
                    st.dataframe(
                        result, hide_index=True,
                        alt="Results of the SQL query against filtered transactions",
                    )
                    st.download_button(
                        "Download query results",
                        data=result.to_csv(index=False).encode("utf-8"),
                        file_name="query_results.csv",
                        mime="text/csv",
                        icon=":material/download:",
                    )
                except Exception as exc:
                    st.error(f"Query failed: {exc}")
                finally:
                    connection.close()


# ---------------------------------------------------------------------------
# EDA figure builders (Stage 3), now driven by the filtered frame
# ---------------------------------------------------------------------------

def annotate_bars(ax, fmt: str = "{:.0f}", offset: int = 3) -> None:
    """Attach value labels to every non-empty bar container on an axis."""
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
                ha="center", va="bottom", fontsize=8,
            )


def fig_value_distribution(df: pd.DataFrame, s: dict):
    values = s["values"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    sns.histplot(values, bins=50, color=BLUE, edgecolor="white", ax=axes[0])
    axes[0].axvline(values.mean(), color=RED, linestyle="--",
                    label=f"Mean = {values.mean():.2f}")
    axes[0].axvline(values.median(), color=GREEN, linestyle="--",
                    label=f"Median = {values.median():.2f}")
    axes[0].set(title="Transaction value distribution", xlabel="Value (BND)",
                ylabel="Number of transactions")
    axes[0].legend()
    sns.boxplot(x=values, color=BLUE, width=0.6, fliersize=4,
                medianprops=dict(color=RED, linewidth=1.5), ax=axes[1])
    axes[1].set(title="Transaction value boxplot (right-skewed)",
                xlabel="Value (BND)", yticks=[])
    sns.despine(ax=axes[1], left=True)
    fig.suptitle("Univariate: transaction value", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def fig_categorical_counts(df: pd.DataFrame, s: dict):
    cols = [
        "payment_channel", "merchant_category", "transaction_status",
        "device_type", "customer_segment", "adoption_level",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, col in zip(axes.flat, cols):
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
    fig.suptitle("Univariate: categorical profiles", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def fig_temporal_patterns(df: pd.DataFrame, s: dict):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.2))
    sns.countplot(data=df, x="transaction_hour", color=BLUE, ax=axes[0])
    axes[0].set(title="By hour of day", xlabel="Hour", ylabel="Transactions")
    axes[0].set_xticks(range(0, 24, 2))

    sns.countplot(data=df, x="day_of_week", order=DAY_ORDER, color=GREEN, ax=axes[1])
    axes[1].set_xticks(range(len(DAY_ORDER)), [d[:3] for d in DAY_ORDER])
    axes[1].set(title="By day of week", xlabel="", ylabel="Transactions")

    month_counts = df.groupby("month").size()
    sns.lineplot(x=month_counts.index, y=month_counts.values, marker="o",
                 color=ORANGE, linewidth=2, ax=axes[2])
    axes[2].set(title="By calendar month (2025)", xlabel="Month", ylabel="Transactions")
    axes[2].set_xticks(range(1, 13))
    fig.suptitle("Univariate: when payments occur", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def fig_customer_profile(df: pd.DataFrame, s: dict):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    sns.histplot(df["age"], bins=20, color=BLUE, edgecolor="white", ax=axes[0, 0])
    axes[0, 0].set(title="Customer age (per transaction)", xlabel="Age",
                   ylabel="Transactions")

    income_order = sorted(df["monthly_income_bnd"].unique())
    sns.countplot(data=df, x="monthly_income_bnd", order=income_order,
                  color=PURPLE, ax=axes[0, 1])
    axes[0, 1].set(title="Monthly income band (BND)", xlabel="Income band",
                   ylabel="Transactions")
    axes[0, 1].tick_params(axis="x", rotation=45)

    sns.histplot(df["adoption_tenure_months"], bins=20, color=GREEN,
                 edgecolor="white", ax=axes[1, 0])
    axes[1, 0].set(title="Adoption tenure", xlabel="Months", ylabel="Transactions")

    sns.countplot(data=df, x="digital_payment_frequency", color=ORANGE, ax=axes[1, 1])
    axes[1, 1].set(title="Self-reported digital frequency", xlabel="Frequency",
                   ylabel="Transactions")
    fig.suptitle("Univariate: customer profile attached to each payment",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def fig_value_by_category(df: pd.DataFrame, s: dict):
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
    return fig


def fig_segment_channel_heatmap(df: pd.DataFrame, s: dict):
    ct = pd.crosstab(df["customer_segment"], df["payment_channel"]) \
           .reindex(index=SEGMENT_ORDER, columns=CHANNEL_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(ct, annot=True, fmt=",d", cmap="Blues", linewidths=0.5,
                annot_kws={"fontsize": 9},
                cbar_kws={"label": "Number of transactions"}, ax=ax)
    ax.set(title="Segment x payment channel (counts)",
           xlabel="Payment channel", ylabel="Customer segment")
    fig.tight_layout()
    return fig


def fig_adoption_tenure_value(df: pd.DataFrame, s: dict):
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
    fig.suptitle("Bivariate: adoption, tenure and value", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def fig_status_by_channel(df: pd.DataFrame, s: dict):
    status_ct = pd.crosstab(df["payment_channel"], df["transaction_status"],
                            normalize="index").mul(100) \
                  .reindex(index=CHANNEL_ORDER, fill_value=0)
    status_ct = status_ct[[c for c in STATUS_ORDER if c in status_ct.columns]]
    ax = status_ct.plot(
        kind="barh", stacked=True, figsize=(10, 5),
        color=[STATUS_COLORS[c] for c in status_ct.columns], width=0.75,
    )
    ax.set(title="Transaction outcome mix by channel",
           xlabel="Share of channel transactions (%)", ylabel="")
    ax.legend(title="Status", loc="lower right")
    for container in ax.containers:
        for bar in container:
            width = bar.get_width()
            if width > 1.5:
                ax.annotate(
                    f"{width:.1f}",
                    (bar.get_x() + width / 2, bar.get_y() + bar.get_height() / 2),
                    ha="center", va="center", fontsize=8, color="white",
                )
    fig = ax.get_figure()
    fig.tight_layout()
    return fig


def fig_income_vs_value(df: pd.DataFrame, s: dict):
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.stripplot(data=df, x="monthly_income_bnd", y="transaction_value_bnd",
                  hue="adoption_level", hue_order=ADOPTION_ORDER,
                  palette=ADOPTION_COLORS, jitter=0.25, alpha=0.25, size=3, ax=ax)
    ax.set(title=f"Income band vs value (r={s['pearson']:.3f}, "
                 f"rho={s['spearman']:.3f})",
           xlabel="Monthly income band (BND)", ylabel="Transaction value (BND)")
    sns.move_legend(ax, "upper left", title=None, markerscale=1.5)
    fig.tight_layout()
    return fig


def fig_geography(df: pd.DataFrame, s: dict):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    district_counts = df["district"].value_counts()
    sns.countplot(data=df, x="district", order=district_counts.index,
                  color=BLUE, ax=axes[0])
    axes[0].set(title="Transactions by district", xlabel="", ylabel="Transactions")
    annotate_bars(axes[0])

    urbanity_means = df.groupby("urbanity")["transaction_value_bnd"].mean() \
                        .reindex(URBANITY_ORDER)
    sns.barplot(x=urbanity_means.index, y=urbanity_means.values,
                color=GREEN, ax=axes[1])
    axes[1].set(title="Mean value by urbanity", xlabel="", ylabel="Mean value (BND)")
    annotate_bars(axes[1], fmt="{:.2f}")
    fig.suptitle("Bivariate: where payments occur", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def fig_correlation_heatmap(df: pd.DataFrame, s: dict):
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(s["corr"], annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                vmin=-1, vmax=1, square=True, linewidths=0.5,
                annot_kws={"fontsize": 8},
                xticklabels=[c.replace("_", "\n") for c in NUMERIC_COLS],
                yticklabels=[c.replace("_", " ") for c in NUMERIC_COLS],
                cbar_kws={"label": "Pearson r", "shrink": 0.8}, ax=ax)
    ax.set(title="Numeric correlation matrix", xlabel="", ylabel="")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def fig_multivariate_outliers(df: pd.DataFrame, s: dict):
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
    fig.suptitle("Multivariate view and outlier inspection", fontsize=13,
                 fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Pages 3–5 — EDA figure gallery
# ---------------------------------------------------------------------------

# Display widths (px) for the per-figure zoom buttons. Streamlit caps a width
# at the parent container, so "zoom in" grows up to the available page width.
ZOOM_LEVELS = [("60%", 560), ("80%", 740), ("100%", 920), ("125%", 1150), ("150%", 1380)]
DEFAULT_ZOOM_INDEX = 2


def change_zoom(key: str, delta: int) -> None:
    """Move one figure's zoom up or down by a single step."""
    current = st.session_state.get(key, DEFAULT_ZOOM_INDEX)
    st.session_state[key] = max(0, min(len(ZOOM_LEVELS) - 1, current + delta))


def reset_zoom(key: str) -> None:
    st.session_state[key] = DEFAULT_ZOOM_INDEX


def render_figures(items: list[tuple[str, object, str]]) -> None:
    """Render each (title, builder, accessible name) in its own zoomable card."""
    for title, builder, alt_text in items:
        key = f"zoom_{builder.__name__}"
        level = st.session_state.get(key, DEFAULT_ZOOM_INDEX)
        label, width = ZOOM_LEVELS[level]
        with st.container(border=True):
            st.subheader(title)
            with st.container(horizontal=True, horizontal_alignment="right"):
                st.badge(f"Zoom {label}", color="gray")
                st.button(
                    "Zoom out", key=f"{key}_out", icon=":material/zoom_out:",
                    on_click=change_zoom, args=(key, -1), disabled=level == 0,
                )
                st.button(
                    "Reset", key=f"{key}_reset", icon=":material/restart_alt:",
                    on_click=reset_zoom, args=(key,),
                    disabled=level == DEFAULT_ZOOM_INDEX,
                )
                st.button(
                    "Zoom in", key=f"{key}_in", icon=":material/zoom_in:",
                    on_click=change_zoom, args=(key, 1),
                    disabled=level == len(ZOOM_LEVELS) - 1,
                )
            st.pyplot(
                builder(frame, stats), alt=alt_text, clear_figure=True, width=width
            )


def page_distributions() -> None:
    st.title("Distributions")
    st.caption(
        "Univariate EDA: the shape of transaction values, categorical profiles, "
        "timing and the customer profile attached to each payment. Every figure "
        "uses the shared filters."
    )
    render_figures([
        ("Transaction value distribution and boxplot", fig_value_distribution,
         "Histogram and boxplot of transaction values, both right-skewed"),
        ("Categorical profiles", fig_categorical_counts,
         "Count plots for channel, category, status, device, segment and adoption"),
        ("When payments occur", fig_temporal_patterns,
         "Transaction counts by hour, weekday and calendar month"),
        ("Customer profile attached to each payment", fig_customer_profile,
         "Distributions of age, income, tenure and self-reported digital frequency"),
    ])


def page_relationships() -> None:
    st.title("Relationships")
    st.caption(
        "Bivariate EDA: how value, channel, adoption, income and geography move "
        "together. Associations are descriptive, not causal."
    )
    render_figures([
        ("Value by merchant category", fig_value_by_category,
         "Boxplots of transaction value by merchant category, ordered by median"),
        ("Segment × payment channel", fig_segment_channel_heatmap,
         "Annotated heatmap of transaction counts by segment and payment channel"),
        ("Adoption, tenure and value", fig_adoption_tenure_value,
         "Boxplot of value by adoption level and scatterplot of tenure against value"),
        ("Outcome mix by channel", fig_status_by_channel,
         "Stacked bars of successful, failed and pending shares for each channel"),
        ("Income band vs value", fig_income_vs_value,
         "Stripplot of transaction value across income bands, coloured by adoption"),
        ("Where payments occur", fig_geography,
         "Transaction counts by district and mean value by urbanity"),
    ])


def page_multivariate() -> None:
    st.title("Multivariate")
    st.caption(
        "Correlations across all numeric fields, plus a focused look at the "
        "segment × channel value surface and the largest payments."
    )
    render_figures([
        ("Numeric correlation matrix", fig_correlation_heatmap,
         "Annotated Pearson correlation heatmap for the numeric variables"),
        ("Segment × channel value and outliers", fig_multivariate_outliers,
         "Heatmap of mean value by segment and channel beside the ten largest payments"),
    ])
    st.caption(
        "The income–value association is expected by design: the data generator "
        "scales amounts by income. It is not evidence of causation."
    )


# ---------------------------------------------------------------------------
# Page 6 — Descriptive statistics (Stage 3), interactive tables
# ---------------------------------------------------------------------------

def build_summary_text(df: pd.DataFrame, s: dict) -> str:
    """Reproduce eda_analysis.py's summary file for the currently filtered rows."""
    lines: list[str] = []
    lines.append("FINAL VISUALISATION - DESCRIPTIVE STATISTICS")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Filtered transaction rows : {len(df):,}")
    lines.append(f"Customer dimension rows   : {len(customers_all):,}")
    lines.append(f"Location dimension rows   : {len(locations):,}")
    lines.append(f"Analysis frame            : {df.shape[0]:,} rows x {df.shape[1]} columns")
    lines.append(f"Date range                : {df['transaction_date'].min().date()} "
                 f"to {df['transaction_date'].max().date()}")
    lines.append("")
    lines.append("Missing values per column (merged frame):")
    lines.append(df.isna().sum().to_string())
    lines.append("")
    lines.append("-" * 72)
    lines.append("NUMERIC DESCRIBE - transaction-level variables")
    lines.append("-" * 72)
    lines.append(df[[
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
    lines.append("CATEGORICAL FREQUENCIES")
    lines.append("-" * 72)
    for col in CATEGORICAL_COLS:
        vc = df[col].value_counts()
        pct = (vc / len(df) * 100).round(2)
        lines.append(f"\n[{col}]")
        lines.append(pd.DataFrame({"count": vc, "percent": pct}).to_string())
    lines.append("")
    lines.append("-" * 72)
    lines.append("TRANSACTION VALUE - GROUPED SUMMARY (BND)")
    lines.append("-" * 72)
    for col in GROUP_COLS:
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
                     normalize="index") * 100).round(1)
        .reindex(SEGMENT_ORDER).fillna(0).to_string()
    )
    lines.append("\n[Channel x Status - row percentages]")
    lines.append(
        (pd.crosstab(df["payment_channel"], df["transaction_status"],
                     normalize="index") * 100).round(2)
        .reindex(CHANNEL_ORDER).fillna(0).to_string()
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
        .reindex(SEGMENT_ORDER).fillna(0).to_string()
    )
    lines.append("")
    lines.append("-" * 72)
    lines.append("CORRELATION MATRIX (Pearson) - numeric variables")
    lines.append("-" * 72)
    lines.append(s["corr"].round(3).to_string())
    lines.append("")
    lines.append(f"Income vs value  Pearson r   = {s['pearson']:.3f}")
    lines.append(f"Income vs value  Spearman rho = {s['spearman']:.3f}")
    lines.append(
        "Interpretation: association only. The generator scales amount by income, "
        "so a positive association is expected by design and is not causal evidence "
        "about real-world behaviour."
    )
    lines.append("")
    lines.append("-" * 72)
    lines.append("OUTLIER CHECK (Tukey 1.5 x IQR)")
    lines.append("-" * 72)
    values = s["values"]
    high = values > s["upper_fence"]
    lines.append(f"Q1={s['q1']:.2f}  Q3={s['q3']:.2f}  IQR={s['iqr']:.2f}")
    lines.append(f"Upper fence={s['upper_fence']:.2f}  Lower fence={s['lower_fence']:.2f}")
    lines.append(f"High-value outliers: {int(high.sum()):,} "
                 f"({high.mean() * 100:.2f}%)")
    lines.append("\nOutlier count by merchant category:")
    lines.append(
        df.assign(outlier=high).groupby("merchant_category")["outlier"]
        .sum().sort_values(ascending=False).to_string()
    )
    lines.append("\nTop 10 largest transactions:")
    lines.append(
        df.nlargest(10, "transaction_value_bnd")[[
            "transaction_id", "transaction_value_bnd", "merchant_category",
            "payment_channel", "customer_segment", "monthly_income_bnd",
        ]].to_string(index=False)
    )
    return "\n".join(lines)


def page_statistics() -> None:
    st.title("Statistics")
    st.caption(
        "Descriptive statistics for the current selection. These tables are the "
        "interactive equivalent of `eda_outputs/summary_statistics.txt`."
    )

    n = len(frame)
    with st.container(horizontal=True):
        st.metric("Filtered rows", f"{n:,}", border=True)
        st.metric("Columns", f"{frame.shape[1]}", border=True)
        st.metric("Median value", f"{stats['values'].median():,.2f} BND", border=True)
        st.metric("Tukey upper fence", f"{stats['upper_fence']:,.2f} BND", border=True)

    tab_overview, tab_freq, tab_groups, tab_cross, tab_corr, tab_outliers = st.tabs([
        "Overview", "Frequencies", "Value summaries", "Crosstabs",
        "Correlations", "Outliers",
    ])

    with tab_overview:
        with st.container(border=True):
            st.subheader("Numeric describe")
            tx_level = frame[[
                "transaction_hour", "transaction_value_bnd", "adoption_tenure_months",
            ]].describe().T
            st.dataframe(tx_level, alt="Descriptive statistics for transaction variables")
            st.caption("Customer and location variables")
            st.dataframe(
                frame[["age", "monthly_income_bnd", "latitude", "longitude"]]
                .describe().T,
                alt="Descriptive statistics for customer and location variables",
            )
        with st.container(border=True):
            st.subheader("Missing values")
            missing = frame.isna().sum().rename("missing").to_frame()
            st.dataframe(missing[missing["missing"] > 0] if missing["missing"].any()
                         else missing.head(0), alt="Missing value counts per column")
            st.caption("No missing values in the current selection."
                       if not missing["missing"].any() else
                       "Counts are for the merged analysis frame.")

    with tab_freq:
        with st.container(border=True):
            st.subheader("Categorical frequencies")
            col = st.selectbox("Column", CATEGORICAL_COLS, key="freq_col")
            vc = frame[col].value_counts().rename("count").to_frame()
            vc["percent"] = (vc["count"] / n * 100).round(2)
            st.dataframe(vc, alt=f"Count and share for each {col} value")

    with tab_groups:
        with st.container(border=True):
            st.subheader("Transaction value by group")
            col = st.selectbox("Group by", GROUP_COLS, key="group_col")
            grouped = frame.groupby(col)["transaction_value_bnd"].agg(
                ["count", "mean", "median", "std", "min", "max"]
            ).round(2).sort_values("median", ascending=False)
            st.dataframe(grouped, alt=f"Transaction value summary grouped by {col}")

    with tab_cross:
        with st.container(border=True):
            st.subheader("Crosstab: segment × channel (row %)")
            st.dataframe(
                (pd.crosstab(frame["customer_segment"], frame["payment_channel"],
                             normalize="index") * 100).round(1)
                .reindex(SEGMENT_ORDER).fillna(0),
                alt="Share of payment channels within each customer segment",
            )
        with st.container(border=True):
            st.subheader("Crosstab: channel × status (row %)")
            st.dataframe(
                (pd.crosstab(frame["payment_channel"], frame["transaction_status"],
                             normalize="index") * 100).round(2)
                .reindex(CHANNEL_ORDER).fillna(0),
                alt="Share of transaction statuses within each payment channel",
            )
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Adoption × urbanity (mean value)")
                st.dataframe(
                    frame.pivot_table(index="adoption_level", columns="urbanity",
                                      values="transaction_value_bnd", aggfunc="mean")
                    .round(2),
                    alt="Mean transaction value by adoption level and urbanity",
                )
        with right:
            with st.container(border=True):
                st.subheader("Segment × urbanity (counts)")
                st.dataframe(
                    pd.crosstab(frame["customer_segment"], frame["urbanity"])
                    .reindex(SEGMENT_ORDER).fillna(0),
                    alt="Transaction counts by customer segment and urbanity",
                )

    with tab_corr:
        with st.container(border=True):
            st.subheader("Pearson correlations")
            st.dataframe(stats["corr"].round(3), alt="Pearson correlation matrix")
            st.caption(
                f"Income vs value: Pearson r = {stats['pearson']:.3f}, "
                f"Spearman rho = {stats['spearman']:.3f}. Association only — "
                "the generator scales amounts by income, so this is not causal."
            )

    with tab_outliers:
        with st.container(border=True):
            st.subheader("Tukey 1.5 × IQR check")
            high = stats["values"] > stats["upper_fence"]
            st.markdown(
                f"Q1 = **{stats['q1']:,.2f}**, Q3 = **{stats['q3']:,.2f}**, "
                f"IQR = **{stats['iqr']:,.2f}** BND. Upper fence = "
                f"**{stats['upper_fence']:,.2f}** BND."
            )
            st.metric("High-value outliers", f"{int(high.sum()):,}",
                      f"{high.mean() * 100:.1f}% of selection", border=True)
            outlier_counts = (
                frame.assign(outlier=high)
                .groupby("merchant_category")["outlier"]
                .sum().sort_values(ascending=False).rename("outliers").to_frame()
            )
            st.dataframe(outlier_counts, alt="Outlier counts by merchant category")
            st.caption("Ten largest payments in the current selection")
            st.dataframe(
                frame.nlargest(10, "transaction_value_bnd")[[
                    "transaction_id", "transaction_value_bnd", "merchant_category",
                    "payment_channel", "customer_segment", "monthly_income_bnd",
                ]],
                hide_index=True,
                alt="Ten largest payments in the current selection",
            )

    st.divider()
    summary_text = build_summary_text(frame, stats)
    st.download_button(
        "Download full summary (.txt)",
        data=summary_text.encode("utf-8"),
        file_name="summary_statistics_filtered.txt",
        mime="text/plain",
        icon=":material/download:",
    )
    with st.expander("Preview summary"):
        st.text(summary_text)


# ---------------------------------------------------------------------------
# Live clock (top right) — refreshes itself without rerunning the whole app
# ---------------------------------------------------------------------------

@st.fragment(run_every="1s")
def live_clock() -> None:
    now = datetime.now()
    st.badge(now.strftime("%H:%M:%S"), icon=":material/schedule:", color="primary")
    st.caption(now.strftime("%a %d %b %Y"))


# ---------------------------------------------------------------------------
# App entry point: load once, navigate, then filter the analysis pages
# ---------------------------------------------------------------------------

header_title, clock_slot = st.columns([10, 1], gap="small")
with header_title:
    st.title("Digital Payment Analytics")
with clock_slot:
    live_clock()

all_data, locations, customers_all = load_data()

page = st.navigation(
    {
        "": [
            st.Page(page_about, title="About", icon=":material/info:"),
            st.Page(page_github, title="GitHub", icon=":material/qr_code:"),
        ],
        "Overview": [
            st.Page(
                page_overview, title="Overview", icon=":material/dashboard:",
                default=True,
            ),
            st.Page(page_data_sql, title="Data & SQL", icon=":material/database:"),
        ],
        "Exploratory analysis": [
            st.Page(page_distributions, title="Distributions", icon=":material/bar_chart:"),
            st.Page(page_relationships, title="Relationships", icon=":material/scatter_plot:"),
            st.Page(page_multivariate, title="Multivariate", icon=":material/grid_on:"),
            st.Page(page_statistics, title="Statistics", icon=":material/table:"),
        ],
    },
    position="top",
)

# Informational pages do not require a valid filter selection. Data pages run
# the shared filters once, then render as before.
if page.title in {"About", "GitHub"}:
    page.run()
    st.stop()

frame = apply_filters(all_data, locations)
start_date = frame["transaction_date"].min().date()
end_date = frame["transaction_date"].max().date()
stats = numeric_stats(frame)
st.session_state.setdefault("sql_query", EXAMPLE_QUERIES["Channel volume"])
page.run()
