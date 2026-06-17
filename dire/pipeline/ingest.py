import pandas as pd
from pathlib import Path

from config import COST_MULTIPLIER, ORIGINAL_PRICE_MULTIPLIER

# Kaggle column → DIRE schema field
COLUMN_MAP: dict[str, str] = {
    "Product ID": "sku_id",
    "Category": "category",
    "Price": "current_price",
    "Inventory Level": "units_on_hand",
    "Units Sold": "units_sold",
    "Date": "date",
    "Store ID": "store_id",   # needed for Stage 2 redistribution
}

REQUIRED_COLUMNS: list[str] = [
    "Product ID", "Category", "Price", "Inventory Level", "Units Sold", "Date",
]  # Store ID is optional — redistribution is skipped if absent


def load(path: str | Path) -> pd.DataFrame:
    """Read a CSV file and return a raw DataFrame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a .csv file, got: {path.suffix!r}")
    return pd.read_csv(path)


def ingest(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Validate, rename, and enrich a raw Kaggle retail DataFrame.

    Returns a DataFrame with the DIRE schema:
        sku_id, category, current_price, units_on_hand, units_sold, date,
        cost, original_price, esg_reporting_pressure
    """
    _validate_columns(df_raw)

    available_cols = [c for c in COLUMN_MAP if c in df_raw.columns]
    df = df_raw[available_cols].copy()
    df = df.rename(columns=COLUMN_MAP)

    df = _coerce_types(df)
    df = _derive_fields(df)

    return df


# --- helpers -----------------------------------------------------------------

def _validate_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if not missing:
        return

    available = sorted(df.columns.tolist())
    raise ValueError(
        f"Missing required column(s): {missing}\n"
        f"Columns found in file: {available}\n"
        "Check that you uploaded the Retail Store Inventory Forecasting dataset."
    )


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ("current_price", "units_on_hand", "units_sold"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["sku_id"] = df["sku_id"].astype(str)
    df["category"] = df["category"].astype(str)

    return df


def _derive_fields(df: pd.DataFrame) -> pd.DataFrame:
    df["cost"] = (df["current_price"] * COST_MULTIPLIER).round(2)
    df["original_price"] = (df["current_price"] * ORIGINAL_PRICE_MULTIPLIER).round(2)
    df["esg_reporting_pressure"] = False
    return df
