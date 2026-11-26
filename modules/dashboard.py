from db import fetch_one, fetch_all


def get_owner_dashboard_data():
    kpis = fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM sales_orders) AS total_orders,
            (SELECT COUNT(*) FROM sales_orders WHERE status = 'Submitted') AS pending_orders,
            (SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE status = 'POSTED') AS total_sales,
            (SELECT COALESCE(SUM(outstanding_amount), 0) FROM invoices WHERE status = 'POSTED') AS total_outstanding,
            (SELECT COALESCE(SUM(current_qty * weighted_avg_rate), 0) FROM inventory_balances) AS total_stock_value,
            (SELECT COALESCE(AVG(cost_per_packet), 0) FROM production_runs) AS avg_cost_per_packet,
            (SELECT COUNT(*) FROM production_runs WHERE yield_abnormal = TRUE) AS abnormal_yield_runs,
            (SELECT COUNT(*) FROM production_consumptions WHERE is_abnormal = TRUE) AS abnormal_material_vars
        """
    )

    product_sales = fetch_all(
        """
        SELECT p.name AS label, COALESCE(SUM(ii.line_total), 0) AS value
        FROM products p
        LEFT JOIN invoice_items ii ON ii.product_id = p.id
        LEFT JOIN invoices i ON i.id = ii.invoice_id AND i.status = 'POSTED'
        GROUP BY p.id, p.name
        ORDER BY value DESC
        """
    )

    stock_breakdown = fetch_all(
        """
        SELECT item_type AS label, COALESCE(SUM(current_qty * weighted_avg_rate), 0) AS value
        FROM inventory_balances
        GROUP BY item_type
        ORDER BY item_type
        """
    )

    recent_runs = fetch_all(
        """
        SELECT pr.batch_no, p.name AS product_name, pr.expected_packets, pr.good_packets,
               pr.yield_variance_pct, pr.yield_abnormal, pr.cost_per_packet
        FROM production_runs pr
        JOIN products p ON p.id = pr.product_id
        ORDER BY pr.id DESC
        LIMIT 8
        """
    )

    return {
        "kpis": kpis,
        "product_sales": product_sales,
        "stock_breakdown": stock_breakdown,
        "recent_runs": recent_runs,
    }
