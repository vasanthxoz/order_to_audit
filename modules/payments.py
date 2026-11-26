from datetime import date
from decimal import Decimal
from db import db_transaction, fetch_all
from modules.audit import log_audit


def _next_payment_no(cur):
    cur.execute("SELECT COUNT(*) AS cnt FROM payments")
    cnt = cur.fetchone()["cnt"] + 1
    return f"PAY-{cnt:05d}"


def record_payment(invoice_id, amount, payment_date=None, payment_mode="UPI", reference_no="", remarks="", user_id=None, username=""):
    """Record full or partial payment against a posted GST invoice."""
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    pay_date = payment_date or date.today()

    with db_transaction() as cur:
        cur.execute("SELECT * FROM invoices WHERE id = %s FOR UPDATE", (int(invoice_id),))
        inv = cur.fetchone()
        if not inv:
            raise ValueError("Invoice not found.")
        if inv["status"] != "POSTED":
            raise ValueError("Cannot record payment against a cancelled invoice.")

        outstanding = Decimal(str(inv["outstanding_amount"]))
        if amt > outstanding:
            raise ValueError(f"Payment Rs.{amt} exceeds outstanding balance Rs.{outstanding}.")

        payment_no = _next_payment_no(cur)
        cur.execute(
            """
            INSERT INTO payments (payment_no, invoice_id, customer_id, payment_date, amount, payment_mode, reference_no, remarks, recorded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payment_no, int(invoice_id), inv["customer_id"], pay_date, amt, payment_mode, reference_no, remarks, user_id),
        )
        pay_id = cur.fetchone()["id"]

        new_paid = Decimal(str(inv["paid_amount"])) + amt
        new_outstanding = Decimal(str(inv["total_amount"])) - new_paid
        cur.execute(
            "UPDATE invoices SET paid_amount = %s, outstanding_amount = %s WHERE id = %s",
            (new_paid, new_outstanding, int(invoice_id)),
        )

        log_audit(cur, user_id, username, "RECORD_PAYMENT", "PAYMENT", pay_id, f"{payment_no}: Rs.{amt} on {inv['invoice_no']}")
        return {"id": pay_id, "payment_no": payment_no, "outstanding_amount": new_outstanding}


def list_payments(start_date=None, end_date=None):
    where = []
    params = []
    if start_date:
        where.append("p.payment_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("p.payment_date <= %s")
        params.append(end_date)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return fetch_all(
        f"""
        SELECT p.*, i.invoice_no, c.name AS customer_name, u.full_name AS recorded_by_name
        FROM payments p
        JOIN invoices i ON i.id = p.invoice_id
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN users u ON u.id = p.recorded_by
        {clause}
        ORDER BY p.payment_date DESC, p.id DESC
        """,
        tuple(params),
    )


def get_outstanding_and_ageing():
    return fetch_all(
        """
        SELECT
            c.id AS customer_id,
            c.name AS customer_name,
            c.state,
            c.phone,
            COUNT(i.id) AS invoice_count,
            COALESCE(SUM(i.total_amount), 0) AS total_invoiced,
            COALESCE(SUM(i.paid_amount), 0) AS total_paid,
            COALESCE(SUM(i.outstanding_amount), 0) AS total_outstanding,
            COALESCE(SUM(CASE WHEN CURRENT_DATE - i.invoice_date <= 30 THEN i.outstanding_amount ELSE 0 END), 0) AS bucket_0_30,
            COALESCE(SUM(CASE WHEN CURRENT_DATE - i.invoice_date BETWEEN 31 AND 60 THEN i.outstanding_amount ELSE 0 END), 0) AS bucket_31_60,
            COALESCE(SUM(CASE WHEN CURRENT_DATE - i.invoice_date > 60 THEN i.outstanding_amount ELSE 0 END), 0) AS bucket_60_plus
        FROM customers c
        JOIN invoices i ON i.customer_id = c.id AND i.status = 'POSTED'
        GROUP BY c.id, c.name, c.state, c.phone
        ORDER BY total_outstanding DESC
        """
    )
