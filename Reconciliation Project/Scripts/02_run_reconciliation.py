"""
02_run_reconciliation.py
--------------------------
Executes the SQL reconciliation engine (02_reconciliation_engine.sql) against
the SQLite database built in step 1, then validates how accurately the SQL
classification logic recovered the ground-truth breaks we injected.

This validation step matters for a portfolio project: it proves the engine
actually works, not just that it "runs without errors."
"""
import sqlite3
import pandas as pd
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(BASE, "data", "reconciliation.db")
SQL_PATH = os.path.join(BASE, "sql", "02_reconciliation_engine.sql")

conn = sqlite3.connect(DB_PATH)
with open(SQL_PATH) as f:
    conn.executescript(f.read())

results = pd.read_sql("SELECT * FROM reconciliation_results", conn)
ground_truth = pd.read_csv(os.path.join(BASE, "data", "ground_truth_breaks.csv"))

print("=== Break type distribution (engine output) ===")
print(results["break_type"].value_counts().to_string())

# --- Validate detection accuracy against known injected breaks ---
merged = results.merge(ground_truth, on="trade_id", how="left")
merged["injected_break_type"] = merged["injected_break_type"].fillna("MATCHED")

# normalize label naming between injection script and SQL engine for comparison
label_map = {
    "TIMING": "TIMING", "FX_RATE": "FX_RATE", "FEE_MISSING": "FEE_MISSING",
    "MISSING_TRADE": "MISSING_IN_SAP", "PRICE_MISMATCH": "PRICE_MISMATCH",
    "MATCHED": "MATCHED",
}
merged["expected"] = merged["injected_break_type"].map(label_map)
merged["correct"] = merged["expected"] == merged["break_type"]

accuracy = merged["correct"].mean() * 100
print(f"\n=== Detection accuracy vs ground truth: {accuracy:.2f}% ===")
print(pd.crosstab(merged["expected"], merged["break_type"]))

results.to_csv(os.path.join(BASE, "data", "reconciliation_results.csv"), index=False)
conn.close()
print(f"\nSaved: data/reconciliation_results.csv ({len(results)} rows)")
