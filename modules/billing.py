from datetime import date
from decimal import Decimal
from db import db_transaction, fetch_all, fetch_one
from modules.gst import compute_gst_split, get_financial_year
from modules.audit import log_audit


def _next_invoice_no(cur, fy):
    cur.execute("SELECT COUNT(*) AS cnt FROM invoices WHERE financial_year = %s", (fy,))
    cnt = cur.fetchone()["cnt"] + 1
    return f"INV/{fy}/{cnt:04d}"


def _next_credit_note_no(cur, fy):
    cur.execute("SELECT COUNT(*) AS cnt FROM credit_notes")
    cnt = cur.fetchone()["cnt"] + 1
    return f"CN/{fy}/{cnt:04d}"


def generate_gst_invoice(order_id, invoice_date=None, user_id=None, username=""):
    """Generate a GST Tax Invoice from an Approved sales order."""
    inv_date = invoice_date or date.today()
    if isinstance(inv_date, str):
        inv_date = date.fromisoformat(inv_date)
    fy = get_financial_year(inv_date)

    with db_transaction() as cur:
        cur.execute(
            """
            SELECT so.*, c.state AS customer_state, c.state_code AS customer_state_code
            FROM sales_orders so
            JOIN customers c ON c.id = so.customer_id
            WHERE so.id = %s
            FOR UPDATE
            """,
            (int(order_id),),
        )
        order = cur.fetchone()
        if not order:
            raise ValueError("Sales order not found.")
        if order["status"] != "Approved":
            raise ValueError(f"Only Approved orders can be invoiced (current: {order['status']}).")

        cur.execute(
            """
            SELECT soi.*, p.hsn_code
            FROM sales_order_items soi
            JOIN products p ON p.id = soi.product_id
            WHERE soi.order_id = %s
            """,
            (int(order_id),),
        )
        items = cur.fetchall()
        if not items:
            raise ValueError("Order has no items.")

        invoice_no = _next_invoice_no(cur, fy)
        place_of_supply = f"{order['customer_state']} ({order['customer_state_code']})"

        total_taxable = Decimal("0.00")
        total_cgst = Decimal("0.00")
        total_sgst = Decimal("0.00")
        total_igst = Decimal("0.00")
        supply_type = "INTRA_STATE"
        prepared = []

        for it in items:
            split = compute_gst_split(it["taxable_amount"], it["gst_rate"], order["customer_state"])
            supply_type = split["supply_type"]
            total_taxable += Decimal(str(it["taxable_amount"]))
            total_cgst += split["cgst_amount"]
            total_sgst += split["sgst_amount"]
            total_igst += split["igst_amount"]
            prepared.append((it, split))

        grand_total = total_taxable + total_cgst + total_sgst + total_igst

        cur.execute(
            """
            INSERT INTO invoices (
                invoice_no, financial_year, order_id, customer_id, invoice_date,
                place_of_supply, supply_type, taxable_amount,
                cgst_amount, sgst_amount, igst_amount, total_amount,
                paid_amount, outstanding_amount, status, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0.00, %s, 'POSTED', %s)
            RETURNING id
            """,
            (
                invoice_no,
                fy,
                int(order_id),
                order["customer_id"],
                inv_date,
                place_of_supply,
                supply_type,
                total_taxable,
                total_cgst,
                total_sgst,
                total_igst,
                grand_total,
                grand_total,
                user_id,
            ),
        )
        invoice_id = cur.fetchone()["id"]

        for it, split in prepared:
            cur.execute(
                """
                INSERT INTO invoice_items (
                    invoice_id, product_id, hsn_code, qty_packets, unit_price,
                    taxable_amount, gst_rate, cgst_rate, cgst_amount,
                    sgst_rate, sgst_amount, igst_rate, igst_amount, line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    it["product_id"],
                    it["hsn_code"],
                    it["qty_packets"],
                    it["unit_price"],
                    it["taxable_amount"],
                    it["gst_rate"],
                    split["cgst_rate"],
                    split["cgst_amount"],
                    split["sgst_rate"],
                    split["sgst_amount"],
                    split["igst_rate"],
                    split["igst_amount"],
                    split["line_total"],
                ),
            )

        cur.execute("UPDATE sales_orders SET status = 'Invoiced' WHERE id = %s", (int(order_id),))
        log_audit(cur, user_id, username, "GENERATE_INVOICE", "INVOICE", invoice_id, f"Generated {invoice_no} total Rs.{grand_total}")
        return {"id": invoice_id, "invoice_no": invoice_no, "total_amount": grand_total}


def cancel_invoice_with_credit_note(invoice_id, reason, user_id=None, username=""):
    """Cancel a posted GST invoice by issuing a Credit Note (never deletes invoices)."""
    with db_transaction() as cur:
        cur.execute("SELECT * FROM invoices WHERE id = %s FOR UPDATE", (int(invoice_id),))
        inv = cur.fetchone()
        if not inv:
            raise ValueError("Invoice not found.")
        if inv["status"] == "CANCELLED":
            raise ValueError("Invoice is already cancelled.")

        cn_no = _next_credit_note_no(cur, inv["financial_year"])
        cur.execute(
            """
            INSERT INTO credit_notes (
                credit_note_no, invoice_id, credit_date, reason,
                taxable_amount, cgst_amount, sgst_amount, igst_amount, total_amount, created_by
            )
            VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                cn_no,
                int(invoice_id),
                reason.strip(),
                inv["taxable_amount"],
                inv["cgst_amount"],
                inv["sgst_amount"],
                inv["igst_amount"],
                inv["total_amount"],
                user_id,
            ),
        )
        cn_id = cur.fetchone()["id"]
        cur.execute("UPDATE invoices SET status = 'CANCELLED', outstanding_amount = 0.00 WHERE id = %s", (int(invoice_id),))
        log_audit(cur, user_id, username, "CANCEL_INVOICE_CREDIT_NOTE", "INVOICE", int(invoice_id), f"Issued {cn_no} for {inv['invoice_no']}: {reason}")
        return {"credit_note_id": cn_id, "credit_note_no": cn_no}


