"""Unit tests for utils/data_processing.py.

Run from the project root with:  python -m pytest
"""

from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_sample_data import generate_sales_data
from utils import data_processing as dp

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_raw(rows):
    """Build a raw DataFrame (all text, like read_csv(dtype=str)) from dict rows."""
    return pd.DataFrame(rows, columns=dp.REQUIRED_COLUMNS)


def row(order_id="A1", date="2025-01-15", product="Pen", category="Office",
        region="East", quantity="2", price="5.00"):
    return [order_id, date, product, category, region, quantity, price]


@pytest.fixture
def sample_clean():
    """A small, valid, cleaned dataset used by filtering and KPI tests."""
    raw = make_raw([
        row("A1", "2025-01-10", "Pen", "Office", "East", "2", "5.00"),
        row("A2", "2025-01-20", "Desk", "Furniture", "West", "1", "100.00"),
        row("A3", "2025-02-05", "Pen", "Office", "West", "10", "4.50"),
        row("A4", "2025-03-01", "Chair", "Furniture", "East", "3", "50.00"),
    ])
    clean, _ = dp.clean_sales_data(raw)
    return clean


# ----------------------------- revenue ------------------------------------- #


def test_revenue_is_quantity_times_unit_price():
    clean, _ = dp.clean_sales_data(make_raw([row(quantity="3", price="19.99")]))
    assert clean.loc[0, "Revenue"] == pytest.approx(59.97)


def test_revenue_is_rounded_to_cents():
    clean, _ = dp.clean_sales_data(make_raw([row(quantity="3", price="0.333")]))
    assert clean.loc[0, "Revenue"] == pytest.approx(1.00)


def test_types_are_converted(sample_clean):
    assert pd.api.types.is_datetime64_any_dtype(sample_clean["Order_Date"])
    assert pd.api.types.is_integer_dtype(sample_clean["Quantity"])
    assert pd.api.types.is_float_dtype(sample_clean["Unit_Price"])


# ----------------------------- missing values ------------------------------ #


def test_missing_category_and_region_become_unknown_and_are_kept():
    raw = make_raw([row(category="", region=None)])
    clean, report = dp.clean_sales_data(raw)
    assert len(clean) == 1
    assert clean.loc[0, "Category"] == dp.UNKNOWN_LABEL
    assert clean.loc[0, "Region"] == dp.UNKNOWN_LABEL
    assert report.unknown_category_filled == 1
    assert report.unknown_region_filled == 1


@pytest.mark.parametrize(
    "bad_row, expected_reason",
    [
        (row(order_id=""), dp.REASON_ORDER_ID),
        (row(date=None), dp.REASON_DATE),
        (row(date="not-a-date"), dp.REASON_DATE),
        (row(product="  "), dp.REASON_PRODUCT),
        (row(quantity=None), dp.REASON_QTY_INVALID),
        (row(price=""), dp.REASON_PRICE_INVALID),
    ],
)
def test_rows_missing_essential_values_are_rejected_with_reason(bad_row, expected_reason):
    clean, report = dp.clean_sales_data(make_raw([bad_row, row("OK")]))
    assert list(clean["Order_ID"]) == ["OK"]
    assert report.rejected_by_reason == {expected_reason: 1}
    assert len(report.rejected_rows) == 1


def test_whitespace_is_trimmed():
    clean, _ = dp.clean_sales_data(make_raw([row(product="  Pen  ", region=" East ")]))
    assert clean.loc[0, "Product"] == "Pen"
    assert clean.loc[0, "Region"] == "East"


# ----------------------------- invalid numbers ----------------------------- #


@pytest.mark.parametrize(
    "quantity, price, expected_reason",
    [
        ("abc", "5", dp.REASON_QTY_INVALID),
        ("-3", "5", dp.REASON_QTY_NON_POSITIVE),
        ("0", "5", dp.REASON_QTY_NON_POSITIVE),
        ("2.5", "5", dp.REASON_QTY_FRACTION),
        ("inf", "5", dp.REASON_QTY_INVALID),
        ("2", "free", dp.REASON_PRICE_INVALID),
        ("2", "-9.99", dp.REASON_PRICE_NON_POSITIVE),
        ("2", "0", dp.REASON_PRICE_NON_POSITIVE),
    ],
)
def test_invalid_numeric_values_are_rejected_not_silently_changed(quantity, price, expected_reason):
    clean, report = dp.clean_sales_data(make_raw([row(quantity=quantity, price=price)]))
    assert clean.empty
    assert report.rejected_by_reason == {expected_reason: 1}


def test_whole_number_quantity_written_as_float_is_accepted():
    clean, _ = dp.clean_sales_data(make_raw([row(quantity="4.0")]))
    assert clean.loc[0, "Quantity"] == 4


