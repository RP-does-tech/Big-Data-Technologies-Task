"""
Stage 6 (Streamlit) — interactive visualisation dashboard
=========================================================

A Streamlit-only companion to ``stage6_dashboard.py``. It reads the Stage 2
CSVs, applies the sidebar filters, and redraws the six question-led visuals
from Stage 6 with interpretations that update with the selected data. It ends
with a small SQL console over the filtered rows (Python's sqlite3, no extra
dependency).

Run::

    python -m streamlit run streamlit_dashboard.py
"""

from __future__ import annotations

import os
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Digital payment analytics",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DIGITAL_RAILS = ["Mobile Wallet", "QR Payment"]
STATUS_ORDER = ["Successful", "Failed", "Pending"]


# ---------------------------------------------------------------------------
# Data loading (cached: filters are applied afterwards, outside the cache)
# ---------------------------------------------------------------------------

@st.cache_data(ttl="1h", show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    tx = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"))
    loc = pd.read_csv(os.path.join(DATA_DIR, "locations.csv"))
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
    tx = tx.merge(
        loc[["location_id", "district", "urbanity"]],
        on="location_id",
        how="left",
    )
    return tx, loc


# ---------------------------------------------------------------------------
# Small chart helpers
# ---------------------------------------------------------------------------

def horizontal_bars(
    source: pd.DataFrame,
    category_col: str,
    value_col: str,
    x_title: str,
    tooltips: list[alt.Tooltip],
    *,
    color: str = "#4C72B0",
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

    selected = st.pills(
        label,
        options,
        selection_mode="multi",
        key=key,
        wrap=True,
    )
    with st.container(horizontal=True):
        st.button("All", key=f"{key}_all", icon=":material/done_all:",
                  on_click=select_all)
        st.button("Clear", key=f"{key}_clear", icon=":material/close:",
                  on_click=clear_all)
    return selected


# ---------------------------------------------------------------------------
# Header and sidebar filters
# ---------------------------------------------------------------------------

st.title("Digital payment analytics")
st.caption(
    "Interactive view of 2025 Brunei digital-payment transactions. Six "
    "question-led charts, each with an interpretation that follows the filters."
)

tx_all, locations = load_data()

min_date = tx_all["transaction_date"].min().date()
max_date = tx_all["transaction_date"].max().date()
channels_all = sorted(tx_all["payment_channel"].dropna().unique())
segments_all = sorted(tx_all["customer_segment"].dropna().unique())
districts_all = sorted(locations["district"].dropna().unique())
statuses_all = [s for s in STATUS_ORDER if s in set(tx_all["transaction_status"])]

filter_specs = (
    ("f_channels", channels_all),
    ("f_segments", segments_all),
    ("f_districts", districts_all),
    ("f_statuses", statuses_all),
)
for key, options in filter_specs:
    st.session_state.setdefault(key, list(options))


def reset_filters() -> None:
    st.session_state.pop("f_dates", None)
    for key, options in filter_specs:
        st.session_state[key] = list(options)


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

start_date, end_date = dates if isinstance(dates, tuple) and len(dates) == 2 else (dates, dates)

if not all([selected_channels, selected_segments, selected_districts, selected_statuses]):
    st.info("Select at least one option in every filter to draw the charts.")
    st.stop()

tx = tx_all.loc[
    tx_all["transaction_date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    & tx_all["payment_channel"].isin(selected_channels)
    & tx_all["customer_segment"].isin(selected_segments)
    & tx_all["district"].isin(selected_districts)
    & tx_all["transaction_status"].isin(selected_statuses)
].copy()

if tx.empty:
    st.warning("No transactions match the current filters. Widen the selection or reset.")
    st.stop()

success = tx[tx["transaction_status"] == "Successful"].copy()
n = len(tx)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

success_value = success["transaction_value_bnd"].sum()
success_rate = len(success) / n * 100
digital_share = (
    tx["payment_channel"].isin(DIGITAL_RAILS).mean() * 100 if n else 0.0
)

with st.container(horizontal=True):
    st.metric("Transactions", f"{n:,}", border=True)
    st.metric("Successful value", f"{success_value:,.0f} BND", border=True)
    st.metric("Success rate", f"{success_rate:.1f}%", border=True)
    st.metric("Digital-first share", f"{digital_share:.1f}%", border=True)

st.caption(
    f"Showing {n:,} of {len(tx_all):,} transactions "
    f"({start_date:%d %b %Y} – {end_date:%d %b %Y}). "
    "Digital-first = Mobile Wallet + QR Payment."
)

# ---------------------------------------------------------------------------
# Q1 — payment channels
# ---------------------------------------------------------------------------

left, right = st.columns(2)
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
                channel_counts,
                "payment_channel",
                "transactions",
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

# ---------------------------------------------------------------------------
# Q2 — merchant-category spend
# ---------------------------------------------------------------------------

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
                    category_spend,
                    "merchant_category",
                    "successful_value",
                    "Successful transaction value (BND)",
                    [
                        alt.Tooltip("merchant_category:N", title="Merchant category"),
                        alt.Tooltip("successful_value:Q", title="Value (BND)", format=",.0f"),
                        alt.Tooltip("payments:Q", title="Payments", format=","),
                    ],
                    color="#55A868",
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

# ---------------------------------------------------------------------------
# Q3 — digital-first segments
# ---------------------------------------------------------------------------

left, right = st.columns(2)
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
                    seg,
                    "customer_segment",
                    "digital_share",
                    "Wallet + QR share of successful payments (%)",
                    [
                        alt.Tooltip("customer_segment:N", title="Customer segment"),
                        alt.Tooltip("digital_share:Q", title="Digital-first (%)", format=".1f"),
                        alt.Tooltip("payments:Q", title="Payments", format=","),
                    ],
                    color="#8172B3",
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

# ---------------------------------------------------------------------------
# Q4 — outcomes by channel
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Q5 — geography
# ---------------------------------------------------------------------------

left, right = st.columns(2)
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
                district_counts,
                "district",
                "transactions",
                "Number of transactions",
                [
                    alt.Tooltip("district:N", title="District"),
                    alt.Tooltip("transactions:Q", title="Transactions", format=","),
                    alt.Tooltip("share:Q", title="Share (%)", format=".1f"),
                ],
                color="#DD8452",
            ),
            alt="Transaction counts by district, showing where payment volume concentrates",
        )
        top_district = district_counts.iloc[0]
        urban_means = (
            tx.groupby("urbanity")["transaction_value_bnd"].mean().sort_values()
        )
        means_text = " | ".join(f"{k} {v:.0f} BND" for k, v in urban_means.items())
        st.caption(
            f"**Interpretation:** {top_district['district']} accounts for "
            f"{top_district['share']:.1f}% of payments, yet mean values by urbanity "
            f"are close ({means_text}): volume is concentrated, amounts are not."
        )

# ---------------------------------------------------------------------------
# Q6 — value distribution and outliers
# ---------------------------------------------------------------------------

with right:
    with st.container(border=True):
        st.subheader("Q6 · Are there extreme payment values?")
        q1, q3 = tx["transaction_value_bnd"].quantile([0.25, 0.75])
        fence = q3 + 1.5 * (q3 - q1)
        median = tx["transaction_value_bnd"].median()

        histogram = (
            alt.Chart(tx)
            .mark_bar(color="#4C72B0", opacity=0.85)
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
                                                range=["#55A868", "#C44E52"])),
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
# Raw data, on demand
# ---------------------------------------------------------------------------

with st.expander("Filtered transaction data", icon=":material/table:"):
    columns = [
        "transaction_id", "transaction_date", "payment_channel",
        "merchant_category", "transaction_value_bnd", "transaction_status",
        "customer_segment", "district", "urbanity", "device_type",
    ]
    view = tx[columns]
    st.dataframe(
        view,
        hide_index=True,
        column_config={
            "transaction_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "transaction_value_bnd": st.column_config.NumberColumn("Value (BND)", format="%.2f"),
            "transaction_id": None,
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

# ---------------------------------------------------------------------------
# SQL query console over the filtered rows
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


st.session_state.setdefault("sql_query", EXAMPLE_QUERIES["Channel volume"])

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
        "Example queries",
        list(EXAMPLE_QUERIES),
        selection_mode="single",
        key="sql_example",
        on_change=use_example,
        wrap=True,
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
                    result,
                    hide_index=True,
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