def list_invoices():
    return fetch_all(
        """
        SELECT i.*, c.name AS customer_name, c.gstin AS customer_gstin, so.order_no, so.status AS order_status
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        JOIN sales_orders so ON so.id = i.order_id
        ORDER BY i.invoice_date DESC, i.id DESC
        """
    )


def get_invoice_details(invoice_id):
    invoice = fetch_one(
        """
        SELECT i.*, c.name AS customer_name, c.gstin AS customer_gstin, c.state AS customer_state,
               c.address AS customer_address, c.phone AS customer_phone, so.order_no, so.status AS order_status
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        JOIN sales_orders so ON so.id = i.order_id
        WHERE i.id = %s
        """,
        (int(invoice_id),),
    )
    if not invoice:
        return None
    items = fetch_all(
        """
        SELECT ii.*, p.name AS product_name, p.sku
        FROM invoice_items ii
        JOIN products p ON p.id = ii.product_id
        WHERE ii.invoice_id = %s
        """,
        (int(invoice_id),),
    )
    customer = {
        "name": invoice["customer_name"],
        "gstin": invoice["customer_gstin"],
        "state": invoice["customer_state"],
        "address": invoice["customer_address"],
        "phone": invoice["customer_phone"],
    }
    return {"invoice": invoice, "items": items, "customer": customer}


def list_credit_notes():
    return fetch_all(
        """
        SELECT cn.*, i.invoice_no, c.name AS customer_name
        FROM credit_notes cn
        JOIN invoices i ON i.id = cn.invoice_id
        JOIN customers c ON c.id = i.customer_id
        ORDER BY cn.credit_date DESC, cn.id DESC
        """
    )
