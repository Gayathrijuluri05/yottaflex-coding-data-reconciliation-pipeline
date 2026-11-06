import argparse
from datetime import datetime, timezone, date
from pathlib import Path
import logging
import time
import uuid
import pandas as pd

from src.ingestion import read_orders
from src.validation import validate_orders
from src.transformation import normalize_target
from src.database import connect, upsert_orders, table_count
from src.reconciliation import reconcile
from src.reporting import write_outputs

def run_pipeline(source_path, target_path, db_path, output_dir, run_id=None):
    run_id = run_id or uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=Path(output_dir) / f"run_{run_id}.log",
                        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        force=True)
    source_count = target_count = 0
    rejected = pd.DataFrame()
    try:
        source_raw = read_orders(source_path)
        target_raw = read_orders(target_path)
        source_count, target_count = len(source_raw), len(target_raw)
        valid, rejected = validate_orders(source_raw, run_date=date.today())
        target_valid, target_rejected = validate_orders(target_raw, run_date=date.today())
        # Target rejects are represented as target-only quality errors in operational logs.
        if not target_rejected.empty:
            logging.warning("Target contains %s invalid rows", len(target_rejected))
        target_norm = normalize_target(target_valid)
        conn = connect(db_path)
        try:
            upsert_orders(conn, valid, run_id)
            logging.info("Published %s valid source rows; database row count=%s", len(valid), table_count(conn))
        finally:
            conn.close()
        result = reconcile(valid, target_norm)
        result["target_rejected_count"] = int(len(target_rejected))
        result["target_rejected_records"] = target_rejected.to_dict(orient="records")
        logging.info("Reconciliation status=%s", result["status"])
        ended = datetime.now(timezone.utc).isoformat()
        return write_outputs(output_dir, Path(output_dir).parent / "quarantine", run_id, result,
                             rejected, started, ended, source_count, len(valid), target_count,
                             time.perf_counter() - t0)
    except Exception as exc:
        logging.exception("Pipeline failed")
        ended = datetime.now(timezone.utc).isoformat()
        failure = {"status": "FAILED", "key_mismatches": [], "field_mismatches": [],
                   "failure_reason": str(exc)}
        write_outputs(output_dir, Path(output_dir).parent / "quarantine", run_id, failure,
                      rejected, started, ended, source_count, 0, target_count,
                      time.perf_counter() - t0, str(exc))
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Source-to-target reconciliation pipeline")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--db", default="data/reconciliation.db")
    parser.add_argument("--output", default="reports")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    report = run_pipeline(args.source, args.target, args.db, args.output, args.run_id)
    print(f"Run {report['run_id']}: {report['status']}")
    print(f"Valid source rows={report['source_valid_count']}, rejected={report['source_rejected_count']}, "
          f"field mismatches={report['field_mismatch_count']}, key mismatches={len(report['key_mismatches'])}")
