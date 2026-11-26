from db import fetch_all
from modules.inventory import get_stock_summary, get_stock_ledger
from modules.costing import get_costing_summary
from modules.payments import get_outstanding_and_ageing, list_payments
from modules.purchases import list_purchases


def _date_clause(col, start_date, end_date, prefix="WHERE"):
    clauses = []
    params = []
    if start_date:
        clauses.append(f"{col} >= %s")
        params.append(start_date)
    if end_date:
        clauses.append(f"{col} <= %s")
        params.append(end_date)
    if not clauses:
        return "", ()
    return f"{prefix} " + " AND ".join(clauses), tuple(params)


def get_sales_register(start_date=None, end_date=None):
    clause, params = _date_clause("i.invoice_date", start_date, end_date)
    return fetch_all(
        f"""
        SELECT i.invoice_no, i.invoice_date, c.name AS customer_name, c.gstin AS customer_gstin,
               i.place_of_supply, i.supply_type, i.taxable_amount,
               i.cgst_amount, i.sgst_amount, i.igst_amount, i.total_amount,
               i.paid_amount, i.outstanding_amount, i.status
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        {clause}
        ORDER BY i.invoice_date DESC, i.id DESC
        """,
        params,
    )


def get_customer_wise_sales(start_date=None, end_date=None, salesman_id=None):
    where = ["i.status = 'POSTED'"]
    params = []
    if start_date:
        where.append("i.invoice_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("i.invoice_date <= %s")
        params.append(end_date)
    if salesman_id:
        where.append("so.salesman_id = %s")
        params.append(int(salesman_id))
    clause = "WHERE " + " AND ".join(where)
    return fetch_all(
        f"""
        SELECT c.name AS customer_name, c.state,
               COUNT(i.id) AS invoice_count,
               COALESCE(SUM(i.taxable_amount), 0) AS taxable_amount,
               COALESCE(SUM(i.cgst_amount + i.sgst_amount + i.igst_amount), 0) AS gst_amount,
               COALESCE(SUM(i.total_amount), 0) AS total_amount,
               COALESCE(SUM(i.outstanding_amount), 0) AS outstanding_amount
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        JOIN sales_orders so ON so.id = i.order_id
        {clause}
        GROUP BY c.id, c.name, c.state
        ORDER BY total_amount DESC
        """,
        tuple(params),
    )


def get_product_wise_sales(start_date=None, end_date=None):
    where = ["i.status = 'POSTED'"]
    params = []
    if start_date:
        where.append("i.invoice_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("i.invoice_date <= %s")
        params.append(end_date)
    clause = "WHERE " + " AND ".join(where)
    return fetch_all(
        f"""
        SELECT p.sku, p.name AS product_name, p.hsn_code,
               COALESCE(SUM(ii.qty_packets), 0) AS total_qty,
               COALESCE(SUM(ii.taxable_amount), 0) AS taxable_amount,
               COALESCE(SUM(ii.cgst_amount + ii.sgst_amount + ii.igst_amount), 0) AS gst_amount,
               COALESCE(SUM(ii.line_total), 0) AS total_sales
        FROM invoice_items ii
        JOIN invoices i ON i.id = ii.invoice_id
        JOIN products p ON p.id = ii.product_id
        {clause}
        GROUP BY p.id, p.sku, p.name, p.hsn_code
        ORDER BY total_sales DESC
        """,
        tuple(params),
    )


def get_gst_summary(start_date=None, end_date=None):
    where = ["i.status = 'POSTED'"]
    params = []
    if start_date:
        where.append("i.invoice_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("i.invoice_date <= %s")
        params.append(end_date)
    clause = "WHERE " + " AND ".join(where)
    return fetch_all(
        f"""
        SELECT i.supply_type, ii.hsn_code, ii.gst_rate,
               COUNT(DISTINCT i.id) AS invoice_count,
               COALESCE(SUM(ii.qty_packets), 0) AS total_qty,
               COALESCE(SUM(ii.taxable_amount), 0) AS taxable_value,
               COALESCE(SUM(ii.cgst_amount), 0) AS cgst_amount,
               COALESCE(SUM(ii.sgst_amount), 0) AS sgst_amount,
               COALESCE(SUM(ii.igst_amount), 0) AS igst_amount,
               COALESCE(SUM(ii.line_total), 0) AS total_invoice_value
        FROM invoice_items ii
        JOIN invoices i ON i.id = ii.invoice_id
        {clause}
        GROUP BY i.supply_type, ii.hsn_code, ii.gst_rate
        ORDER BY i.supply_type, ii.hsn_code
        """,
        tuple(params),
    )


def get_production_variance_report(start_date=None, end_date=None):
    clause, params = _date_clause("pr.production_date", start_date, end_date)
    return fetch_all(
        f"""
        SELECT pr.batch_no, pr.production_date, p.name AS product_name,
               pr.expected_packets, pr.good_packets, pr.damaged_pouches,
               pr.wastage_qty, pr.cartons_used, pr.yield_variance_pct, pr.yield_abnormal,
               pr.total_cost, pr.cost_per_packet
        FROM production_runs pr
        JOIN products p ON p.id = pr.product_id
        {clause}
        ORDER BY pr.production_date DESC, pr.id DESC
        """,
        params,
    )


def get_material_variance_details():
    return fetch_all(
        """
        SELECT pr.batch_no, pr.production_date, p.name AS product_name,
               pc.item_type, COALESCE(rm.name, pm.name) AS item_name,
               pc.planned_qty, pc.actual_qty, pc.damaged_qty,
               pc.unit_rate, pc.total_cost, pc.variance_pct, pc.is_abnormal
        FROM production_consumptions pc
        JOIN production_runs pr ON pr.id = pc.production_run_id
        JOIN products p ON p.id = pr.product_id
        LEFT JOIN raw_materials rm ON pc.item_type = 'RAW_MATERIAL' AND rm.id = pc.item_id
        LEFT JOIN packaging_materials pm ON pc.item_type = 'PACKAGING_MATERIAL' AND pm.id = pc.item_id
        ORDER BY pr.production_date DESC, pr.id DESC, pc.id
        """
    )


def build_export_dataset(report_type, start_date=None, end_date=None):
    """Return (title, headers, rows) for CSV/Excel/PDF exports."""
    if report_type == "sales_register":
        data = get_sales_register(start_date, end_date)
        headers = ["Invoice No", "Date", "Customer", "GSTIN", "Place of Supply", "Type", "Taxable", "CGST", "SGST", "IGST", "Total", "Paid", "Outstanding", "Status"]
        rows = [[r["invoice_no"], r["invoice_date"], r["customer_name"], r["customer_gstin"], r["place_of_supply"], r["supply_type"], r["taxable_amount"], r["cgst_amount"], r["sgst_amount"], r["igst_amount"], r["total_amount"], r["paid_amount"], r["outstanding_amount"], r["status"]] for r in data]
        return "Sales Register", headers, rows
    if report_type == "gst_summary":
        data = get_gst_summary(start_date, end_date)
        headers = ["Supply Type", "HSN", "GST %", "Invoices", "Qty", "Taxable Value", "CGST", "SGST", "IGST", "Total Value"]
        rows = [[r["supply_type"], r["hsn_code"], r["gst_rate"], r["invoice_count"], r["total_qty"], r["taxable_value"], r["cgst_amount"], r["sgst_amount"], r["igst_amount"], r["total_invoice_value"]] for r in data]
        return "GSTR-1 / GSTR-3B Summary", headers, rows
    if report_type == "purchases":
        data = list_purchases(start_date, end_date)
        headers = ["Purchase No", "Date", "Supplier", "Supplier Inv", "Subtotal", "GST", "Total"]
        rows = [[r["purchase_no"], r["purchase_date"], r["supplier_name"], r["supplier_invoice_no"], r["subtotal"], r["gst_amount"], r["total_amount"]] for r in data]
        return "Purchase Register", headers, rows
    if report_type == "stock_summary":
        data = get_stock_summary()
        headers = ["Category", "Code", "Item", "Unit", "Opening", "Receipts", "Issues", "Closing", "Avg Rate", "Stock Value"]
        rows = [[r["item_type"], r["item_code"], r["item_name"], r["unit_code"], r["opening_qty"], r["total_receipts"], r["total_issues"], r["current_qty"], r["weighted_avg_rate"], r["stock_value"]] for r in data]
        return "Stock Summary", headers, rows
    if report_type == "stock_ledger":
        data = get_stock_ledger(limit=500)
        headers = ["Date", "Category", "Item", "Type", "In", "Out", "Rate", "Value", "Balance", "Doc No", "User"]
        rows = [[r["movement_date"].strftime("%Y-%m-%d %H:%M"), r["item_type"], r["item_name"], r["movement_type"], r["qty_in"], r["qty_out"], r["unit_rate"], r["total_value"], r["balance_qty"], r["source_doc_no"], r["user_name"]] for r in data]
        return "Stock Ledger", headers, rows
    if report_type == "production_variance":
        data = get_production_variance_report(start_date, end_date)
        headers = ["Batch No", "Date", "Product", "Expected", "Good Pkts", "Damaged", "Wastage", "Cartons", "Yield Var %", "Abnormal", "Total Cost", "Cost/Pkt"]
        rows = [[r["batch_no"], r["production_date"], r["product_name"], r["expected_packets"], r["good_packets"], r["damaged_pouches"], r["wastage_qty"], r["cartons_used"], r["yield_variance_pct"], "YES" if r["yield_abnormal"] else "NO", r["total_cost"], r["cost_per_packet"]] for r in data]
        return "Production & Variance Report", headers, rows
    if report_type == "costing":
        data = get_costing_summary()
        headers = ["Batch No", "Date", "Product", "Good Pkts", "Material", "Packaging", "Overhead", "Total Cost", "Cost/Pkt", "Selling Price", "Margin/Pkt"]
        rows = [[r["batch_no"], r["production_date"], r["product_name"], r["good_packets"], r["material_cost"], r["packaging_cost"], r["overhead_cost"], r["total_cost"], r["cost_per_packet_2dp"], r["selling_price_2dp"], r["margin_per_packet"]] for r in data]
        return "Production Costing Report", headers, rows
    if report_type == "payments_ageing":
        data = get_outstanding_and_ageing()
        headers = ["Customer", "State", "Invoices", "Invoiced", "Paid", "Outstanding", "0-30 Days", "31-60 Days", "60+ Days"]
        rows = [[r["customer_name"], r["state"], r["invoice_count"], r["total_invoiced"], r["total_paid"], r["total_outstanding"], r["bucket_0_30"], r["bucket_31_60"], r["bucket_60_plus"]] for r in data]
        return "Outstanding & Receivables Ageing", headers, rows
    data = list_payments(start_date, end_date)
    headers = ["Payment No", "Date", "Invoice No", "Customer", "Mode", "Reference", "Amount"]
    rows = [[r["payment_no"], r["payment_date"], r["invoice_no"], r["customer_name"], r["payment_mode"], r["reference_no"], r["amount"]] for r in data]
    return "Payments Collection Report", headers, rows
