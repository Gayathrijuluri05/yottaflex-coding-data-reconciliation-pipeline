import pandas as pd

COMPARE_FIELDS = ["customer_id", "order_date", "quantity", "unit_price", "status", "amount"]

def reconcile(source: pd.DataFrame, target: pd.DataFrame, tolerance: float = 0.01):
    src = source.copy()
    tgt = target.copy()
    src["order_id"] = src["order_id"].astype(str)
    tgt["order_id"] = tgt["order_id"].astype(str)
    src = src.drop_duplicates("order_id", keep="first")
    tgt = tgt.drop_duplicates("order_id", keep="first")
    src_keys, tgt_keys = set(src.order_id), set(tgt.order_id)
    key_rows = ([{"order_id": k, "mismatch_type": "source_only"} for k in sorted(src_keys - tgt_keys)] +
                [{"order_id": k, "mismatch_type": "target_only"} for k in sorted(tgt_keys - src_keys)])
    joined = src.merge(tgt, on="order_id", how="inner", suffixes=("_source", "_target"))
    mismatches = []
    for _, row in joined.iterrows():
        for field in COMPARE_FIELDS:
            a, b = row[f"{field}_source"], row[f"{field}_target"]
            if pd.isna(a) and pd.isna(b):
                continue
            if field in ("unit_price", "amount"):
                equal = pd.notna(a) and pd.notna(b) and abs(float(a) - float(b)) <= tolerance
            elif field == "quantity":
                equal = pd.notna(a) and pd.notna(b) and float(a) == float(b)
            else:
                equal = str(a) == str(b)
            if not equal:
                mismatches.append({"order_id": row["order_id"], "field": field,
                                   "source_value": None if pd.isna(a) else a,
                                   "target_value": None if pd.isna(b) else b})
    def aggregates(df):
        return {
            "row_count": int(len(df)),
            "distinct_order_count": int(df.order_id.nunique()) if "order_id" in df else 0,
            "quantity_sum": int(pd.to_numeric(df.quantity, errors="coerce").fillna(0).sum()) if "quantity" in df else 0,
            "amount_sum": round(float(pd.to_numeric(df.amount, errors="coerce").fillna(0).sum()), 2) if "amount" in df else 0.0,
        }
    src_agg, tgt_agg = aggregates(src), aggregates(tgt)
    return {
        "source_aggregates": src_agg,
        "target_aggregates": tgt_agg,
        "key_mismatches": key_rows,
        "field_mismatches": mismatches,
        "row_count_match": src_agg["row_count"] == tgt_agg["row_count"],
        "key_match": len(key_rows) == 0,
        "aggregate_match": src_agg == tgt_agg,
        "field_mismatch_count": len(mismatches),
        "status": "PASS" if not key_rows and not mismatches and src_agg == tgt_agg else "FAIL",
    }
