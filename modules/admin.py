from db import fetch_one


def get_admin_summary():
    return fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM sales_orders WHERE status = 'Submitted') AS submitted_orders,
            (SELECT COUNT(*) FROM sales_orders WHERE status = 'Approved') AS approved_orders,
            (SELECT COUNT(*) FROM sales_orders WHERE status = 'Invoiced') AS invoiced_orders,
            (SELECT COUNT(*) FROM sales_orders WHERE status = 'Dispatched') AS dispatched_orders,
            (SELECT COUNT(*) FROM sales_orders WHERE has_stock_shortage = TRUE AND status = 'Submitted') AS shortage_orders,
            (SELECT COALESCE(SUM(outstanding_amount), 0) FROM invoices WHERE status = 'POSTED') AS total_outstanding
        """
    )
