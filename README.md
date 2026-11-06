# Source-to-Target Data Reconciliation Pipeline

A local, reproducible data-engineering project that validates order data, loads valid source
records into SQLite, quarantines invalid records, and reconciles the source against a target
CSV using counts, business keys, aggregates, and field-level comparisons.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Generate deterministic sample source and target files
python generate_data.py --rows 100 --seed 42 --output data/sample

# Run the pipeline
python main.py --source data/sample/source_orders.csv \
               --target data/sample/target_orders.csv \
               --db data/reconciliation.db \
               --output reports

# Run automated tests
pytest -q
```

To generate a larger dataset:
```bash
python generate_data.py --rows 100000 --seed 42 --output data/large
python main.py --source data/large/source_orders.csv \
               --target data/large/target_orders.csv \
               --db data/large/reconciliation.db \
               --output data/large/reports
```

## Architecture

`CSV source -> ingestion -> schema/business validation -> quarantine + valid rows -> SQLite upsert -> source/target reconciliation -> JSON/CSV reports`

The source and target represent the same business entity at the same grain: **one row per order**.
The stable business key is `order_id`. `customer_id` is a required reference key. The target is
an independently supplied CSV snapshot, not the SQLite table; SQLite is the pipeline's published
target store. This makes the source-vs-target comparison reproducible and independently testable.

## Data contract / data dictionary

| Field | Type | Nullable | Rule |
|---|---|---:|---|
| order_id | string | no | Stable primary/business key; unique within a batch |
| customer_id | string | no | Must match `CUST-` followed by 5 digits |
| order_date | ISO date | no | `YYYY-MM-DD`; not later than 30 days after run date |
| quantity | integer | no | 1 through 10,000 |
| unit_price | decimal | no | 0 through 1,000,000 |
| status | string | no | `NEW`, `PAID`, `SHIPPED`, or `CANCELLED` |
| amount | decimal | derived | `quantity * unit_price`, rounded to 2 decimals |

**Grain:** one order per row.  
**Relationships:** `orders.customer_id -> customers.customer_id` (the sample generator creates
valid customer IDs; the pipeline validates the key format. A production extension should load
a customer master and enforce actual referential integrity against it).  
**History:** this starter uses a current-state order snapshot. A production CDC/event pipeline
should preserve immutable change events and effective timestamps rather than overwrite history.

## Validation and reconciliation rules

- Required fields, parseable types, allowed status, numeric boundaries, date boundaries.
- Duplicate `order_id`: first valid occurrence wins; later occurrences are quarantined.
- Unexpected/missing columns: fail fast as a schema error.
- Invalid rows are retained in `quarantine/rejected_<run_id>.csv` with `reject_reason`.
- Reconciliation compares valid source rows with target rows by key and checks:
  - row counts and distinct key counts;
  - missing and unexpected business keys;
  - `quantity`, `unit_price`, `status`, `order_date`, and derived `amount`;
  - row count, quantity sum, and amount sum.
- Decimal comparisons use a configurable tolerance (default 0.01).
- The SQLite load uses `INSERT ... ON CONFLICT DO UPDATE` keyed by `order_id`, so rerunning
  the same input does not create duplicate rows.

## Outputs

Each run creates:
- `reports/reconciliation_<run_id>.json`: machine-readable run summary and mismatches.
- `reports/field_mismatches_<run_id>.csv`: one row per differing field.
- `reports/key_mismatches_<run_id>.csv`: source-only and target-only keys.
- `reports/run_<run_id>.log`: operational log.
- `data/quarantine/rejected_<run_id>.csv`: invalid source records.

The JSON report includes run ID, timestamps, input/valid/rejected counts, target count,
aggregate comparisons, mismatch totals, status, and failure reason.

## Idempotency, retries, and backfills

- The stable key is `order_id`; SQLite uses an upsert, not blind append.
- A rerun with identical input updates the same keys and does not increase the table row count.
- A retry after a process failure can safely rerun the whole batch. Reports are uniquely named by
  run ID, so earlier run evidence remains available.
- A backfill is run by supplying the historical source and target snapshots with a distinct run.
  This current-state design updates rows by key; use an append-only event table for full history.

## Performance

`main.py` reports elapsed seconds and records/second. The reconciliation path uses Pandas joins
rather than nested Python loops (approximately linearithmic in row count). For larger production
volumes, use database-side joins/aggregations, partitioned files, and incremental key-range loads.

## Known limitations and next steps

- Local CSV + SQLite only; no scheduler, cloud object storage, streaming, or distributed compute.
- Customer referential integrity is format-validated, not checked against a customer dimension.
- Current-state upsert does not preserve every historical version.
- For production: add a customer dimension, schema versioning, checksums, secrets management,
  alerting, orchestration, and a CDC/SCD2 strategy.

## Repository contents

- `src/`: ingestion, validation, transformation, database, reconciliation, reporting.
- `generate_data.py`: fixed-seed sample and scalable synthetic data generator.
- `tests/`: happy path, empty input, malformed rows, duplicates, nulls, domain boundaries,
  schema drift, and idempotency.
- `data/sample/`: generated starter CSVs (created by the quick-start command).
