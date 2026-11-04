from pathlib import Path

import pandas as pd
import pytest

from inventory_analyzer import add_abc_class, run
from sql_report import compare, run_sql
from validation import DataValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------- ABC classification ----------

def abc_input(costs, demands=None):
    demands = demands or [1.0] * len(costs)
    return pd.DataFrame({
        "product_id": [f"P{i}" for i in range(len(costs))],
        "daily_demand": demands,
        "unit_cost": costs,
    })


def test_abc_follows_80_15_5_rule_regardless_of_row_order():
    # values proportional to 70 / 20 / 7 / 3 percent, given in shuffled order
    df = abc_input([0.7, 7.0, 0.3, 2.0])
    result = add_abc_class(df).set_index("product_id")["abc_class"]
    assert result["P1"] == "A"   # 70%
    assert result["P3"] == "A"   # next 20% (value above it is 70%, still under 80%)
    assert result["P0"] == "B"   # value above it is 90%
    assert result["P2"] == "C"   # value above it is 97%


def test_abc_zero_demand_product_is_class_c():
    df = abc_input([5.0, 5.0], demands=[3.0, 0.0])
    result = add_abc_class(df).set_index("product_id")["abc_class"]
    assert result["P0"] == "A"
    assert result["P1"] == "C"


def test_abc_when_nothing_is_consumed_everything_is_c():
    df = abc_input([5.0, 2.0], demands=[0.0, 0.0])
    assert list(add_abc_class(df)["abc_class"]) == ["C", "C"]


# ---------- SQL version matches the Python version ----------

def test_sql_and_python_agree_on_full_dataset(tmp_path):
    path = str(PROJECT_ROOT / "data" / "inventory.csv")
    sql_df = run_sql(path)
    python_df = run(path, str(tmp_path / "report.csv"))
    assert compare(sql_df, python_df) == []
    assert sql_df["est_cost"].sum() == pytest.approx(96376.40)


def test_sql_matches_hand_calculated_products(tmp_path):
    rows = [
        ("10-626-8536", "S", 17, 0, 5.4, 10, 11, 5.0, 50),
        ("49-377-9731", "S", 18, 0, 2.2, 5, 7, 2.0, 20),
        ("70-145-2550", "S", 91, 20, 4.6, 5, 10, 2.4, 20),
        ("29-017-6255", "S", 0, 0, 3.5, 3, 7, 4.6, 10),
        ("11-581-9869", "S", 51, 0, 0.0, 3, 8, 1.5, 10),
    ]
    columns = ["product_id", "supplier", "stock", "on_order", "daily_demand",
               "lead_time_days", "safety_stock", "unit_cost", "moq"]
    csv_path = tmp_path / "five.csv"
    pd.DataFrame(rows, columns=columns).to_csv(csv_path, index=False)

    result = run_sql(str(csv_path)).set_index("product_id")
    assert result.loc["10-626-8536", "status"] == "URGENT"
    assert result.loc["10-626-8536", "order_qty"] == 200
    assert result.loc["49-377-9731", "status"] == "REORDER"
    assert result.loc["49-377-9731", "order_qty"] == 60
    assert result.loc["70-145-2550", "status"] == "OK"
    assert result.loc["70-145-2550", "order_qty"] == 0
    assert result.loc["29-017-6255", "est_cost"] == pytest.approx(552.0)
    assert result.loc["11-581-9869", "status"] == "OK"


def test_sql_report_also_rejects_bad_data():
    with pytest.raises(DataValidationError):
        run_sql(str(PROJECT_ROOT / "tests" / "bad_data" / "negative_stock.csv"))