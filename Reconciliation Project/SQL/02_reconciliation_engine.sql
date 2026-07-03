-- ============================================================================
-- 02_reconciliation_engine.sql
-- ----------------------------------------------------------------------------
-- Reconciliation logic: compare ETRM (front-office trade record) against
-- SAP (back-office accounting record) and classify every trade as either
-- MATCHED or a specific BREAK type.
--
-- Concept for anyone new to this: SQLite (like most databases) doesn't have a
-- built-in "FULL OUTER JOIN" keyword, so we build one manually:
--   FULL OUTER JOIN = (LEFT JOIN A->B)  UNION  (LEFT JOIN B->A)
-- This guarantees that trades which exist in ONLY ONE system (a "missing
-- trade" break) are captured, not just trades that exist in both.
--
-- Tolerance-based matching: real financial data always has floating point /
-- rounding noise, so we never compare floats with "=". Instead we use a
-- tolerance band (e.g. price within $0.02/bbl, notional within $50) — this
-- mirrors how real reconciliation tools (e.g. Duco, SmartStream TLM) work.
-- ============================================================================

DROP TABLE IF EXISTS reconciliation_results;

CREATE TABLE reconciliation_results AS
WITH joined AS (
    -- every ETRM trade, matched to SAP if it exists there
    SELECT
        e.trade_id,
        e.desk,
        e.counterparty,
        e.currency,
        e.trade_date,
        e.settlement_date        AS etrm_settlement_date,
        s.settlement_date        AS sap_settlement_date,
        e.price_usd_bbl          AS etrm_price,
        s.price_usd_bbl          AS sap_price,
        e.volume_bbl             AS etrm_volume,
        s.volume_bbl             AS sap_volume,
        e.notional                AS etrm_notional,
        s.notional                AS sap_notional,
        e.fee                     AS etrm_fee,
        s.fee                     AS sap_fee,
        CASE WHEN s.trade_id IS NULL THEN 1 ELSE 0 END AS missing_in_sap
    FROM etrm_trades e
    LEFT JOIN sap_ledger s ON e.trade_id = s.trade_id

    UNION ALL

    -- any SAP trade that has no ETRM counterpart at all (front office never booked it,
    -- or it was cancelled in ETRM but the accounting entry was never reversed)
    SELECT
        s.trade_id,
        s.desk,
        s.counterparty,
        s.currency,
        s.trade_date,
        NULL                      AS etrm_settlement_date,
        s.settlement_date         AS sap_settlement_date,
        NULL                      AS etrm_price,
        s.price_usd_bbl           AS sap_price,
        NULL                      AS etrm_volume,
        s.volume_bbl              AS sap_volume,
        NULL                      AS etrm_notional,
        s.notional                AS sap_notional,
        NULL                      AS etrm_fee,
        s.fee                     AS sap_fee,
        0                         AS missing_in_sap
    FROM sap_ledger s
    LEFT JOIN etrm_trades e ON s.trade_id = e.trade_id
    WHERE e.trade_id IS NULL
)
SELECT
    trade_id, desk, counterparty, currency, trade_date,
    etrm_settlement_date, sap_settlement_date,
    etrm_price, sap_price, etrm_volume, sap_volume,
    etrm_notional, sap_notional, etrm_fee, sap_fee,

    -- classification: order matters — most specific / severe break wins
    CASE
        WHEN missing_in_sap = 1                                     THEN 'MISSING_IN_SAP'
        WHEN etrm_notional IS NULL                                  THEN 'MISSING_IN_ETRM'
        WHEN etrm_settlement_date <> sap_settlement_date            THEN 'TIMING'
        WHEN sap_fee = 0 AND etrm_fee > 0                           THEN 'FEE_MISSING'
        WHEN ABS(etrm_price - sap_price) > 0.02
             AND ABS(etrm_notional - sap_notional)
                 > 0.02 * etrm_volume + 5                            THEN 'PRICE_MISMATCH'
        WHEN ABS(etrm_notional - sap_notional) > 50
             AND ABS(etrm_price - sap_price) <= 0.02                THEN 'FX_RATE'
        WHEN ABS(etrm_notional - sap_notional) > 50                 THEN 'NOTIONAL_UNEXPLAINED'
        ELSE 'MATCHED'
    END AS break_type
FROM joined;

-- Quick sanity check query (run separately): break_type distribution
-- SELECT break_type, COUNT(*) FROM reconciliation_results GROUP BY break_type ORDER BY 2 DESC;
