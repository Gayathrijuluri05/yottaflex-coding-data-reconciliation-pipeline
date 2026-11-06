import argparse
from pathlib import Path
import numpy as np
import pandas as pd

STATUSES = ["NEW", "PAID", "SHIPPED", "CANCELLED"]

def generate(rows=100, seed=42, output="data/sample"):
    rng = np.random.default_rng(seed)
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    n = rows
    ids = [f"ORD-{i:07d}" for i in range(1, n + 1)]
    source = pd.DataFrame({
        "order_id": ids,
        "customer_id": [f"CUST-{x:05d}" for x in rng.integers(1, max(2, n // 2 + 2), n)],
        "order_date": pd.to_datetime("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D"),
        "quantity": rng.integers(1, 15, n),
        "unit_price": np.round(rng.uniform(5, 500, n), 2),
        "status": rng.choice(STATUSES, n),
    })
    source["order_date"] = source["order_date"].dt.strftime("%Y-%m-%d")
    target = source.copy()
    # Deliberate, labelled reconciliation differences (kept out of input labels).
    if n >= 5:
        target.loc[1, "status"] = "PAID" if target.loc[1, "status"] != "PAID" else "NEW"
        target.loc[2, "unit_price"] = round(float(target.loc[2, "unit_price"]) + 3.25, 2)
        target = target.drop(index=3)
        extra = source.iloc[[4]].copy()
        extra["order_id"] = "ORD-9999999"
        target = pd.concat([target, extra], ignore_index=True)
    # Deliberately invalid source records to exercise quarantine.
    if n >= 10:
        bad = source.iloc[[0]].copy()
        bad["order_id"] = "ORD-BAD0001"
        bad["quantity"] = 0
        source = pd.concat([source, bad], ignore_index=True)
        null_row = source.iloc[[1]].copy()
        null_row["order_id"] = "ORD-BAD0002"
        null_row["customer_id"] = ""
        source = pd.concat([source, null_row], ignore_index=True)
    source.to_csv(out / "source_orders.csv", index=False)
    target.to_csv(out / "target_orders.csv", index=False)
    # Expected labels are separate from the actual input data.
    labels = {
        "purpose": "Synthetic test labels; not pipeline input",
        "expected_source_invalid_order_ids": ["ORD-BAD0001", "ORD-BAD0002"] if n >= 10 else [],
        "expected_target_missing_key_count": 1 if n >= 5 else 0,
        "expected_target_extra_key_count": 1 if n >= 5 else 0,
        "expected_field_mismatch_orders": ["ORD-0000002", "ORD-0000003"] if n >= 5 else [],
    }
    (out / "expected_labels.json").write_text(pd.Series(labels).to_json(indent=2), encoding="utf-8")
    print(f"Generated {len(source)} source and {len(target)} target rows in {out}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="data/sample")
    a = p.parse_args()
    generate(a.rows, a.seed, a.output)
