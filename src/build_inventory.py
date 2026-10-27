import numpy as np
import pandas as pd

rng = np.random.default_rng(42)  # fixed seed = same result every run

df = pd.read_csv("data/products.csv")

# 1. Clean up and rename existing columns
df["category"] = df["category"].fillna("Uncategorized")
df = df.rename(columns={
    "current_stock": "stock",
    "lead_time": "lead_time_days",
    "reorder_level": "reorder_level_given",
})
df = df.drop(columns=["initial_stock"])

# 2. Suppliers: 2 per category, each with its own lead time and MOQ
suppliers = {
    "Fruits & Vegetables": [("FreshFarm Co", 3, 10), ("GreenValley Produce", 5, 20)],
    "Dairy":               [("DairyDirect", 2, 12), ("MilkWay Foods", 4, 24)],
    "Grains & Pulses":     [("AgriGrain Ltd", 10, 50), ("PulseTrade", 14, 50)],
    "Seafood":             [("OceanCatch", 4, 10), ("BlueWave Seafood", 7, 20)],
    "Oils & Fats":         [("PureOil Supply", 8, 24), ("GoldPress Oils", 12, 48)],
    "Beverages":           [("DrinkHub", 6, 24), ("AquaFresh", 9, 36)],
    "Bakery":              [("BakeHouse", 2, 12), ("CrustMasters", 3, 20)],
    "Uncategorized":       [("General Supplies", 7, 10), ("General Supplies", 7, 10)],
}

pick = rng.integers(0, 2, size=len(df))
df["supplier"] = [suppliers[c][p][0] for c, p in zip(df["category"], pick)]
df["lead_time_days"] = [suppliers[c][p][1] for c, p in zip(df["category"], pick)]
df["moq"] = [suppliers[c][p][2] for c, p in zip(df["category"], pick)]

# 3. Demand and safety stock
df["daily_demand"] = rng.uniform(0.5, 6.0, size=len(df)).round(1)
df["safety_stock"] = np.ceil(df["daily_demand"] * rng.integers(1, 4, size=len(df))).astype(int)

# 4. On order: 70% have nothing on order, the rest have 1-3 MOQ batches coming
has_order = rng.random(len(df)) > 0.70
df["on_order"] = np.where(has_order, df["moq"] * rng.integers(1, 4, size=len(df)), 0)

# 5. Deliberate edge cases for testing later
df.loc[0:2, ["stock", "on_order"]] = 0      # zero stock
df.loc[3:4, "daily_demand"] = 0             # zero demand

# 6. Product names
df["product_name"] = df["category"].str.split().str[0] + " item " + (df.index + 1).astype(str).str.zfill(3)

cols = ["product_id", "product_name", "category", "supplier", "stock", "on_order",
        "daily_demand", "lead_time_days", "safety_stock", "unit_cost", "moq",
        "reorder_level_given", "expiration_date"]
df[cols].to_csv("data/inventory.csv", index=False)
print(df[cols].head(10).to_string())
print(df.shape)