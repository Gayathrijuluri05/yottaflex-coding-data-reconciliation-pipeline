from pathlib import Path
import pandas as pd

EXPECTED_COLUMNS = ["order_id", "customer_id", "order_date", "quantity", "unit_price", "status"]

def read_orders(path: str | Path) -> pd.DataFrame:
    """Read CSV as strings so validation, not pandas inference, controls parsing."""
    df = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing = sorted(set(EXPECTED_COLUMNS) - set(df.columns))
    extra = sorted(set(df.columns) - set(EXPECTED_COLUMNS))
    if missing or extra:
        raise ValueError(f"Schema mismatch; missing={missing}, unexpected={extra}")
    return df[EXPECTED_COLUMNS].copy()
