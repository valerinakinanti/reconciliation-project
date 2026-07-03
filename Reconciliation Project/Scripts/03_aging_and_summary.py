"""
03_aging_and_summary.py
-------------------------
Turns raw break classifications into the kind of summary an Internal Audit /
Treasury Controls team actually reports to management:

1. AGING — how long has each break been open? A break open 1 day is routine;
   a break open 10+ days is a control failure that auditors will flag, because
   it means nobody is monitoring reconciliation daily.
   Aging = reference_date - trade_date, bucketed into:
     0-2 days   -> "Same cycle"      (normal operational lag)
     3-5 days   -> "Aging"           (needs follow-up)
     6-10 days  -> "Overdue"         (control concern)
     11+ days   -> "Critical"        (audit finding territory)

2. FINANCIAL EXPOSURE — for value breaks (PRICE_MISMATCH, FX_RATE,
   FEE_MISSING, NOTIONAL_UNEXPLAINED) we quantify the $ difference between
   what ETRM and SAP each say the trade is worth. This is the number a CFO
   actually cares about — "how much money is at stake", not just "how many
   rows don't match."

3. BREAKDOWNS by desk / counterparty / break type — this is what lets you
   say something insight-driven in an interview, e.g. "68% of FX_RATE breaks
   sit in the Freight desk because those trades are booked in SGD/EUR", not
   just "there are some breaks."
"""
import pandas as pd
import numpy as np
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
results = pd.read_csv(os.path.join(BASE, "data", "reconciliation_results.csv"))
results["trade_date"] = pd.to_datetime(results["trade_date"])

REFERENCE_DATE = pd.Timestamp("2025-01-15")  # books close ~2 weeks after month-end — realistic reporting lag

# NOTE ON SCOPE: overall match-rate / break-type stats below use the FULL YEAR
# of trades (that's the right lens for "how healthy is our control environment
# overall"). But AGING only makes sense for ONE reconciliation cycle at a time
# — a January trade can't meaningfully be "critically overdue" against a
# reference date 12 months later just because the dataset spans a year. So the
# aging view is scoped to the most recently closed monthly cycle (December
# 2024) — this is what a real Treasury Ops "open items" report would show.
CURRENT_CYCLE_START = pd.Timestamp("2024-12-01")
CURRENT_CYCLE_END = pd.Timestamp("2024-12-31")
results["age_days"] = (REFERENCE_DATE - results["trade_date"]).dt.days

def age_bucket(days):
    if days <= 10:
        return "0-10 days (Same cycle)"
    elif days <= 20:
        return "11-20 days (Aging)"
    elif days <= 30:
        return "21-30 days (Overdue)"
    else:
        return "31+ days (Critical)"

breaks_all = results[results["break_type"] != "MATCHED"].copy()
breaks = breaks_all[
    (breaks_all["trade_date"] >= CURRENT_CYCLE_START) & (breaks_all["trade_date"] <= CURRENT_CYCLE_END)
].copy()
breaks["age_bucket"] = breaks["age_days"].apply(age_bucket)

# financial exposure = |ETRM notional - SAP notional|, treating missing trades
# as full notional exposure (the whole trade is unaccounted for in one system)
def exposure(row):
    if row["break_type"] in ("MISSING_IN_SAP",):
        return abs(row["etrm_notional"])
    if row["break_type"] in ("MISSING_IN_ETRM",):
        return abs(row["sap_notional"])
    if pd.isna(row["etrm_notional"]) or pd.isna(row["sap_notional"]):
        return 0.0
    notional_diff = abs(row["etrm_notional"] - row["sap_notional"])
    fee_diff = abs((row["etrm_fee"] or 0) - (row["sap_fee"] or 0))
    return notional_diff + fee_diff

breaks_all["exposure_usd"] = breaks_all.apply(exposure, axis=1)
breaks["exposure_usd"] = breaks.apply(exposure, axis=1)

summary = {
    "as_of_date": REFERENCE_DATE.strftime("%Y-%m-%d"),
    "current_cycle": f"{CURRENT_CYCLE_START.strftime('%b %Y')} reconciliation (open items as of {REFERENCE_DATE.strftime('%d %b %Y')})",
    "total_trades": int(len(results)),
    "matched_trades": int((results["break_type"] == "MATCHED").sum()),
    "total_breaks": int(len(breaks_all)),
    "match_rate_pct": round((results["break_type"] == "MATCHED").mean() * 100, 2),
    "total_exposure_usd": round(breaks_all["exposure_usd"].sum(), 2),
    "current_cycle_open_breaks": int(len(breaks)),
    "current_cycle_exposure_usd": round(breaks["exposure_usd"].sum(), 2),

    # Full-year lens — "how healthy is the control environment overall"
    "by_break_type": (
        breaks_all.groupby("break_type")
        .agg(count=("trade_id", "count"), exposure_usd=("exposure_usd", "sum"))
        .reset_index().round(2).to_dict(orient="records")
    ),
    "by_desk": (
        breaks_all.groupby("desk")
        .agg(count=("trade_id", "count"), exposure_usd=("exposure_usd", "sum"))
        .reset_index().round(2).to_dict(orient="records")
    ),
    "by_counterparty_top10": (
        breaks_all.groupby("counterparty")
        .agg(count=("trade_id", "count"), exposure_usd=("exposure_usd", "sum"))
        .reset_index().sort_values("exposure_usd", ascending=False).head(10)
        .round(2).to_dict(orient="records")
    ),

    # Single-cycle lens — "what's open right now and how stale is it"
    "by_age_bucket": (
        breaks.groupby("age_bucket")
        .agg(count=("trade_id", "count"), exposure_usd=("exposure_usd", "sum"))
        .reset_index().round(2).to_dict(orient="records")
    ),
    "heatmap_desk_age": (
        breaks.groupby(["desk", "age_bucket"]).size()
        .reset_index(name="count").to_dict(orient="records")
    ),
    "sample_breaks": (
        breaks.sort_values("exposure_usd", ascending=False)
        .head(25)[["trade_id", "desk", "counterparty", "break_type", "age_bucket", "exposure_usd", "trade_date"]]
        .assign(trade_date=lambda d: d["trade_date"].dt.strftime("%Y-%m-%d"))
        .round(2).to_dict(orient="records")
    ),
}

out_path = os.path.join(BASE, "outputs", "dashboard_summary.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(summary, f, indent=2)

print(f"Match rate (full year): {summary['match_rate_pct']}%")
print(f"Total breaks (full year): {summary['total_breaks']}  |  Total exposure: ${summary['total_exposure_usd']:,.0f}")
print(f"Open items in current cycle ({CURRENT_CYCLE_START.strftime('%b %Y')}): {summary['current_cycle_open_breaks']}"
      f"  |  Exposure: ${summary['current_cycle_exposure_usd']:,.0f}")
print(f"Critical (31+ day) open breaks: "
      f"{sum(b['count'] for b in summary['by_age_bucket'] if 'Critical' in b['age_bucket'])}")
print(f"Saved dashboard summary -> {out_path}")
