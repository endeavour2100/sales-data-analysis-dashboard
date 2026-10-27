"""Data loading, cleaning, filtering and aggregation for the Sales Dashboard.

This module contains NO Streamlit code, so every function can be tested on its
own and reused outside the dashboard.

Typical flow:
    sales, report = load_clean_sales_data("data/sales_data.csv")
    filtered = filter_sales_data(sales, start_date, end_date, regions=["East"])
    kpis = calculate_kpis(filtered)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REQUIRED_COLUMNS = [
    "Order_ID",
    "Order_Date",
    "Product",
    "Category",
    "Region",
    "Quantity",
    "Unit_Price",
]
TEXT_COLUMNS = ["Order_ID", "Product", "Category", "Region"]
UNKNOWN_LABEL = "Unknown"

# Human-readable rejection reasons, in the order the checks are applied.
# A row is reported under the FIRST reason that applies to it.
REASON_ORDER_ID = "Missing Order_ID"
REASON_DATE = "Missing or unparseable Order_Date"
REASON_PRODUCT = "Missing Product"
REASON_QTY_INVALID = "Missing or non-numeric Quantity"
REASON_QTY_NON_POSITIVE = "Quantity is zero or negative"
REASON_QTY_FRACTION = "Quantity is not a whole number"
REASON_PRICE_INVALID = "Missing or non-numeric Unit_Price"
REASON_PRICE_NON_POSITIVE = "Unit_Price is zero or negative"


class DataValidationError(Exception):
    """Raised when the dataset is missing, unreadable or malformed."""


@dataclass
class CleaningReport:
    """Summary of what the cleaning step did, so nothing happens silently."""

    rows_loaded: int = 0
    rows_kept: int = 0
    exact_duplicates_removed: int = 0
    conflicting_rows_flagged: int = 0
    unknown_category_filled: int = 0
    unknown_region_filled: int = 0
    rejected_by_reason: dict = field(default_factory=dict)
    rejected_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    duplicate_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    conflicting_rows: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def rows_rejected(self) -> int:
        """Total number of rows excluded because they were invalid."""
        return int(sum(self.rejected_by_reason.values()))


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #


def validate_columns(df: pd.DataFrame) -> None:
    """Raise DataValidationError if any required column is missing."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise DataValidationError(
            "The dataset is missing required column(s): "
            f"{', '.join(missing)}. Expected columns: {', '.join(REQUIRED_COLUMNS)}."
        )


