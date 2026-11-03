import pandas as pd

REQUIRED_COLUMNS = [
    "product_id", "supplier", "stock", "on_order", "daily_demand",
    "lead_time_days", "safety_stock", "unit_cost", "moq",
]
NUMERIC_COLUMNS = [
    "stock", "on_order", "daily_demand", "lead_time_days",
    "safety_stock", "unit_cost", "moq",
]
NON_NEGATIVE_COLUMNS = ["stock", "on_order", "daily_demand", "lead_time_days", "safety_stock"]
POSITIVE_COLUMNS = ["unit_cost", "moq"]

MAX_EXAMPLES = 5


class DataValidationError(Exception):
    """Raised when the input data cannot be trusted to produce a correct report."""


def _where(df, mask):
    """Describe the first few bad rows, using CSV row numbers (header is row 1)."""
    bad = df[mask]
    parts = []
    for index, row in bad.head(MAX_EXAMPLES).iterrows():
        parts.append(f"row {index + 2} (product_id {row['product_id']})")
    text = ", ".join(parts)
    if len(bad) > MAX_EXAMPLES:
        text += f" and {len(bad) - MAX_EXAMPLES} more"
    return text


def validate_inventory(df):
    """Check the inventory table. Raises DataValidationError listing every problem found."""
    # 1. Required columns must exist. Nothing else can be checked without them.
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_columns:
        raise DataValidationError("Missing required column(s): " + ", ".join(missing_columns))

    if df.empty:
        raise DataValidationError("The file has no data rows.")

    errors = []

    # 2. product_id: present and unique
    blank_id = df["product_id"].isna() | (df["product_id"].astype(str).str.strip() == "")
    if blank_id.any():
        errors.append("Missing product_id at " + _where(df, blank_id))
    duplicated = df["product_id"].duplicated(keep=False) & ~blank_id
    if duplicated.any():
        ids = df.loc[duplicated, "product_id"].unique()[:MAX_EXAMPLES]
        errors.append("Duplicate product_id: " + ", ".join(str(i) for i in ids))

    # 3. supplier: present
    blank_supplier = df["supplier"].isna() | (df["supplier"].astype(str).str.strip() == "")
    if blank_supplier.any():
        errors.append("Missing supplier at " + _where(df, blank_supplier))

    # 4. numeric columns: no blanks, no text, no negatives, positive where required
    numbers = {}
    for col in NUMERIC_COLUMNS:
        original = df[col]
        converted = pd.to_numeric(original, errors="coerce")
        blank = original.isna()
        not_a_number = converted.isna() & ~blank
        if blank.any():
            errors.append(f"Empty values in '{col}' at " + _where(df, blank))
        if not_a_number.any():
            example = original[not_a_number].iloc[0]
            errors.append(
                f"Non-numeric values in '{col}' (for example '{example}') at "
                + _where(df, not_a_number)
            )
        numbers[col] = converted

    for col in NON_NEGATIVE_COLUMNS:
        negative = numbers[col] < 0
        if negative.any():
            errors.append(f"Negative values in '{col}' at " + _where(df, negative))

    for col in POSITIVE_COLUMNS:
        not_positive = numbers[col] <= 0
        if not_positive.any():
            errors.append(f"'{col}' must be greater than 0, found problems at " + _where(df, not_positive))

    if errors:
        raise DataValidationError("\n".join("- " + e for e in errors))