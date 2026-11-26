from datetime import date
from db import db_transaction, fetch_all
from modules.inventory import record_stock_movement
from modules.audit import log_audit


def _next_dispatch_no(cur):
    cur.execute("SELECT COUNT(*) AS cnt FROM dispatches")
    cnt = cur.fetchone()["cnt"] + 1
    return f"DSP-{cnt:05d}"


def dispatch_order(order_id, dispatch_date=None, vehicle_no="", transporter="", lr_no="", remarks="", user_id=None, username=""):
    """
    Dispatch an Invoiced order:
    - Reduces finished-goods stock atomically via stock_ledger
    - Marks order status as 'Dispatched'
    """
    dsp_date = dispatch_date or date.today()
    with db_transaction() as cur:
        cur.execute("SELECT * FROM sales_orders WHERE id = %s FOR UPDATE", (int(order_id),))
        order = cur.fetchone()
        if not order:
            raise ValueError("Sales order not found.")
        if order["status"] != "Invoiced":
            raise ValueError(f"Only Invoiced orders can be dispatched (current: {order['status']}).")

        cur.execute("SELECT * FROM invoices WHERE order_id = %s AND status = 'POSTED'", (int(order_id),))
        inv = cur.fetchone()
        if not inv:
            raise ValueError("A posted GST invoice is required before dispatch.")

        cur.execute(
            """
            SELECT soi.*, p.unit_id, p.name AS product_name
            FROM sales_order_items soi
            JOIN products p ON p.id = soi.product_id
            WHERE soi.order_id = %s
            """,
            (int(order_id),),
        )
        items = cur.fetchall()

        dispatch_no = _next_dispatch_no(cur)
        cur.execute(
            """
            INSERT INTO dispatches (dispatch_no, order_id, invoice_id, dispatch_date, vehicle_no, transporter, lr_no, remarks, dispatched_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (dispatch_no, int(order_id), inv["id"], dsp_date, vehicle_no, transporter, lr_no, remarks, user_id),
        )
        dispatch_id = cur.fetchone()["id"]

        for it in items:
            record_stock_movement(
                cur=cur,
                item_type="FINISHED_GOOD",
                item_id=it["product_id"],
                unit_id=it["unit_id"],
                movement_type="DISPATCH_OUT",
                qty_out=it["qty_packets"],
                source_doc_type="DISPATCH",
                source_doc_id=dispatch_id,
                source_doc_no=dispatch_no,
                remarks=f"Dispatched {it['qty_packets']} pkt of {it['product_name']} for {inv['invoice_no']}",
                user_id=user_id,
            )

        cur.execute("UPDATE sales_orders SET status = 'Dispatched' WHERE id = %s", (int(order_id),))
        log_audit(cur, user_id, username, "DISPATCH_ORDER", "DISPATCH", dispatch_id, f"Dispatched {order['order_no']} ({dispatch_no})")
        return {"id": dispatch_id, "dispatch_no": dispatch_no}


def list_dispatches():
    return fetch_all(
        """
        SELECT d.*, so.order_no, i.invoice_no, c.name AS customer_name, u.full_name AS dispatched_by_name
        FROM dispatches d
        JOIN sales_orders so ON so.id = d.order_id
        JOIN invoices i ON i.id = d.invoice_id
        JOIN customers c ON c.id = so.customer_id
        LEFT JOIN users u ON u.id = d.dispatched_by
        ORDER BY d.dispatch_date DESC, d.id DESC
        """
    )
