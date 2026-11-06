import pandas as pd

def normalize_target(df: pd.DataFrame) -> pd.DataFrame:
    """Parse target values using the same deterministic business representation."""
    if df.empty:
        return pd.DataFrame(columns=["order_id", "customer_id", "order_date", "quantity", "unit_price", "status", "amount"])
    out = df.copy()
    out["order_id"] = out["order_id"].astype(str).str.strip()
    out["customer_id"] = out["customer_id"].astype(str).str.strip()
    out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce")
    out["unit_price"] = pd.to_numeric(out["unit_price"], errors="coerce").round(2)
    out["status"] = out["status"].astype(str).str.strip().str.upper()
    out["amount"] = (out["quantity"] * out["unit_price"]).round(2)
    return out[["order_id", "customer_id", "order_date", "quantity", "unit_price", "status", "amount"]]