# ----------------------------- duplicates ---------------------------------- #


def test_exact_duplicates_are_removed_once_and_reported():
    raw = make_raw([row("A1"), row("A1"), row("A2")])
    clean, report = dp.clean_sales_data(raw)
    assert list(clean["Order_ID"]) == ["A1", "A2"]
    assert report.exact_duplicates_removed == 1
    assert len(report.duplicate_rows) == 1


def test_same_order_with_different_products_is_not_a_duplicate():
    raw = make_raw([row("A1", product="Pen"), row("A1", product="Desk")])
    clean, report = dp.clean_sales_data(raw)
    assert len(clean) == 2
    assert report.exact_duplicates_removed == 0
    assert report.conflicting_rows_flagged == 0
    # Two line items, but only ONE order.
    assert dp.calculate_kpis(clean)["total_orders"] == 1


def test_conflicting_duplicates_are_kept_and_flagged():
    raw = make_raw([row("A1", quantity="2"), row("A1", quantity="5")])
    clean, report = dp.clean_sales_data(raw)
    assert len(clean) == 2
    assert report.conflicting_rows_flagged == 2


def test_duplicates_are_detected_after_type_conversion():
    # "5" vs "5.0" and padded text describe the same record.
    raw = make_raw([row("A1", price="5"), row(" A1 ", price="5.0")])
    clean, report = dp.clean_sales_data(raw)
    assert len(clean) == 1
    assert report.exact_duplicates_removed == 1


# ----------------------------- validation / loading ------------------------ #


def test_missing_required_column_raises_clear_error():
    raw = make_raw([row()]).drop(columns=["Region"])
    with pytest.raises(dp.DataValidationError, match="Region"):
        dp.clean_sales_data(raw)


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(dp.DataValidationError, match="not found"):
        dp.load_clean_sales_data(tmp_path / "nope.csv")


