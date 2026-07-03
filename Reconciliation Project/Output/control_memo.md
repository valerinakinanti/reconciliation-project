# Reconciliation Control Memo — Commodity Trading Book
**Scope:** SAP (Accounting) vs ETRM/ENDUR (Front Office) trade reconciliation
**Period reviewed:** FY2024 (6,000 trades) | **Open items as of:** 15 Jan 2025
**Prepared for:** Treasury Operations / Internal Audit review

---

## 1. Executive Summary
Of 6,000 trades booked across FY2024, **91.0% matched cleanly** between SAP and
ETRM on first pass. The remaining **540 breaks (9.0%)** represent
**USD 589.9M in gross financial exposure** — i.e., the total dollar difference
between what the two systems say the trade book is worth. This is a **gross,
not net** figure (offsetting errors in both directions are not netted), which
is the conservative and audit-standard way to state exposure.

**Key finding:** a single break type — trades booked in ETRM but never keyed
into SAP (`MISSING_IN_SAP`) — accounts for **96% of total dollar exposure**
(USD 568.5M) despite being only 20% of break count. This is the highest-priority
control gap: a few large, unrecorded trades create outsized financial statement
risk versus many small timing differences.

## 2. Findings by Break Type
| Break Type | Count | Exposure (USD) | Root Cause |
|---|---|---|---|
| MISSING_IN_SAP | 108 | 568,504,314 | Trade confirmed in ETRM but not yet keyed into accounting — process gap between front-office booking and back-office entry, not a system defect |
| FX_RATE | 108 | 13,606,532 | Non-USD trades (SGD/EUR) revalued using a stale FX snapshot in SAP vs. same-day rate in ETRM |
| PRICE_MISMATCH | 108 | 7,136,425 | ETRM price amended post-trade (e.g., pricing period average finalized); SAP not re-synced |
| FEE_MISSING | 108 | 700,297 | Broker/exchange fee accrual not yet posted in SAP at time of report |
| TIMING | 108 | 0 (timing only) | Settlement date differs by 1–2 days — normal operational lag, not a valuation risk |

## 3. Aging — Open Items, December 2024 Cycle
| Age Bucket | Open Items | Exposure (USD) |
|---|---|---|
| 11–20 days (Aging) | 5 | 29,150,272 |
| 21–30 days (Overdue) | 20 | 7,699,064 |
| 31+ days (Critical) | 24 | 23,243,007 |

**24 items have been open for 31+ days** — under a standard T+5 reconciliation
control (the norm at most commodity trading operations), anything open past
10 business days should trigger an escalation to the desk head. The presence
of critical-aged items indicates the current process relies on periodic
manual review rather than a systematic daily aging alert.

## 4. Concentration
- **By desk:** Crude Oil carries the largest break count (216) but Naphtha &
  Gasoline carries higher exposure per break, consistent with larger lot
  sizes and more frequent price amendments in that market.
- **By counterparty:** the top 5 counterparties account for a disproportionate
  share of exposure — concentration risk that supports moving to a
  counterparty-tiered control (higher-frequency recon for top-volume
  counterparties).

## 5. Recommendations
1. **Same-day booking control**: implement a same-day trade capture check
   (ETRM trade count vs. SAP entry count) to catch `MISSING_IN_SAP` within
   24 hours instead of at month-end — this alone addresses 96% of dollar exposure.
2. **FX snapshot alignment**: synchronize the FX rate feed used by SAP to the
   same intraday snapshot ETRM uses for non-USD trades.
3. **Aging SLA**: introduce an automated aging alert at T+10 business days,
   escalating to desk head at T+20 — closing the gap that currently allows
   items to reach 31+ days unresolved.
4. **Fee accrual cutoff**: align SAP's fee accrual batch job to run before
   the daily reconciliation snapshot, eliminating the FEE_MISSING category
   entirely (it's a timing/sequencing issue, not a data quality issue).

---
*Methodology note: reconciliation performed via tolerance-based SQL matching
(price tolerance $0.02/bbl, notional tolerance $50) across the full trade
population, with break classification validated at 100% accuracy against
known test cases before being applied to the full dataset.*
