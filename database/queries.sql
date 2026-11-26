-- Reference SQL Queries for Order-to-Audit Management System

-- 1. Live Stock Summary across Raw Materials, Packaging Materials, and Finished Goods
SELECT
    ib.item_type,
    ib.item_id,
    COALESCE(rm.name, pm.name, p.name) AS item_name,
    u.code AS unit_code,
    ib.opening_qty,
    ib.current_qty,
    ib.weighted_avg_rate,
    ROUND(ib.current_qty * ib.weighted_avg_rate, 2) AS stock_value
FROM inventory_balances ib
JOIN units u ON u.id = ib.unit_id
LEFT JOIN raw_materials rm ON ib.item_type = 'RAW_MATERIAL' AND rm.id = ib.item_id
LEFT JOIN packaging_materials pm ON ib.item_type = 'PACKAGING_MATERIAL' AND pm.id = ib.item_id
LEFT JOIN products p ON ib.item_type = 'FINISHED_GOOD' AND p.id = ib.item_id
ORDER BY ib.item_type, item_name;

-- 2. GSTR-1 / GSTR-3B Outward Supplies Summary
SELECT
    i.invoice_no,
    i.invoice_date,
    c.name AS customer_name,
    c.gstin AS customer_gstin,
    i.place_of_supply,
    i.supply_type,
    i.taxable_amount,
    i.cgst_amount,
    i.sgst_amount,
    i.igst_amount,
    i.total_amount,
    i.status
FROM invoices i
JOIN customers c ON c.id = i.customer_id
ORDER BY i.invoice_date DESC, i.id DESC;

-- 3. Customer-wise Receivables Ageing
SELECT
    c.id AS customer_id,
    c.name AS customer_name,
    c.state,
    COALESCE(SUM(i.total_amount), 0) AS total_invoiced,
    COALESCE(SUM(i.paid_amount), 0) AS total_paid,
    COALESCE(SUM(i.outstanding_amount), 0) AS total_outstanding,
    COALESCE(SUM(CASE WHEN CURRENT_DATE - i.invoice_date <= 30 THEN i.outstanding_amount ELSE 0 END), 0) AS bucket_0_30,
    COALESCE(SUM(CASE WHEN CURRENT_DATE - i.invoice_date BETWEEN 31 AND 60 THEN i.outstanding_amount ELSE 0 END), 0) AS bucket_31_60,
    COALESCE(SUM(CASE WHEN CURRENT_DATE - i.invoice_date > 60 THEN i.outstanding_amount ELSE 0 END), 0) AS bucket_60_plus
FROM customers c
LEFT JOIN invoices i ON i.customer_id = c.id AND i.status = 'POSTED'
GROUP BY c.id, c.name, c.state
HAVING COALESCE(SUM(i.outstanding_amount), 0) > 0
ORDER BY total_outstanding DESC;