def load_raw_csv(path: Union[str, Path]) -> pd.DataFrame:
    """Read the CSV as text (no type guessing) and check its structure."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DataValidationError(
            f"Dataset file not found at '{csv_path}'. "
            "Place your CSV there or run `python scripts/generate_sample_data.py`."
        )
    try:
        # dtype=str keeps values exactly as written; we convert types ourselves
        # so that bad values are reported instead of silently altered.
        raw = pd.read_csv(csv_path, dtype=str)
    except pd.errors.EmptyDataError as error:
        raise DataValidationError(f"The file '{csv_path.name}' is empty.") from error
    except pd.errors.ParserError as error:
        raise DataValidationError(
            f"The file '{csv_path.name}' is not a valid CSV file: {error}"
        ) from error
    except UnicodeDecodeError as error:
        raise DataValidationError(
            f"The file '{csv_path.name}' could not be read as UTF-8 text."
        ) from error

    raw.columns = [str(col).strip() for col in raw.columns]
    validate_columns(raw)
    if raw.empty:
        raise DataValidationError(
            f"The file '{csv_path.name}' has a header row but no data rows."
        )
    return raw


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #


def _clean_text(series: pd.Series) -> pd.Series:
    """Trim whitespace and turn blank strings into real missing values."""
    text = series.astype("string").str.strip()
    text = text.mask(text.eq(""))
    return text.astype(object).where(text.notna(), np.nan)


def _to_number(series: pd.Series) -> pd.Series:
    """Convert to numbers; anything unparseable (or infinite) becomes NaN."""
    numbers = pd.to_numeric(series, errors="coerce")
    return numbers.replace([np.inf, -np.inf], np.nan)


def _assign_reason(reasons: pd.Series, condition: pd.Series, label: str) -> None:
    """Give `label` to rows that match `condition` and have no reason yet."""
    reasons.loc[condition.fillna(False) & reasons.isna()] = label


def clean_sales_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Validate and clean raw sales data.

    Returns (clean_dataframe, CleaningReport). See the README section
    "Data-cleaning methodology" for the full list of rules.
    """
    validate_columns(raw)
    data = raw[REQUIRED_COLUMNS].copy().reset_index(drop=True)
    report = CleaningReport(rows_loaded=len(data))

    # 1. Standardise text and convert types (invalid values become NaN/NaT).
    parsed = pd.DataFrame(index=data.index)
    for column in TEXT_COLUMNS:
        parsed[column] = _clean_text(data[column])
    # format="mixed" accepts several date styles; ISO (YYYY-MM-DD) is recommended.
    parsed["Order_Date"] = pd.to_datetime(
        data["Order_Date"], errors="coerce", format="mixed"
    )
    parsed["Quantity"] = _to_number(data["Quantity"])
    parsed["Unit_Price"] = _to_number(data["Unit_Price"])

    # 2. Decide which rows are invalid. Each row gets its first matching reason.
    reasons = pd.Series(np.nan, index=data.index, dtype=object)
    _assign_reason(reasons, parsed["Order_ID"].isna(), REASON_ORDER_ID)
    _assign_reason(reasons, parsed["Order_Date"].isna(), REASON_DATE)
    _assign_reason(reasons, parsed["Product"].isna(), REASON_PRODUCT)
    _assign_reason(reasons, parsed["Quantity"].isna(), REASON_QTY_INVALID)
    _assign_reason(reasons, parsed["Quantity"] <= 0, REASON_QTY_NON_POSITIVE)
    _assign_reason(reasons, parsed["Quantity"] % 1 != 0, REASON_QTY_FRACTION)
    _assign_reason(reasons, parsed["Unit_Price"].isna(), REASON_PRICE_INVALID)
    _assign_reason(reasons, parsed["Unit_Price"] <= 0, REASON_PRICE_NON_POSITIVE)

    rejected_mask = reasons.notna()
    report.rejected_by_reason = reasons[rejected_mask].value_counts().to_dict()
    # Show rejected rows exactly as they appeared in the file, plus the reason.
    report.rejected_rows = data.loc[rejected_mask].assign(
        Rejection_Reason=reasons[rejected_mask]
    )

    valid = parsed.loc[~rejected_mask].copy()

    # 3. Missing Category / Region: keep the sale, label it "Unknown".
    #    Revenue is still real, so we do not throw it away.
    report.unknown_category_filled = int(valid["Category"].isna().sum())
    report.unknown_region_filled = int(valid["Region"].isna().sum())
    valid["Category"] = valid["Category"].fillna(UNKNOWN_LABEL)
    valid["Region"] = valid["Region"].fillna(UNKNOWN_LABEL)

    # 4. Duplicates.
    #    - Exact duplicates (every field identical) are removed, keeping the first.
    #    - Rows sharing Order_ID + Product but differing elsewhere are KEPT
    #      (we cannot know which one is right) and reported as conflicts.
    exact_duplicate_mask = valid.duplicated(subset=REQUIRED_COLUMNS, keep="first")
    report.exact_duplicates_removed = int(exact_duplicate_mask.sum())
    report.duplicate_rows = data.loc[valid.index[exact_duplicate_mask]]
    valid = valid.loc[~exact_duplicate_mask]

    conflict_mask = valid.duplicated(subset=["Order_ID", "Product"], keep=False)
    report.conflicting_rows_flagged = int(conflict_mask.sum())
    report.conflicting_rows = data.loc[valid.index[conflict_mask]]

    # 5. Final types and derived columns.
    clean = valid.copy()
    clean["Order_Date"] = clean["Order_Date"].dt.normalize()
    clean["Quantity"] = clean["Quantity"].astype("int64")
    clean["Unit_Price"] = clean["Unit_Price"].astype("float64")
    clean["Revenue"] = np.round(clean["Quantity"] * clean["Unit_Price"], 2)
    # First day of the month, used to group by month.
    clean["Month"] = clean["Order_Date"].dt.to_period("M").dt.to_timestamp()

    clean = clean.sort_values(["Order_Date", "Order_ID"]).reset_index(drop=True)
    report.rows_kept = len(clean)
    return clean, report


def load_clean_sales_data(path: Union[str, Path]) -> tuple[pd.DataFrame, CleaningReport]:
    """Load a CSV and clean it. Raises DataValidationError on unusable data."""
    clean, report = clean_sales_data(load_raw_csv(path))
    if clean.empty:
        raise DataValidationError(
            "No valid rows remain after cleaning. "
            f"{report.rows_rejected} row(s) were rejected; "
            "check the Order_Date, Quantity and Unit_Price columns."
        )
    return clean, report


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


