"""Sales Data Analysis Dashboard.

Run from the project root with:
    streamlit run app.py

All data cleaning, filtering and aggregation lives in utils/data_processing.py.
This file only builds the user interface and the charts.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import data_processing as dp

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Relative to this file, so it works locally and on Streamlit Community Cloud.
DATA_PATH = Path(__file__).resolve().parent / "data" / "sales_data.csv"
CURRENCY = "$"
PRIMARY_COLOR = "#2563eb"
CATEGORY_COLORS = px.colors.qualitative.Safe  # colour-blind-friendly palette

st.set_page_config(
    page_title="Sales Data Analysis Dashboard",
    page_icon="📊",
    layout="wide",
)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def money(value: float, decimals: int = 2) -> str:
    """Format a number as currency, e.g. $1,234.50."""
    return f"{CURRENCY}{value:,.{decimals}f}"


@st.cache_data(show_spinner="Loading and cleaning data...")
def load_data(path: str, file_version: float):
    """Load + clean the CSV. `file_version` (modified time) refreshes the cache
    automatically if the file is replaced."""
    return dp.load_clean_sales_data(path)


def show_chart(figure: go.Figure) -> None:
    """Render a Plotly figure at full container width."""
    st.plotly_chart(figure, width="stretch")


def style_figure(figure: go.Figure, height: int = 380) -> go.Figure:
    """Apply consistent layout settings to every chart."""
    figure.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=60, b=10),
        title=dict(font=dict(size=16), x=0),
        font=dict(size=13),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
    )
    return figure


def money_axis(figure: go.Figure, axis: str) -> None:
    """Format an axis as currency."""
    update = figure.update_yaxes if axis == "y" else figure.update_xaxes
    update(tickprefix=CURRENCY, tickformat=",.0f")


def month_axis(figure: go.Figure) -> None:
    """Show one labelled tick per month on a date x-axis."""
    figure.update_xaxes(tickformat="%b %Y", dtick="M1", tickangle=-45, title_text="Month")


# --------------------------------------------------------------------------- #
# Chart builders (each returns a Plotly figure from an aggregated DataFrame)
# --------------------------------------------------------------------------- #


def monthly_revenue_chart(monthly: pd.DataFrame) -> go.Figure:
    figure = px.line(
        monthly, x="Month", y="Revenue", markers=True,
        custom_data=["Orders", "Units"], title="Monthly revenue trend",
    )
    figure.update_traces(
        line_color=PRIMARY_COLOR,
        hovertemplate=(
            "<b>%{x|%B %Y}</b><br>Revenue: " + CURRENCY + "%{y:,.2f}"
            "<br>Orders: %{customdata[0]}<br>Units: %{customdata[1]}<extra></extra>"
        ),
    )
    month_axis(figure)
    money_axis(figure, "y")
    figure.update_yaxes(title_text=f"Revenue ({CURRENCY})", rangemode="tozero")
    return style_figure(figure)


def revenue_by_product_chart(by_product: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        by_product, x="Revenue", y="Product", orientation="h",
        custom_data=["Orders", "Units", "Share_Pct"], title="Revenue by product",
    )
    figure.update_traces(
        marker_color=PRIMARY_COLOR,
        hovertemplate=(
            "<b>%{y}</b><br>Revenue: " + CURRENCY + "%{x:,.2f}"
            "<br>Share: %{customdata[2]:.1f}%<br>Orders: %{customdata[0]}"
            "<br>Units: %{customdata[1]}<extra></extra>"
        ),
    )
    figure.update_yaxes(categoryorder="total ascending", title_text="")
    figure.update_xaxes(title_text=f"Revenue ({CURRENCY})")
    money_axis(figure, "x")
    return style_figure(figure, height=430)


def revenue_by_region_chart(by_region: pd.DataFrame) -> go.Figure:
    figure = px.pie(
        by_region, names="Region", values="Revenue", hole=0.45,
        custom_data=["Orders", "Units"], color_discrete_sequence=CATEGORY_COLORS,
        title="Revenue share by region",
    )
    figure.update_traces(
        textinfo="percent+label",
        hovertemplate=(
            "<b>%{label}</b><br>Revenue: " + CURRENCY + "%{value:,.2f}"
            "<br>Share: %{percent}<br>Orders: %{customdata[0]}"
            "<br>Units: %{customdata[1]}<extra></extra>"
        ),
    )
    figure.update_layout(showlegend=False)
    return style_figure(figure)


def category_chart(by_category: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        by_category, x="Category", y="Revenue", custom_data=["Orders", "Units", "Share_Pct"],
        title="Sales by product category",
    )
    figure.update_traces(
        marker_color=PRIMARY_COLOR,
        texttemplate=CURRENCY + "%{y:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>Revenue: " + CURRENCY + "%{y:,.2f}"
            "<br>Share: %{customdata[2]:.1f}%<br>Orders: %{customdata[0]}"
            "<br>Units: %{customdata[1]}<extra></extra>"
        ),
    )
    figure.update_xaxes(title_text="")
    figure.update_yaxes(title_text=f"Revenue ({CURRENCY})")
    money_axis(figure, "y")
    return style_figure(figure)


def monthly_orders_chart(monthly: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        monthly, x="Month", y="Orders", custom_data=["Units"], title="Monthly order volume"
    )
    figure.update_traces(
        marker_color=PRIMARY_COLOR,
        hovertemplate=(
            "<b>%{x|%B %Y}</b><br>Orders: %{y}<br>Units: %{customdata[0]}<extra></extra>"
        ),
    )
    month_axis(figure)
    figure.update_yaxes(title_text="Number of orders")
    return style_figure(figure)


def top_products_chart(top: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        top, x="Revenue", y="Product", orientation="h",
        custom_data=["Orders", "Units", "Share_Pct"], title="Top 5 products by revenue",
    )
    figure.update_traces(
        marker_color=PRIMARY_COLOR,
        texttemplate=CURRENCY + "%{x:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>Revenue: " + CURRENCY + "%{x:,.2f}"
            "<br>Share: %{customdata[2]:.1f}%<br>Orders: %{customdata[0]}"
            "<br>Units: %{customdata[1]}<extra></extra>"
        ),
    )
    figure.update_yaxes(categoryorder="total ascending", title_text="")
    figure.update_xaxes(title_text=f"Revenue ({CURRENCY})")
    money_axis(figure, "x")
    # Leave headroom so the longest bar's value label is not clipped.
    figure.update_xaxes(range=[0, top["Revenue"].max() * 1.2])
    return style_figure(figure)


# --------------------------------------------------------------------------- #
# Page sections
# --------------------------------------------------------------------------- #


def render_header() -> None:
    st.title("📊 Sales Data Analysis Dashboard")
    st.write(
        "Explore revenue, orders and product performance. Use the filters in the "
        "sidebar and every KPI, chart, insight and table updates."
    )
    st.info(
        "**Synthetic sample data.** The records shown here were randomly generated "
        "for demonstration. They are not real business transactions.",
        icon="ℹ️",
    )


def render_data_quality(report: dp.CleaningReport) -> None:
    """Show what the cleaning step did, so no row disappears silently."""
    with st.expander("Data quality report", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Rows loaded", f"{report.rows_loaded:,}")
        col2.metric("Rows used", f"{report.rows_kept:,}")
        col3.metric("Invalid rows excluded", f"{report.rows_rejected:,}")
        col4.metric("Exact duplicates removed", f"{report.exact_duplicates_removed:,}")

        if report.unknown_category_filled or report.unknown_region_filled:
            st.write(
                f"Missing values labelled **{dp.UNKNOWN_LABEL}**: "
                f"{report.unknown_category_filled} Category, "
                f"{report.unknown_region_filled} Region."
            )
        if report.conflicting_rows_flagged:
            st.warning(
                f"{report.conflicting_rows_flagged} row(s) share an Order_ID and Product "
                "but have different details. They were kept; please review them."
            )
            st.dataframe(report.conflicting_rows, hide_index=True)
        if report.rows_rejected:
            st.write("**Excluded rows by reason**")
            st.dataframe(
                pd.Series(report.rejected_by_reason, name="Rows").rename_axis("Reason"),
            )
            st.dataframe(report.rejected_rows, hide_index=True)
        if not (report.rows_rejected or report.exact_duplicates_removed
                or report.conflicting_rows_flagged):
            st.success("No data-quality problems were found.")


def render_sidebar(sales: pd.DataFrame) -> dict:
    """Draw the filters and return the selected values."""
    st.sidebar.header("Filters")

    min_date = sales["Order_Date"].min().date()
    max_date = sales["Order_Date"].max().date()
    start_date = st.sidebar.date_input(
        "Start date", value=min_date, min_value=min_date, max_value=max_date
    )
    end_date = st.sidebar.date_input(
        "End date", value=max_date, min_value=min_date, max_value=max_date
    )
    if start_date > end_date:
        st.sidebar.error("Start date must be on or before the end date.")
        st.stop()

    regions = st.sidebar.multiselect(
        "Region", sorted(sales["Region"].unique()), default=sorted(sales["Region"].unique())
    )
    categories = st.sidebar.multiselect(
        "Product category", sorted(sales["Category"].unique()),
        default=sorted(sales["Category"].unique()),
    )
    products = st.sidebar.multiselect(
        "Product name", sorted(sales["Product"].unique()),
        default=sorted(sales["Product"].unique()),
    )
    st.sidebar.caption(
        "Filters combine with AND. Clearing a selection removes all of its records."
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "regions": regions,
        "categories": categories,
        "products": products,
    }


def render_kpis(kpis: dict) -> None:
    cards = [
        ("Total Revenue", money(kpis["total_revenue"]), "Sum of Quantity × Unit_Price"),
        ("Total Orders", f"{kpis['total_orders']:,}", "Number of distinct Order_IDs"),
        ("Total Units Sold", f"{kpis['total_units']:,}", "Sum of Quantity"),
        ("Average Order Value", money(kpis["average_order_value"]), "Total Revenue ÷ Total Orders"),
    ]
    for column, (label, value, help_text) in zip(st.columns(4), cards):
        with column, st.container(border=True):
            st.metric(label, value, help=help_text)


def render_insights(insights: dict) -> None:
    """Show insights generated from the current (filtered) data."""
    st.subheader("Business insights")
    top_product, top_region = insights["top_product"], insights["top_region"]
    top_category, best_month = insights["top_category"], insights["best_month"]

    cards = [
        ("Highest-revenue product", top_product["Product"],
         f"{money(top_product['Revenue'])} · {top_product['Share_Pct']:.1f}% of revenue"),
        ("Best-performing region", top_region["Region"],
         f"{money(top_region['Revenue'])} · {top_region['Share_Pct']:.1f}% of revenue"),
        ("Highest-revenue category", top_category["Category"],
         f"{money(top_category['Revenue'])} · {top_category['Share_Pct']:.1f}% of revenue"),
        ("Month with highest revenue", best_month["Month"].strftime("%B %Y"),
         money(best_month["Revenue"])),
    ]
    for column, (label, headline, detail) in zip(st.columns(4), cards):
        with column, st.container(border=True):
            st.caption(label)
            st.markdown(f"#### {headline}")
            st.write(detail)

    # Revenue distribution across products and regions.
    k = insights["top_products_count"]
    product_text = (
        f"- **Products:** the top {k} product{'s' if k > 1 else ''} generate "
        f"**{insights['top_products_share_pct']:.1f}%** of revenue "
        f"across {insights['product_count']} product(s)."
    )
    if insights["region_count"] > 1:
        lowest = insights["lowest_region"]
        region_text = (
            f"- **Regions:** {top_region['Region']} contributes "
            f"**{top_region['Share_Pct']:.1f}%** of revenue, while {lowest['Region']} "
            f"contributes **{lowest['Share_Pct']:.1f}%**."
        )
    else:
        region_text = f"- **Regions:** all revenue comes from {top_region['Region']}."
    st.markdown(product_text + "\n" + region_text)


def render_charts(filtered: pd.DataFrame) -> None:
    monthly = dp.monthly_summary(filtered)
    by_product = dp.revenue_by(filtered, "Product")
    by_region = dp.revenue_by(filtered, "Region")
    by_category = dp.revenue_by(filtered, "Category")
    top = dp.top_products(filtered, 5)

    st.subheader("Charts")
    left, right = st.columns([3, 2])
    with left:
        show_chart(monthly_revenue_chart(monthly))
    with right:
        show_chart(revenue_by_region_chart(by_region))

    left, right = st.columns(2)
    with left:
        show_chart(revenue_by_product_chart(by_product))
    with right:
        show_chart(top_products_chart(top))

    left, right = st.columns(2)
    with left:
        show_chart(category_chart(by_category))
    with right:
        show_chart(monthly_orders_chart(monthly))


def render_table(filtered: pd.DataFrame) -> None:
    st.subheader("Sales records")
    search = st.text_input(
        "Search records",
        placeholder="Type an order ID, product, category or region...",
    ).strip()

    table = filtered
    if search:
        text_columns = ["Order_ID", "Product", "Category", "Region"]
        match = pd.Series(False, index=table.index)
        for column in text_columns:
            match |= table[column].str.contains(search, case=False, regex=False)
        table = table.loc[match]

    st.caption(f"Showing {len(table):,} of {len(filtered):,} records matching the sidebar filters.")
    if table.empty:
        st.warning("No records match your search.")
        return

    st.dataframe(
        table[dp.REQUIRED_COLUMNS + ["Revenue"]],
        hide_index=True,
        column_config={
            "Order_Date": st.column_config.DateColumn("Order date", format="YYYY-MM-DD"),
            "Unit_Price": st.column_config.NumberColumn("Unit price", format=f"{CURRENCY}%.2f"),
            "Revenue": st.column_config.NumberColumn("Revenue", format=f"{CURRENCY}%.2f"),
        },
    )
    st.download_button(
        "⬇️ Download filtered data (CSV)",
        data=dp.to_csv_bytes(table),
        file_name="filtered_sales_data.csv",
        mime="text/csv",
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> None:
    render_header()

    try:
        file_version = DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0.0
        sales, report = load_data(str(DATA_PATH), file_version)
    except dp.DataValidationError as error:
        st.error(f"**The dataset could not be loaded.** {error}")
        st.info(
            "Expected a CSV at `data/sales_data.csv` with these columns: "
            + ", ".join(f"`{col}`" for col in dp.REQUIRED_COLUMNS)
        )
        st.stop()

    render_data_quality(report)
    selection = render_sidebar(sales)

    filtered = dp.filter_sales_data(
        sales,
        start_date=selection["start_date"],
        end_date=selection["end_date"],
        regions=selection["regions"],
        categories=selection["categories"],
        products=selection["products"],
    )

    if filtered.empty:
        st.warning(
            "No records match the current filters. Widen the date range or select "
            "more regions, categories or products."
        )
        st.stop()

    render_kpis(dp.calculate_kpis(filtered))
    render_insights(dp.generate_insights(filtered))
    render_charts(filtered)
    render_table(filtered)

    st.caption("Built with Python, Pandas, NumPy, Plotly and Streamlit · Synthetic sample data.")


main()
