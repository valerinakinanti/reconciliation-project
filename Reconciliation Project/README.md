# Trade Reconciliation Control Tower

A SQL + Python engine that reconciles a commodity trading firm's front-office
trade book (ETRM/ENDUR) against its back-office accounting ledger (SAP),
classifies discrepancies into 5 real-world break types, ages open items, and
quantifies financial exposure — the same control function performed daily by
Treasury Operations and tested by Internal Audit at commodity trading firms.

**Live dashboard:** `outputs/dashboard.html` (open directly in any browser)
**Control memo:** `outputs/control_memo.md`

## Why this project

This is built on real operational exposure to SAP–ETRM(ENDUR) reconciliation
from a commodity trading finance internship — extended into a standalone,
generalizable tool rather than a tutorial-style exercise. It's designed to
answer the questions an interviewer would actually ask: *why did you build
this, what's the tolerance logic, how did you validate it works.*

## What it does

1. **Generates realistic trade data** (`scripts/01_generate_trades.py`) —
   6,000 commodity trades across 5 desks, with prices anchored to actual 2024
   monthly average WTI crude prices (EIA), not random numbers. Deliberately
   injects 5 break types into a simulated SAP copy of the ETRM book.

2. **Reconciles via SQL** (`sql/02_reconciliation_engine.sql`) — a
   tolerance-based FULL OUTER JOIN (built manually, since SQLite has no native
   FULL OUTER JOIN) that classifies every trade as MATCHED or one of:
   `TIMING`, `FX_RATE`, `FEE_MISSING`, `PRICE_MISMATCH`, `MISSING_IN_SAP` /
   `MISSING_IN_ETRM`.

3. **Validates detection accuracy** (`scripts/02_run_reconciliation.py`) —
   cross-checks the engine's output against the known ground-truth breaks
   injected in step 1. Result: **100% classification accuracy.**

4. **Computes aging & financial exposure** (`scripts/03_aging_and_summary.py`)
   — buckets open items by age (0-10 / 11-20 / 21-30 / 31+ days) and
   quantifies the USD exposure per break, per desk, per counterparty.

5. **Reports findings** — a management-style control memo
   (`outputs/control_memo.md`) with root causes and remediation
   recommendations, plus an interactive dashboard (`outputs/dashboard.html`).

## Key finding

91.0% of trades matched cleanly. Of the 9% that didn't, a single break type —
trades booked in the front office but never keyed into accounting
(`MISSING_IN_SAP`) — accounted for **96% of total dollar exposure** despite
being only 20% of break volume. See the control memo for the full write-up
and remediation plan.

## Stack

Python (pandas, numpy) · SQLite · SQL (window-free portable syntax) · HTML/CSS/JS
for the dashboard (no framework dependency — opens in any browser).

## Run it yourself

```bash
cd scripts
python3 01_generate_trades.py       # generates data/*.csv and data/reconciliation.db
python3 02_run_reconciliation.py    # runs SQL engine, prints validation accuracy
python3 03_aging_and_summary.py     # produces outputs/dashboard_summary.json
```

Then open `outputs/dashboard.html` in a browser.

## Project structure

```
recon-project/
├── data/                    generated trade data (CSV + SQLite DB)
├── sql/02_reconciliation_engine.sql
├── scripts/
│   ├── 01_generate_trades.py
│   ├── 02_run_reconciliation.py
│   └── 03_aging_and_summary.py
├── outputs/
│   ├── dashboard.html
│   ├── dashboard_summary.json
│   └── control_memo.md
└── README.md
```
