from datetime import date
import pandas as pd
import pytest
from src.validation import validate_orders
from src.reconciliation import reconcile
from src.database import connect, upsert_orders, table_count
from src.ingestion import read_orders

def frame(rows):
    return pd.DataFrame(rows, columns=["order_id","customer_id","order_date","quantity","unit_price","status"])

def good(order_id="ORD-0000001", **kw):
    x = {"order_id":order_id,"customer_id":"CUST-00001","order_date":"2025-01-01",
         "quantity":"2","unit_price":"10.00","status":"PAID"}
    x.update(kw)
    return x

def test_happy_path_and_reconciliation_pass():
    raw = frame([good()])
    valid, rejected = validate_orders(raw, date(2025, 1, 2))
    assert len(valid) == 1 and rejected.empty
    result = reconcile(valid, valid.copy())
    assert result["status"] == "PASS"

def test_empty_input():
    raw = frame([])
    valid, rejected = validate_orders(raw, date(2025, 1, 2))
    assert valid.empty and rejected.empty

def test_malformed_record_and_missing_required_field():
    raw = frame([good("ORD-1", order_date="not-a-date"), good("ORD-2", customer_id="")])
    valid, rejected = validate_orders(raw, date(2025, 1, 2))
    assert valid.empty and len(rejected) == 2

def test_duplicate_business_key_first_wins():
    raw = frame([good(), good(quantity="3")])
    valid, rejected = validate_orders(raw, date(2025, 1, 2))
    assert len(valid) == 1
    assert "duplicate_order_id" in rejected.iloc[0]["reject_reason"]

def test_null_and_numeric_boundaries():
    raw = frame([good("ORD-1", quantity="0"), good("ORD-2", unit_price="")])
    valid, rejected = validate_orders(raw, date(2025, 1, 2))
    assert len(rejected) == 2

def test_domain_future_date_and_invalid_customer_reference_format():
    raw = frame([good("ORD-1", order_date="2026-12-31"),
                 good("ORD-2", customer_id="UNKNOWN")])
    valid, rejected = validate_orders(raw, date(2026, 11, 6))
    assert len(rejected) == 2
    assert any("order_date_too_far_in_future" in x for x in rejected.reject_reason)
    assert any("invalid_customer_id_format" in x for x in rejected.reject_reason)

def test_reconciliation_detects_missing_extra_and_field_mismatch():
    src, _ = validate_orders(frame([good(), good("ORD-2")]), date(2025, 1, 2))
    tgt = src.copy()
    tgt.loc[0, "status"] = "NEW"
    tgt = tgt.iloc[:1].copy()
    result = reconcile(src, tgt)
    assert result["status"] == "FAIL"
    assert result["field_mismatch_count"] == 1
    assert len(result["key_mismatches"]) == 1

def test_unexpected_schema_change_fails(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("order_id,customer_id,unexpected\\n1,2,3\\n")
    with pytest.raises(ValueError, match="Schema mismatch"):
        read_orders(p)

def test_idempotent_upsert(tmp_path):
    valid, _ = validate_orders(frame([good()]), date(2025, 1, 2))
    conn = connect(tmp_path / "test.db")
    upsert_orders(conn, valid, "run1")
    upsert_orders(conn, valid, "run2")
    assert table_count(conn) == 1
    assert conn.execute("SELECT last_run_id FROM orders").fetchone()[0] == "run2"
    conn.close()
