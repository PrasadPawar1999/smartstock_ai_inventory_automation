import sqlite3
import sys
from pathlib import Path

import pandas as pd

from inventory_analyzer import run
from validation import validate_inventory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_FILE = PROJECT_ROOT / "sql" / "reorder_report.sql"

COMPARE_TEXT = ["status", "abc_class"]
COMPARE_NUMBERS = ["inventory_position", "lead_time_demand", "reorder_point",
                   "target_stock", "gap", "order_qty", "est_cost", "annual_value"]


def run_sql(input_path):
    """Load the CSV into an in-memory SQLite database and run the reorder query."""
    df = pd.read_csv(input_path)
    validate_inventory(df)
    connection = sqlite3.connect(":memory:")
    try:
        df.to_sql("inventory", connection, index=False)
        return pd.read_sql_query(SQL_FILE.read_text(), connection)
    finally:
        connection.close()


def compare(sql_df, python_df):
    """Return a list of differences between the SQL result and the Python report."""
    merged = sql_df.merge(python_df, on="product_id", suffixes=("_sql", "_py"))
    problems = []
    if len(sql_df) != len(python_df) or len(merged) != len(python_df):
        problems.append(f"Row counts differ: SQL {len(sql_df)}, Python {len(python_df)}, matched {len(merged)}")
    for col in COMPARE_TEXT:
        different = merged[merged[f"{col}_sql"] != merged[f"{col}_py"]]
        if len(different):
            problems.append(f"{col}: {len(different)} rows differ")
    for col in COMPARE_NUMBERS:
        gap = (merged[f"{col}_sql"] - merged[f"{col}_py"]).abs()
        different = merged[gap > 0.005]
        if len(different):
            problems.append(f"{col}: {len(different)} rows differ")
    return problems


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else str(PROJECT_ROOT / "data" / "inventory.csv")
    sql_df = run_sql(input_path)
    sql_df.to_csv(PROJECT_ROOT / "reports" / "reorder_report_sql.csv", index=False)

    python_df = run(input_path, str(PROJECT_ROOT / "reports" / "reorder_report.csv"))
    problems = compare(sql_df, python_df)

    print("SQL status counts:")
    print(sql_df["status"].value_counts())
    print("SQL total estimated purchase cost:", round(sql_df["est_cost"].sum(), 2))
    if problems:
        print("MISMATCH between SQL and Python:")
        for p in problems:
            print("-", p)
        sys.exit(1)
    print(f"MATCH: SQL and Python agree on all {len(sql_df)} products.")