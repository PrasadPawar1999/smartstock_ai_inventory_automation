import sys

import numpy as np
import pandas as pd

from validation import DataValidationError, validate_inventory

PLANNING_DAYS = 30  # target stock covers this many days of demand


def load_data(path):
    """Read the inventory CSV into a DataFrame."""
    return pd.read_csv(path)


def calculate_metrics(df):
    """Add position, lead-time demand, reorder point, target stock and days of cover."""
    df = df.copy()
    df["inventory_position"] = df["stock"] + df["on_order"]
    df["lead_time_demand"] = (df["daily_demand"] * df["lead_time_days"]).round(2)
    df["reorder_point"] = (df["lead_time_demand"] + df["safety_stock"]).round(2)
    df["target_stock"] = (df["daily_demand"] * PLANNING_DAYS + df["safety_stock"]).round(2)

    # Days of cover: stock / daily demand. Zero demand has no valid answer -> empty (NaN)
    demand = df["daily_demand"].replace(0, np.nan)
    df["days_of_cover"] = (df["stock"] / demand).round(2)
    return df


def classify_status(df):
    """Label each product URGENT, REORDER or OK."""
    df = df.copy()
    is_urgent = df["inventory_position"] < df["lead_time_demand"]
    is_reorder = (df["inventory_position"] <= df["reorder_point"]) & ~is_urgent
    df["status"] = np.select([is_urgent, is_reorder], ["URGENT", "REORDER"], default="OK")
    return df


def calculate_orders(df):
    """Work out the gap, MOQ-rounded order quantity and estimated cost."""
    df = df.copy()
    df["gap"] = (df["target_stock"] - df["inventory_position"]).round(2)
    needs_order = (df["status"] != "OK") & (df["gap"] > 0)
    batches = np.ceil(df["gap"] / df["moq"])
    df["order_qty"] = np.where(needs_order, batches * df["moq"], 0).astype(int)
    df["est_cost"] = (df["order_qty"] * df["unit_cost"]).round(2)
    return df


def add_abc_class(df):
    """ABC classification by annual consumption value (daily demand x 365 x unit cost).

    A = products making up the first 80% of total value, B = the next 15%, C = the rest.
    A product is A if the value ranked above it is still under 80% of the total.
    """
    df = df.copy()
    df["annual_value"] = df["daily_demand"] * 365 * df["unit_cost"]

    ranked = df.sort_values(["annual_value", "product_id"], ascending=[False, True])
    total = ranked["annual_value"].sum()
    if total == 0:
        df["abc_class"] = "C"
        return df

    share_before = (ranked["annual_value"].cumsum() - ranked["annual_value"]) / total
    ranked["abc_class"] = np.select([share_before < 0.80, share_before < 0.95], ["A", "B"], default="C")
    df["abc_class"] = ranked["abc_class"]  # lines up by row index
    return df


def sort_by_priority(df):
    """URGENT first, then REORDER, then OK. Within a status, least days of cover first."""
    rank = {"URGENT": 0, "REORDER": 1, "OK": 2}
    df = df.copy()
    df["_rank"] = df["status"].map(rank)
    df = df.sort_values(["_rank", "days_of_cover"], na_position="last")
    return df.drop(columns="_rank")


def save_report(df, path):
    """Write the report to CSV. Empty days_of_cover is written as n/a."""
    df.to_csv(path, index=False, na_rep="n/a")


def run(input_path="data/inventory.csv", output_path="reports/reorder_report.csv"):
    df = load_data(input_path)
    validate_inventory(df)
    df = calculate_metrics(df)
    df = classify_status(df)
    df = calculate_orders(df)
    df = add_abc_class(df)
    df = sort_by_priority(df)
    save_report(df, output_path)
    return df


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "data/inventory.csv"
    try:
        report = run(input_path)
    except FileNotFoundError:
        print(f"ERROR: input file not found: {input_path}")
        sys.exit(1)
    except DataValidationError as error:
        print("DATA VALIDATION FAILED - no report was written.")
        print(error)
        sys.exit(1)

    print(report["status"].value_counts())
    print("Total estimated purchase cost:", round(report["est_cost"].sum(), 2))