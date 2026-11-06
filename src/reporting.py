import json
from pathlib import Path
import pandas as pd

def write_outputs(output_dir, quarantine_dir, run_id, report, rejected, started_at, ended_at,
                  source_count, valid_count, target_count, elapsed_seconds, failure_reason=None):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    qdir = Path(quarantine_dir); qdir.mkdir(parents=True, exist_ok=True)
    if not rejected.empty:
        rejected.to_csv(qdir / f"rejected_{run_id}.csv", index=False)
    pd.DataFrame(report.get("field_mismatches", [])).to_csv(out / f"field_mismatches_{run_id}.csv", index=False)
    pd.DataFrame(report.get("key_mismatches", [])).to_csv(out / f"key_mismatches_{run_id}.csv", index=False)
    report.update({
        "run_id": run_id, "started_at": started_at, "ended_at": ended_at,
        "source_input_count": source_count, "source_valid_count": valid_count,
        "source_rejected_count": int(len(rejected)), "target_input_count": target_count,
        "elapsed_seconds": round(elapsed_seconds, 4),
        "records_per_second": round(source_count / elapsed_seconds, 2) if elapsed_seconds > 0 else None,
        "failure_reason": failure_reason,
    })
    with open(out / f"reconciliation_{run_id}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return report
