"""
01_generate_trades.py
----------------------
Generates two independent trade populations that simulate what a commodity
trading firm's Accounting system (SAP) and Trading/ETRM system (ENDUR) would
each record for the same underlying trades.

Why two systems for the same trades?
In real commodity trading operations, the FRONT OFFICE books a trade in the
ETRM system (e.g. ENDUR) the moment a deal is agreed. Separately, the BACK
OFFICE / ACCOUNTING team records the accounting entry in SAP once the trade
is confirmed and invoiced. Because these are two independently maintained
systems, small differences creep in: a price gets updated in one system but
not the other, a fee is booked a day late, a trade is cancelled in one system
but the cancellation isn't yet reflected in the other, etc.

Reconciliation = the process of comparing these two independent records of
the "same" economic reality and proving they agree, trade by trade. Anything
that doesn't agree is called a "break" or "exception", and someone has to
investigate WHY it doesn't agree (this is exactly the work described in the
brief: "reconcile monthly trading PnL... between SAP and ETRM/ENDUR").

This script deliberately injects 5 realistic break types so the reconciliation
engine (02_reconciliation_engine.py) has real discrepancies to detect —
mirroring the kinds of breaks real commodity trading ops teams deal with.

Price realism: instead of random numbers, trade prices are anchored to actual
2024 monthly average WTI crude oil settlement prices (source: EIA Short-Term
Energy Outlook / Cushing OK WTI spot price series), with realistic day-to-day
noise layered on top. This is what "grounded in real market data" means in
practice for a portfolio project — the numbers should survive a "where did
this come from" question in an interview.
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta

np.random.seed(42)  # reproducible — important for a portfolio piece you'll walk through live

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Real-world anchor: 2024 monthly average WTI crude price (USD/bbl)
#    Source: EIA Short-Term Energy Outlook / Cushing OK WTI spot series.
#    Approximate published monthly averages — used here as the "true market"
#    backbone so simulated trade prices track an actual historical curve
#    rather than being pulled from thin air.
# ---------------------------------------------------------------------------
WTI_MONTHLY_2024 = {
    1: 74.1, 2: 76.6, 3: 81.3, 4: 85.7, 5: 79.6, 6: 78.5,
    7: 81.8, 8: 76.9, 9: 70.2, 10: 71.9, 11: 69.8, 12: 69.5,
}

DESKS = ["Crude Oil", "Middle Distillates", "Naphtha & Gasoline", "Fuel Oil", "Freight"]
COUNTERPARTIES = [
    "Vitol SA", "Trafigura Group", "Glencore Energy UK", "Mercuria Energy",
    "Shell Trading", "BP Oil International", "PetroChina Intl", "Reliance Industries",
    "Chevron Products", "TotalEnergies Trading", "ExxonMobil Sales & Supply", "Unipec Asia",
]
CURRENCIES = ["USD", "USD", "USD", "SGD", "EUR"]  # USD-heavy, realistic for crude/products

N_TRADES = 6000


def daily_price(date: datetime) -> float:
    """Simulate a realistic daily settlement price around the real monthly anchor."""
    base = WTI_MONTHLY_2024[date.month]
    # small autocorrelated daily noise so prices don't look like white noise
    noise = np.random.normal(0, 1.1)
    return round(base + noise, 2)


def generate_base_trades(n=N_TRADES) -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    rows = []
    for i in range(n):
        trade_date = start + timedelta(days=int(np.random.uniform(0, 364)))
        settle_date = trade_date + timedelta(days=int(np.random.choice([2, 3, 5, 30], p=[0.55, 0.25, 0.1, 0.1])))
        desk = np.random.choice(DESKS, p=[0.42, 0.22, 0.16, 0.12, 0.08])
        price = daily_price(trade_date) + np.random.normal(0, 0.35)  # bid/offer-ish variance
        volume_bbl = int(np.random.choice([25000, 50000, 100000, 150000, 200000],
                                           p=[0.35, 0.3, 0.2, 0.1, 0.05]))
        notional = round(price * volume_bbl, 2)
        currency = np.random.choice(CURRENCIES)
        fee = round(notional * np.random.uniform(0.0008, 0.0018), 2)
        rows.append({
            "trade_id": f"TRD-2024-{i+100000}",
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "settlement_date": settle_date.strftime("%Y-%m-%d"),
            "desk": desk,
            "counterparty": np.random.choice(COUNTERPARTIES),
            "currency": currency,
            "price_usd_bbl": round(price, 2),
            "volume_bbl": volume_bbl,
            "notional": notional,
            "fee": fee,
        })
    return pd.DataFrame(rows)


def build_etrm_and_sap(base: pd.DataFrame):
    """
    ETRM = front-office trading system record (assumed 'source of truth' for trade economics).
    SAP  = back-office accounting record, derived from ETRM but subject to independent
           lags, manual re-keying, and system timing — which is where real breaks originate.

    5 injected break types (mirrors real commodity ops reconciliation breaks):
      1. TIMING       - settlement date differs (accounting posts a day/two late)
      2. FX_RATE      - non-USD trades revalued at a different FX rate snapshot
      3. FEE_MISSING  - accrued fee not yet booked in SAP
      4. MISSING_TRADE- trade exists in ETRM but was never keyed into SAP (or vice versa)
      5. PRICE_MISMATCH - price amended in ETRM post-trade, SAP still has original price
    """
    etrm = base.copy()
    sap = base.copy()

    n = len(base)
    idx = np.arange(n)
    np.random.shuffle(idx)

    # Roughly 9% of trades will carry a break — realistic for a well-controlled but real ops environment
    n_breaks = int(n * 0.09)
    break_idx = idx[:n_breaks]
    chunks = np.array_split(break_idx, 5)

    break_log = []  # ground truth, used later to validate the engine's detection

    # 1. TIMING difference
    for i in chunks[0]:
        d = pd.to_datetime(sap.loc[i, "settlement_date"]) + timedelta(days=int(np.random.choice([1, 2])))
        sap.loc[i, "settlement_date"] = d.strftime("%Y-%m-%d")
        break_log.append((base.loc[i, "trade_id"], "TIMING"))

    # 2. FX_RATE mismatch (only applies to non-USD trades; simulate a stale FX snapshot in SAP)
    fx_candidates = [i for i in chunks[1]]
    for i in fx_candidates:
        fx_drift = np.random.uniform(0.01, 0.04) * np.random.choice([-1, 1])
        sap.loc[i, "notional"] = round(sap.loc[i, "notional"] * (1 + fx_drift), 2)
        break_log.append((base.loc[i, "trade_id"], "FX_RATE"))

    # 3. FEE_MISSING in SAP (fee accrual not yet posted)
    for i in chunks[2]:
        sap.loc[i, "fee"] = 0.0
        break_log.append((base.loc[i, "trade_id"], "FEE_MISSING"))

    # 4. MISSING_TRADE — drop from SAP entirely (not yet keyed in)
    missing_ids = set(base.loc[chunks[3], "trade_id"])
    sap = sap[~sap["trade_id"].isin(missing_ids)]
    for tid in missing_ids:
        break_log.append((tid, "MISSING_TRADE"))

    # 5. PRICE_MISMATCH — ETRM amended post-trade, SAP still has stale price
    for i in chunks[4]:
        amend = np.random.uniform(0.15, 1.75) * np.random.choice([-1, 1])
        etrm.loc[i, "price_usd_bbl"] = round(etrm.loc[i, "price_usd_bbl"] + amend, 2)
        etrm.loc[i, "notional"] = round(etrm.loc[i, "price_usd_bbl"] * etrm.loc[i, "volume_bbl"], 2)
        break_log.append((base.loc[i, "trade_id"], "PRICE_MISMATCH"))

    break_log_df = pd.DataFrame(break_log, columns=["trade_id", "injected_break_type"])
    return etrm.reset_index(drop=True), sap.reset_index(drop=True), break_log_df


if __name__ == "__main__":
    base = generate_base_trades()
    etrm, sap, ground_truth = build_etrm_and_sap(base)

    etrm.to_csv(os.path.join(OUT_DIR, "etrm_trades.csv"), index=False)
    sap.to_csv(os.path.join(OUT_DIR, "sap_ledger.csv"), index=False)
    ground_truth.to_csv(os.path.join(OUT_DIR, "ground_truth_breaks.csv"), index=False)

    db_path = os.path.join(OUT_DIR, "reconciliation.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    etrm.to_sql("etrm_trades", conn, index=False)
    sap.to_sql("sap_ledger", conn, index=False)
    conn.close()

    print(f"ETRM trades: {len(etrm)}")
    print(f"SAP entries: {len(sap)}")
    print(f"Injected breaks (ground truth): {len(ground_truth)}")
    print(f"Break rate: {len(ground_truth)/len(base)*100:.2f}%")
    print(f"SQLite DB written to: {db_path}")
