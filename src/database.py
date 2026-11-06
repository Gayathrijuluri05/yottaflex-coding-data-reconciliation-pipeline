import sqlite3
from pathlib import Path
import pandas as pd

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
 order_id TEXT PRIMARY KEY,
 customer_id TEXT NOT NULL,
 order_date TEXT NOT NULL,
 quantity INTEGER NOT NULL,
 unit_price REAL NOT NULL,
 status TEXT NOT NULL,
 amount REAL NOT NULL,
 last_run_id TEXT NOT NULL
)
"""

def connect(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(CREATE_SQL)
    conn.commit()
    return conn

def upsert_orders(conn, df: pd.DataFrame, run_id: str):
    if df.empty:
        return
    records = [tuple(row) + (run_id,) for row in df[["order_id","customer_id","order_date","quantity","unit_price","status","amount"]].itertuples(index=False, name=None)]
    conn.executemany("""
      INSERT INTO orders(order_id,customer_id,order_date,quantity,unit_price,status,amount,last_run_id)
      VALUES(?,?,?,?,?,?,?,?)
      ON CONFLICT(order_id) DO UPDATE SET
       customer_id=excluded.customer_id, order_date=excluded.order_date,
       quantity=excluded.quantity, unit_price=excluded.unit_price,
       status=excluded.status, amount=excluded.amount, last_run_id=excluded.last_run_id
    """, records)
    conn.commit()

def table_count(conn):
    return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
