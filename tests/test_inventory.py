from pathlib import Path

import pandas as pd
import pytest

from inventory_analyzer import calculate_metrics, calculate_orders, classify_status, run
from validation import DataValidationError, validate_inventory

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_df(**overrides):
    """One healthy product. Override any column to build a test case."""
    row = {
        "product_id": "T-001",
        "supplier": "Test Supplier",
        "stock": 100,
        "on_order": 0,
        "daily_demand": 2.0,
        "lead_time_days": 5,
        "safety_stock": 10,
        "unit_cost": 3.0,
        "moq": 10,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def analyze(df):
    """Run the calculation steps (no file reading)."""
    return calculate_orders(classify_status(calculate_metrics(df)))


# ---------- Status rules ----------

def test_stock_well_above_reorder_point_is_ok():
    result = analyze(make_df(stock=100))
    assert result.loc[0, "status"] == "OK"
    assert result.loc[0, "order_qty"] == 0


def test_stock_exactly_at_reorder_point_is_reorder():
    # reorder point = 2.0 * 5 + 10 = 20
    result = analyze(make_df(stock=20))
    assert result.loc[0, "reorder_point"] == 20
    assert result.loc[0, "status"] == "REORDER"


def test_stock_just_above_reorder_point_is_ok():
    result = analyze(make_df(stock=21))
    assert result.loc[0, "status"] == "OK"


def test_stock_below_lead_time_demand_is_urgent():
    # lead-time demand = 2.0 * 5 = 10
    result = analyze(make_df(stock=9))
    assert result.loc[0, "status"] == "URGENT"


def test_stock_exactly_equal_to_lead_time_demand_is_reorder_not_urgent():
    result = analyze(make_df(stock=10))
    assert result.loc[0, "status"] == "REORDER"


def test_zero_stock_with_demand_is_urgent():
    result = analyze(make_df(stock=0))
    assert result.loc[0, "status"] == "URGENT"


def test_on_order_counts_towards_inventory_position():
    # stock alone (5) would be urgent, but 50 on order brings the position to 55
    result = analyze(make_df(stock=5, on_order=50))
    assert result.loc[0, "inventory_position"] == 55
    assert result.loc[0, "status"] == "OK"


# ---------- Order quantity and cost ----------

def test_order_quantity_rounds_up_to_moq():
    # demand 1, lead 7, safety 0, stock 7 -> REORDER, target 30, gap 23, MOQ 10 -> 30
    result = analyze(make_df(stock=7, daily_demand=1.0, lead_time_days=7,
                             safety_stock=0, moq=10))
    assert result.loc[0, "gap"] == 23
    assert result.loc[0, "order_qty"] == 30


def test_gap_that_is_exact_multiple_of_moq_is_not_rounded_up():
    # demand 1, lead 10, safety 0, stock 10 -> gap 20, MOQ 10 -> 20
    result = analyze(make_df(stock=10, daily_demand=1.0, lead_time_days=10,
                             safety_stock=0, moq=10))
    assert result.loc[0, "gap"] == 20
    assert result.loc[0, "order_qty"] == 20


def test_ok_product_gets_no_order_even_if_gap_is_positive():
    # position 111 is above reorder point 33, but below the 148 target
    result = analyze(make_df(stock=91, on_order=20, daily_demand=4.6,
                             lead_time_days=5, safety_stock=10, moq=20))
    assert result.loc[0, "gap"] == 37
    assert result.loc[0, "status"] == "OK"
    assert result.loc[0, "order_qty"] == 0


def test_estimated_cost_is_quantity_times_unit_cost():
    result = analyze(make_df(stock=7, daily_demand=1.0, lead_time_days=7,
                             safety_stock=0, moq=10, unit_cost=2.5))
    assert result.loc[0, "est_cost"] == 75.0


# ---------- Zero demand rule ----------

def test_zero_demand_days_of_cover_is_empty_not_infinite():
    result = analyze(make_df(daily_demand=0, stock=51, safety_stock=8))
    assert pd.isna(result.loc[0, "days_of_cover"])


def test_zero_demand_with_stock_above_safety_stock_is_ok_with_no_order():
    result = analyze(make_df(daily_demand=0, stock=51, safety_stock=8))
    assert result.loc[0, "reorder_point"] == 8
    assert result.loc[0, "status"] == "OK"
    assert result.loc[0, "order_qty"] == 0


def test_zero_demand_below_safety_stock_orders_up_to_safety_stock():
    # stock 3, safety stock 5 -> gap 2, rounded up to MOQ 10
    result = analyze(make_df(daily_demand=0, stock=3, safety_stock=5, moq=10))
    assert result.loc[0, "status"] == "REORDER"
    assert result.loc[0, "order_qty"] == 10


# ---------- Hand-calculated answer key (from the Excel sheet) ----------

ANSWER_KEY = [
    # id, stock, on_order, demand, lead, safety, cost, moq,
    #   position, ltd, rop, target, status, gap, qty, est_cost
    ("10-626-8536", 17, 0, 5.4, 10, 11, 5.0, 50, 17, 54, 65, 173, "URGENT", 156, 200, 1000.0),
    ("49-377-9731", 18, 0, 2.2, 5, 7, 2.0, 20, 18, 11, 18, 73, "REORDER", 55, 60, 120.0),
    ("70-145-2550", 91, 20, 4.6, 5, 10, 2.4, 20, 111, 23, 33, 148, "OK", 37, 0, 0.0),
    ("29-017-6255", 0, 0, 3.5, 3, 7, 4.6, 10, 0, 10.5, 17.5, 112, "URGENT", 112, 120, 552.0),
    ("11-581-9869", 51, 0, 0.0, 3, 8, 1.5, 10, 51, 0, 8, 8, "OK", -43, 0, 0.0),
]


@pytest.mark.parametrize(
    "pid, stock, on_order, demand, lead, safety, cost, moq,"
    "position, ltd, rop, target, status, gap, qty, est_cost",
    ANSWER_KEY,
)
def test_matches_hand_calculated_answer_key(pid, stock, on_order, demand, lead, safety,
                                            cost, moq, position, ltd, rop, target,
                                            status, gap, qty, est_cost):
    df = make_df(product_id=pid, stock=stock, on_order=on_order, daily_demand=demand,
                 lead_time_days=lead, safety_stock=safety, unit_cost=cost, moq=moq)
    r = analyze(df).iloc[0]
    assert r["inventory_position"] == pytest.approx(position)
    assert r["lead_time_demand"] == pytest.approx(ltd)
    assert r["reorder_point"] == pytest.approx(rop)
    assert r["target_stock"] == pytest.approx(target)
    assert r["status"] == status
    assert r["gap"] == pytest.approx(gap)
    assert r["order_qty"] == qty
    assert r["est_cost"] == pytest.approx(est_cost)


# ---------- Validation: good and bad data ----------

def test_valid_data_passes_validation():
    validate_inventory(make_df())


def test_missing_required_column_is_rejected():
    with pytest.raises(DataValidationError, match="Missing required column"):
        validate_inventory(make_df().drop(columns=["moq"]))


def test_negative_stock_is_rejected():
    with pytest.raises(DataValidationError, match="Negative values in 'stock'"):
        validate_inventory(make_df(stock=-5))


def test_negative_demand_is_rejected():
    with pytest.raises(DataValidationError, match="Negative values in 'daily_demand'"):
        validate_inventory(make_df(daily_demand=-1))


def test_text_in_number_column_is_rejected():
    with pytest.raises(DataValidationError, match="Non-numeric values in 'lead_time_days'"):
        validate_inventory(make_df(lead_time_days="7 days"))


def test_empty_number_is_rejected():
    with pytest.raises(DataValidationError, match="Empty values in 'on_order'"):
        validate_inventory(make_df(on_order=None))


def test_zero_moq_is_rejected():
    with pytest.raises(DataValidationError, match="'moq' must be greater than 0"):
        validate_inventory(make_df(moq=0))


def test_negative_unit_cost_is_rejected():
    with pytest.raises(DataValidationError, match="'unit_cost' must be greater than 0"):
        validate_inventory(make_df(unit_cost=-2))


def test_duplicate_product_id_is_rejected():
    df = pd.concat([make_df(), make_df()], ignore_index=True)
    with pytest.raises(DataValidationError, match="Duplicate product_id"):
        validate_inventory(df)


def test_missing_supplier_is_rejected():
    with pytest.raises(DataValidationError, match="Missing supplier"):
        validate_inventory(make_df(supplier=""))


def test_file_with_no_rows_is_rejected():
    with pytest.raises(DataValidationError, match="no data rows"):
        validate_inventory(make_df().iloc[0:0])


def test_all_problems_are_reported_together():
    df = make_df(stock=-1, moq=0)
    with pytest.raises(DataValidationError) as error:
        validate_inventory(df)
    assert "'stock'" in str(error.value)
    assert "'moq'" in str(error.value)


@pytest.mark.parametrize("path", sorted((PROJECT_ROOT / "tests" / "bad_data").glob("*.csv")))
def test_every_bad_sample_file_is_rejected(path, tmp_path):
    with pytest.raises(DataValidationError):
        run(str(path), str(tmp_path / "report.csv"))
    assert not (tmp_path / "report.csv").exists()


# ---------- Full pipeline on the real dataset ----------

def test_full_dataset_status_counts_and_total_cost(tmp_path):
    report = run(str(PROJECT_ROOT / "data" / "inventory.csv"), str(tmp_path / "report.csv"))
    counts = report["status"].value_counts()
    assert len(report) == 990
    assert counts["OK"] == 850
    assert counts["URGENT"] == 83
    assert counts["REORDER"] == 57
    assert report["est_cost"].sum() == pytest.approx(96376.40)


def test_report_is_sorted_urgent_first_and_writes_na_for_zero_demand(tmp_path):
    out = tmp_path / "report.csv"
    report = run(str(PROJECT_ROOT / "data" / "inventory.csv"), str(out))
    assert report.iloc[0]["status"] == "URGENT"
    assert report.iloc[-1]["status"] == "OK"
    assert "n/a" in out.read_text()