def filter_sales_data(
    df: pd.DataFrame,
    start_date=None,
    end_date=None,
    regions: Optional[Iterable[str]] = None,
    categories: Optional[Iterable[str]] = None,
    products: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Return the rows that match every supplied filter (AND logic).

    - ``None`` means "do not filter on this field".
    - An empty list means "nothing selected", which matches no rows.
    - Dates are inclusive on both ends.
    - Raises ValueError if start_date is after end_date.
    """
    start = pd.Timestamp(start_date) if start_date is not None else None
    end = pd.Timestamp(end_date) if end_date is not None else None
    if start is not None and end is not None and start > end:
        raise ValueError("Start date must be on or before the end date.")

    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df["Order_Date"] >= start
    if end is not None:
        mask &= df["Order_Date"] <= end
    for column, selected in (
        ("Region", regions),
        ("Category", categories),
        ("Product", products),
    ):
        if selected is not None:
            mask &= df[column].isin(list(selected))
    return df.loc[mask]


# --------------------------------------------------------------------------- #
# KPIs and aggregations
# --------------------------------------------------------------------------- #


def calculate_kpis(df: pd.DataFrame) -> dict:
    """Compute the four headline metrics. Safe on empty data (returns zeros).

    Total Orders counts DISTINCT Order_IDs, so an order with several line
    items is counted once. Average Order Value = Total Revenue / Total Orders.
    """
    if df.empty:
        return {
            "total_revenue": 0.0,
            "total_orders": 0,
            "total_units": 0,
            "average_order_value": 0.0,
        }
    total_revenue = float(df["Revenue"].sum())
    total_orders = int(df["Order_ID"].nunique())
    return {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "total_units": int(df["Quantity"].sum()),
        "average_order_value": total_revenue / total_orders,
    }


def revenue_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Revenue, orders, units and revenue share per value of `column`."""
    columns = [column, "Revenue", "Orders", "Units", "Share_Pct"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        df.groupby(column)
        .agg(Revenue=("Revenue", "sum"), Orders=("Order_ID", "nunique"), Units=("Quantity", "sum"))
        .reset_index()
        .sort_values("Revenue", ascending=False)
        .reset_index(drop=True)
    )
    grouped["Share_Pct"] = grouped["Revenue"] / grouped["Revenue"].sum() * 100
    return grouped


def top_products(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """The `n` products with the highest revenue."""
    return revenue_by(df, "Product").head(n)


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, orders and units per calendar month.

    Months with no sales between the first and last month are included with
    zeros, so charts do not skip over gaps.
    """
    columns = ["Month", "Revenue", "Orders", "Units"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    grouped = df.groupby("Month").agg(
        Revenue=("Revenue", "sum"), Orders=("Order_ID", "nunique"), Units=("Quantity", "sum")
    )
    full_range = pd.date_range(grouped.index.min(), grouped.index.max(), freq="MS")
    grouped = grouped.reindex(full_range, fill_value=0)
    grouped.index.name = "Month"
    return grouped.reset_index()


# --------------------------------------------------------------------------- #
# Insights
# --------------------------------------------------------------------------- #


def generate_insights(df: pd.DataFrame) -> Optional[dict]:
    """Derive business insights from the (filtered) data. None if no data.

    Ties are resolved by taking the first entry in revenue order.
    """
    if df.empty:
        return None

    by_product = revenue_by(df, "Product")
    by_region = revenue_by(df, "Region")
    by_category = revenue_by(df, "Category")
    monthly = monthly_summary(df)
    best_month = monthly.loc[monthly["Revenue"].idxmax()]

    top_k = min(3, len(by_product))
    return {
        "top_product": by_product.iloc[0].to_dict(),
        "top_region": by_region.iloc[0].to_dict(),
        "top_category": by_category.iloc[0].to_dict(),
        "best_month": {"Month": best_month["Month"], "Revenue": float(best_month["Revenue"])},
        # Distribution: how concentrated is revenue?
        "top_products_count": top_k,
        "top_products_share_pct": float(by_product["Share_Pct"].head(top_k).sum()),
        "region_count": len(by_region),
        "lowest_region": by_region.iloc[-1].to_dict(),
        "product_count": len(by_product),
    }


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a sales table to UTF-8 CSV bytes for download."""
    export = df[REQUIRED_COLUMNS + ["Revenue"]].copy()
    export["Order_Date"] = pd.to_datetime(export["Order_Date"]).dt.strftime("%Y-%m-%d")
    return export.to_csv(index=False).encode("utf-8")
