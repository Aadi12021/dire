import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.ingest import ingest, load, REQUIRED_COLUMNS

FIXTURE = Path(__file__).parent.parent / "data" / "fixture.csv"

FULL_ROW = {
    "Date": "2024-01-01",
    "Store ID": "S01",
    "Product ID": "P001",
    "Category": "Electronics",
    "Region": "North",
    "Inventory Level": 200,
    "Units Sold": 30,
    "Units Ordered": 50,
    "Demand Forecast": 35,
    "Price": 100.0,
    "Weather Condition": "Sunny",
    "Holiday/Promotion": 0,
}


# --- load() ------------------------------------------------------------------

def test_load_returns_dataframe():
    df = load(FIXTURE)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_load_missing_file():
    with pytest.raises(FileNotFoundError, match="Dataset not found"):
        load("nonexistent.csv")


def test_load_wrong_extension(tmp_path):
    bad = tmp_path / "data.xlsx"
    bad.write_text("x")
    with pytest.raises(ValueError, match=r"Expected a \.csv"):
        load(bad)


# --- ingest() happy path -----------------------------------------------------

def test_ingest_renames_columns():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert set(["sku_id", "category", "current_price", "units_on_hand", "units_sold", "date"]).issubset(df.columns)


def test_ingest_drops_extra_columns():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert "Store ID" not in df.columns
    assert "Weather Condition" not in df.columns


def test_ingest_derives_cost():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert df["cost"].iloc[0] == pytest.approx(45.0)


def test_ingest_derives_original_price():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert df["original_price"].iloc[0] == pytest.approx(130.0)


def test_ingest_esg_defaults_to_false():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert df["esg_reporting_pressure"].iloc[0] == False  # noqa: E712 — np.False_ != `is False`


def test_ingest_date_is_datetime():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_ingest_sku_id_is_string():
    df = ingest(pd.DataFrame([FULL_ROW]))
    assert pd.api.types.is_string_dtype(df["sku_id"])


# --- ingest() error handling -------------------------------------------------

def test_ingest_missing_columns_raises():
    bad = pd.DataFrame([{"Product ID": "P001", "Price": 10.0}])
    with pytest.raises(ValueError, match="Missing required column"):
        ingest(bad)


def test_ingest_error_lists_missing_columns():
    bad = pd.DataFrame([{"Product ID": "P001", "Price": 10.0}])
    with pytest.raises(ValueError) as exc:
        ingest(bad)
    msg = str(exc.value)
    assert "Category" in msg
    assert "Inventory Level" in msg


def test_ingest_error_lists_available_columns():
    bad = pd.DataFrame([{"Product ID": "P001", "wrong_col": "x"}])
    with pytest.raises(ValueError) as exc:
        ingest(bad)
    assert "wrong_col" in str(exc.value)


# --- round-trip on the fixture -----------------------------------------------

def test_fixture_round_trip():
    df = ingest(load(FIXTURE))
    assert len(df) > 0
    assert df["cost"].notna().all()
    assert df["original_price"].notna().all()
    assert (df["esg_reporting_pressure"] == False).all()
