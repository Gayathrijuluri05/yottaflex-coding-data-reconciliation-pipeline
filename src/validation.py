from datetime import date, timedelta
import pandas as pd
import re

ALLOWED_STATUSES = {"NEW", "PAID", "SHIPPED", "CANCELLED"}

def validate_orders(df: pd.DataFrame, run_date: date | None = None):
    """Return (valid, rejected). First valid occurrence of a business key wins."""
    run_date = run_date or date.today()
    valid_rows, rejected_rows = [], []
    seen = set()
    for row_num, row in df.iterrows():
        rec = row.to_dict()
        reasons = []
        for field in ("order_id", "customer_id", "order_date", "quantity", "unit_price", "status"):
            if str(rec.get(field, "")).strip() == "":
                reasons.append(f"missing_required:{field}")
        order_id = str(rec.get("order_id", "")).strip()
        customer_id = str(rec.get("customer_id", "")).strip()
        if order_id and order_id in seen:
            reasons.append("duplicate_order_id")
        if order_id:
            seen.add(order_id)
        if customer_id and not re.fullmatch(r"CUST-\d{5}", customer_id):
            reasons.append("invalid_customer_id_format")
        try:
            order_date = pd.to_datetime(rec.get("order_date"), format="%Y-%m-%d", errors="raise").date()
            if order_date > run_date + timedelta(days=30):
                reasons.append("order_date_too_far_in_future")
        except Exception:
            reasons.append("invalid_order_date")
            order_date = None
        try:
            quantity = int(rec.get("quantity"))
            if quantity < 1 or quantity > 10000:
                reasons.append("quantity_out_of_range")
        except Exception:
            reasons.append("invalid_quantity")
            quantity = None
        try:
            unit_price = float(rec.get("unit_price"))
            if not (0 <= unit_price <= 1_000_000):
                reasons.append("unit_price_out_of_range")
        except Exception:
            reasons.append("invalid_unit_price")
            unit_price = None
        status = str(rec.get("status", "")).strip().upper()
        if status and status not in ALLOWED_STATUSES:
            reasons.append("invalid_status")
        if reasons:
            rec["source_row_number"] = int(row_num) + 2
            rec["reject_reason"] = "|".join(sorted(set(reasons)))
            rejected_rows.append(rec)
        else:
            valid_rows.append({
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": order_date.isoformat(),
                "quantity": quantity,
                "unit_price": round(unit_price, 2),
                "status": status,
                "amount": round(quantity * unit_price, 2),
            })
    columns = ["order_id", "customer_id", "order_date", "quantity", "unit_price", "status", "amount"]
    valid = pd.DataFrame(valid_rows, columns=columns)
    rejected = pd.DataFrame(rejected_rows)
    return valid, rejected
