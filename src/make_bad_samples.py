import os

import pandas as pd

os.makedirs("tests/bad_data", exist_ok=True)
good = pd.read_csv("data/inventory.csv").head(20)

# 1. A required column is missing
good.drop(columns=["moq"]).to_csv("tests/bad_data/missing_column.csv", index=False)

# 2. Negative stock
bad = good.copy()
bad.loc[2, "stock"] = -5
bad.to_csv("tests/bad_data/negative_stock.csv", index=False)

# 3. Text instead of a number in lead time
bad = good.copy()
bad["lead_time_days"] = bad["lead_time_days"].astype(object)
bad.loc[4, "lead_time_days"] = "7 days"
bad.to_csv("tests/bad_data/text_lead_time.csv", index=False)

# 4. Duplicate product_id
bad = pd.concat([good, good.head(1)], ignore_index=True)
bad.to_csv("tests/bad_data/duplicate_id.csv", index=False)

# 5. Missing supplier
bad = good.copy()
bad.loc[6, "supplier"] = ""
bad.to_csv("tests/bad_data/missing_supplier.csv", index=False)

# 6. Empty on_order, zero MOQ and a negative cost
bad = good.copy()
bad.loc[1, "on_order"] = None
bad.loc[3, "moq"] = 0
bad.loc[5, "unit_cost"] = -2
bad.to_csv("tests/bad_data/blank_and_invalid_numbers.csv", index=False)

print("Created 6 bad sample files in tests/bad_data/")