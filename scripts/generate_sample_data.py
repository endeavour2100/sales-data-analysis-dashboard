"""Generate the SYNTHETIC sample dataset used by the dashboard.

Every record is randomly generated with a fixed seed. None of it comes from
real business transactions.

Usage (from the project root):
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
NUM_ORDERS = 320
YEAR = 2025
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sales_data.csv"

# (product, category, typical unit price, relative popularity)
PRODUCTS = [
    ("Wireless Mouse", "Electronics", 24.99, 9),
    ("Mechanical Keyboard", "Electronics", 79.99, 6),
    ("Bluetooth Speaker", "Electronics", 59.99, 6),
    ("27-inch Monitor", "Electronics", 219.00, 3),
    ("Ergonomic Chair", "Furniture", 189.00, 3),
    ("Standing Desk", "Furniture", 349.00, 2),
    ("Bookshelf", "Furniture", 99.00, 3),
    ("Notebook Pack", "Office Supplies", 12.50, 12),
    ("Gel Pen Set", "Office Supplies", 8.99, 12),
    ("Desk Organizer", "Office Supplies", 22.00, 7),
    ("Laptop Backpack", "Accessories", 54.00, 5),
    ("USB-C Hub", "Accessories", 39.00, 7),
]
REGIONS = ["North", "South", "East", "West"]
REGION_WEIGHTS = [0.20, 0.25, 0.23, 0.32]
# Mild seasonality: spring bump, strong November/December.
MONTH_WEIGHTS = [6, 6, 8, 7, 7, 7, 6, 7, 8, 9, 12, 14]


def max_quantity_for(price: float) -> int:
    """Cheaper items are bought in larger quantities."""
    if price < 30:
        return 8
    if price < 100:
        return 5
    return 2


def generate_sales_data(seed: int = SEED, num_orders: int = NUM_ORDERS) -> pd.DataFrame:
    """Build the synthetic dataset. The same seed always gives the same data."""
    rng = np.random.default_rng(seed)

    product_probs = np.array([p[3] for p in PRODUCTS], dtype=float)
    product_probs /= product_probs.sum()
    month_probs = np.array(MONTH_WEIGHTS, dtype=float)
    month_probs /= month_probs.sum()

    product_idx = rng.choice(len(PRODUCTS), size=num_orders, p=product_probs)
    months = rng.choice(np.arange(1, 13), size=num_orders, p=month_probs)
    regions = rng.choice(REGIONS, size=num_orders, p=REGION_WEIGHTS)

    rows = []
    for i in range(num_orders):
        product, category, base_price, _ = PRODUCTS[product_idx[i]]
        month = int(months[i])
        day = int(rng.integers(1, calendar.monthrange(YEAR, month)[1] + 1))
        # Small price variation to mimic discounts and price changes.
        unit_price = round(float(base_price * rng.uniform(0.92, 1.08)), 2)
        quantity = int(rng.integers(1, max_quantity_for(base_price) + 1))
        rows.append(
            {
                "Order_Date": pd.Timestamp(YEAR, month, day).strftime("%Y-%m-%d"),
                "Product": product,
                "Category": category,
                "Region": str(regions[i]),
                "Quantity": quantity,
                "Unit_Price": unit_price,
            }
        )

    df = pd.DataFrame(rows).sort_values("Order_Date", kind="stable").reset_index(drop=True)
    df.insert(0, "Order_ID", [f"ORD-{1001 + i}" for i in range(len(df))])
    return df


def main() -> None:
    df = generate_sales_data()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} synthetic records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