def test_empty_file_raises_clear_error(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    with pytest.raises(dp.DataValidationError, match="empty"):
        dp.load_clean_sales_data(path)


def test_header_only_file_raises_clear_error(tmp_path):
    path = tmp_path / "header_only.csv"
    path.write_text(",".join(dp.REQUIRED_COLUMNS) + "\n")
    with pytest.raises(dp.DataValidationError, match="no data rows"):
        dp.load_clean_sales_data(path)


def test_file_with_wrong_columns_raises_clear_error(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("a,b\n1,2\n")
    with pytest.raises(dp.DataValidationError, match="missing required column"):
        dp.load_clean_sales_data(path)


def test_file_where_every_row_is_invalid_raises_clear_error(tmp_path):
    path = tmp_path / "all_bad.csv"
    path.write_text(",".join(dp.REQUIRED_COLUMNS) + "\nA1,bad-date,Pen,Office,East,1,5\n")
    with pytest.raises(dp.DataValidationError, match="No valid rows"):
        dp.load_clean_sales_data(path)


def test_load_valid_csv_round_trip(tmp_path):
    path = tmp_path / "ok.csv"
    path.write_text(",".join(dp.REQUIRED_COLUMNS) + "\nA1,2025-01-15,Pen,Office,East,2,5.00\n")
    clean, report = dp.load_clean_sales_data(path)
    assert report.rows_loaded == 1 and report.rows_kept == 1
    assert clean.loc[0, "Revenue"] == pytest.approx(10.0)


# ----------------------------- empty datasets ------------------------------ #


def test_cleaning_an_empty_dataframe_returns_empty_result():
    clean, report = dp.clean_sales_data(make_raw([]))
    assert clean.empty
    assert report.rows_loaded == 0 and report.rows_kept == 0
    assert "Revenue" in clean.columns and "Month" in clean.columns


def test_kpis_on_empty_data_are_zero(sample_clean):
    empty = sample_clean.iloc[0:0]
    assert dp.calculate_kpis(empty) == {
        "total_revenue": 0.0,
        "total_orders": 0,
        "total_units": 0,
        "average_order_value": 0.0,
    }


def test_aggregations_and_insights_handle_empty_data(sample_clean):
    empty = sample_clean.iloc[0:0]
    assert dp.revenue_by(empty, "Product").empty
    assert dp.top_products(empty).empty
    assert dp.monthly_summary(empty).empty
    assert dp.generate_insights(empty) is None


def test_filtering_an_empty_dataframe_does_not_crash(sample_clean):
    empty = sample_clean.iloc[0:0]
    assert dp.filter_sales_data(empty, "2025-01-01", "2025-12-31", regions=["East"]).empty


# ----------------------------- filtering ----------------------------------- #


def test_no_filters_returns_everything(sample_clean):
    assert len(dp.filter_sales_data(sample_clean)) == len(sample_clean)


def test_date_filter_is_inclusive(sample_clean):
    result = dp.filter_sales_data(sample_clean, "2025-01-20", "2025-02-05")
    assert list(result["Order_ID"]) == ["A2", "A3"]


def test_region_category_and_product_filters(sample_clean):
    assert list(dp.filter_sales_data(sample_clean, regions=["East"])["Order_ID"]) == ["A1", "A4"]
    assert list(dp.filter_sales_data(sample_clean, categories=["Furniture"])["Order_ID"]) == ["A2", "A4"]
    assert list(dp.filter_sales_data(sample_clean, products=["Pen"])["Order_ID"]) == ["A1", "A3"]


def test_filters_combine_with_and_logic(sample_clean):
    result = dp.filter_sales_data(
        sample_clean, "2025-01-01", "2025-02-28", regions=["West"], categories=["Office"]
    )
    assert list(result["Order_ID"]) == ["A3"]


def test_empty_selection_matches_nothing(sample_clean):
    assert dp.filter_sales_data(sample_clean, regions=[]).empty


def test_filter_with_no_matches_returns_empty_frame(sample_clean):
    assert dp.filter_sales_data(sample_clean, "2030-01-01", "2030-12-31").empty


def test_start_date_after_end_date_raises(sample_clean):
    with pytest.raises(ValueError, match="Start date"):
        dp.filter_sales_data(sample_clean, "2025-03-01", "2025-01-01")


def test_kpis_follow_the_filtered_data(sample_clean):
    kpis = dp.calculate_kpis(dp.filter_sales_data(sample_clean, regions=["West"]))
    # A2: 1 x 100.00, A3: 10 x 4.50
    assert kpis["total_revenue"] == pytest.approx(145.00)
    assert kpis["total_orders"] == 2
    assert kpis["total_units"] == 11
    assert kpis["average_order_value"] == pytest.approx(72.50)


# ----------------------------- aggregations & insights --------------------- #


def test_monthly_summary_fills_gap_months_with_zero():
    raw = make_raw([row("A1", "2025-01-10"), row("A2", "2025-03-10")])
    clean, _ = dp.clean_sales_data(raw)
    monthly = dp.monthly_summary(clean)
    assert list(monthly["Month"].dt.month) == [1, 2, 3]
    assert monthly.loc[1, "Revenue"] == 0 and monthly.loc[1, "Orders"] == 0


def test_revenue_shares_sum_to_100(sample_clean):
    assert dp.revenue_by(sample_clean, "Region")["Share_Pct"].sum() == pytest.approx(100.0)


def test_top_products_are_ordered_and_limited(sample_clean):
    top = dp.top_products(sample_clean, n=2)
    assert len(top) == 2
    assert top["Revenue"].is_monotonic_decreasing


def test_insights_are_derived_from_data_not_hardcoded(sample_clean):
    insights = dp.generate_insights(sample_clean)
    # Revenue: Pen 10+45=55, Desk 100, Chair 150 -> Chair; Furniture 250 vs Office 55.
    assert insights["top_product"]["Product"] == "Chair"
    assert insights["top_category"]["Category"] == "Furniture"
    assert insights["top_region"]["Region"] == "East"  # 10 + 150 = 160 vs West 145
    assert insights["best_month"]["Month"] == pd.Timestamp("2025-03-01")

    # Filtering changes the answer, proving nothing is hardcoded.
    only_west = dp.generate_insights(dp.filter_sales_data(sample_clean, regions=["West"]))
    assert only_west["top_product"]["Product"] == "Desk"
    assert only_west["region_count"] == 1


def test_csv_export_has_expected_columns_and_dates(sample_clean):
    text = dp.to_csv_bytes(sample_clean).decode("utf-8")
    header = text.splitlines()[0]
    assert header == ",".join(dp.REQUIRED_COLUMNS + ["Revenue"])
    assert "2025-01-10" in text


# ----------------------------- bundled sample dataset ---------------------- #


def test_sample_dataset_is_valid_and_large_enough():
    clean, report = dp.load_clean_sales_data(PROJECT_ROOT / "data" / "sales_data.csv")
    assert len(clean) >= 200
    assert report.rows_rejected == 0 and report.exact_duplicates_removed == 0
    assert clean["Month"].nunique() >= 6
    assert clean["Product"].nunique() >= 5
    assert clean["Category"].nunique() >= 3
    assert clean["Region"].nunique() >= 3


def test_sample_dataset_generator_is_reproducible():
    first = generate_sales_data()
    second = generate_sales_data()
    pd.testing.assert_frame_equal(first, second)
    on_disk = pd.read_csv(PROJECT_ROOT / "data" / "sales_data.csv")
    pd.testing.assert_frame_equal(first, on_disk)
