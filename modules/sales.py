from decimal import Decimal, ROUND_HALF_UP
from db import db_transaction, fetch_all, fetch_one
from modules.audit import log_audit


def _next_order_no(cur):
    cur.execute("SELECT COUNT(*) AS cnt FROM sales_orders")
    cnt = cur.fetchone()["cnt"] + 1
    return f"SO-{cnt:05d}"


def create_sales_order(customer_id, salesman_id, order_date, items, remarks="", username=""):
    """
    Create a sales order with automatic price lookup from default price list
    and live finished-goods stock availability check (flags shortage warnings).
    items: list of {product_id, qty_packets}
    """
    if not items:
        raise ValueError("At least one product item is required.")

    with db_transaction() as cur:
        order_no = _next_order_no(cur)
        subtotal = Decimal("0.00")
        gst_total = Decimal("0.00")
        shortages = []
        prepared = []

        for it in items:
            product_id = int(it["product_id"])
            qty = Decimal(str(it["qty_packets"]))
            if qty <= 0:
                raise ValueError("Order quantity must be greater than zero.")

            cur.execute(
                """
                SELECT p.id, p.name, p.gst_rate,
                       COALESCE(pli.selling_price, 0) AS selling_price,
                       COALESCE(ib.current_qty, 0) AS available_qty
                FROM products p
                LEFT JOIN price_lists pl ON pl.is_default = TRUE AND pl.is_active = TRUE
                LEFT JOIN price_list_items pli ON pli.price_list_id = pl.id AND pli.product_id = p.id
                LEFT JOIN inventory_balances ib ON ib.item_type = 'FINISHED_GOOD' AND ib.item_id = p.id
                WHERE p.id = %s
                """,
                (product_id,),
            )
            prod = cur.fetchone()
            if not prod:
                raise ValueError(f"Product #{product_id} not found.")

            unit_price = Decimal(str(prod["selling_price"]))
            gst_rate = Decimal(str(prod["gst_rate"]))
            avail = Decimal(str(prod["available_qty"]))
            if avail < qty:
                shortage = qty - avail
                shortages.append(f"{prod['name']}: requested {qty}, available {avail}, shortage {shortage}")

            taxable = (qty * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            gst_amt = (taxable * gst_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_total = taxable + gst_amt
            subtotal += taxable
            gst_total += gst_amt

            prepared.append({
                "product_id": product_id,
                "qty_packets": qty,
                "unit_price": unit_price,
                "gst_rate": gst_rate,
                "taxable_amount": taxable,
                "gst_amount": gst_amt,
                "line_total": line_total,
            })

        total_amount = subtotal + gst_total
        has_shortage = len(shortages) > 0
        shortage_note = "; ".join(shortages)

        cur.execute(
            """
            INSERT INTO sales_orders (
                order_no, customer_id, salesman_id, order_date, status,
                subtotal, gst_amount, total_amount, has_stock_shortage, shortage_note, remarks
            )
            VALUES (%s, %s, %s, %s, 'Submitted', %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (order_no, int(customer_id), int(salesman_id), order_date, subtotal, gst_total, total_amount, has_shortage, shortage_note, remarks),
        )
        order_id = cur.fetchone()["id"]

        for p in prepared:
            cur.execute(
                """
                INSERT INTO sales_order_items (
                    order_id, product_id, qty_packets, unit_price, gst_rate,
                    taxable_amount, gst_amount, line_total
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (order_id, p["product_id"], p["qty_packets"], p["unit_price"], p["gst_rate"], p["taxable_amount"], p["gst_amount"], p["line_total"]),
            )

        log_audit(cur, salesman_id, username, "CREATE_ORDER", "SALES_ORDER", order_id, f"Created {order_no} total Rs.{total_amount}")
        return {
            "id": order_id,
            "order_no": order_no,
            "has_stock_shortage": has_shortage,
            "shortage_note": shortage_note,
            "total_amount": total_amount,
        }


def verify_and_update_order_status(order_id, new_status, admin_id, admin_username="", remarks=""):
    """Admin verifies stock and approves or rejects a Submitted order."""
    if new_status not in ("Approved", "Rejected"):
        raise ValueError("Invalid verification status.")

    with db_transaction() as cur:
        cur.execute("SELECT * FROM sales_orders WHERE id = %s FOR UPDATE", (int(order_id),))
        order = cur.fetchone()
        if not order:
            raise ValueError("Order not found.")
        if order["status"] != "Submitted":
            raise ValueError(f"Order {order['order_no']} is already {order['status']}.")

        if new_status == "Approved":
            cur.execute("SELECT product_id, qty_packets FROM sales_order_items WHERE order_id = %s", (int(order_id),))
            for item in cur.fetchall():
                cur.execute(
                    "SELECT current_qty FROM inventory_balances WHERE item_type = 'FINISHED_GOOD' AND item_id = %s",
                    (item["product_id"],),
                )
                bal = cur.fetchone()
                avail = Decimal(str(bal["current_qty"])) if bal else Decimal("0")
                if avail < Decimal(str(item["qty_packets"])):
                    shortage = Decimal(str(item["qty_packets"])) - avail
                    raise ValueError(
                        f"Cannot approve: insufficient finished-goods stock (available {avail}, requested {item['qty_packets']}, shortage {shortage})."
                    )

        cur.execute(
            """
            UPDATE sales_orders
            SET status = %s, verified_by = %s, verified_at = NOW(),
                remarks = CASE WHEN %s <> '' THEN %s ELSE remarks END
            WHERE id = %s
            """,
            (new_status, admin_id, remarks, remarks, int(order_id)),
        )
        log_audit(cur, admin_id, admin_username, f"ORDER_{new_status.upper()}", "SALES_ORDER", int(order_id), f"{order['order_no']} -> {new_status}")


def list_orders(salesman_id=None, status=None):
    where = []
    params = []
    if salesman_id:
        where.append("so.salesman_id = %s")
        params.append(int(salesman_id))
    if status:
        where.append("so.status = %s")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return fetch_all(
        f"""
        SELECT so.*, c.name AS customer_name, c.state AS customer_state,
               u.full_name AS salesman_name
        FROM sales_orders so
        JOIN customers c ON c.id = so.customer_id
        JOIN users u ON u.id = so.salesman_id
        {clause}
        ORDER BY so.order_date DESC, so.id DESC
        """,
        tuple(params),
    )


def get_order_details(order_id):
    order = fetch_one(
        """
        SELECT so.*, c.name AS customer_name, c.state AS customer_state, c.state_code AS customer_state_code,
               c.gstin AS customer_gstin, u.full_name AS salesman_name
        FROM sales_orders so
        JOIN customers c ON c.id = so.customer_id
        JOIN users u ON u.id = so.salesman_id
        WHERE so.id = %s
        """,
        (int(order_id),),
    )
    if not order:
        return None
    items = fetch_all(
        """
        SELECT soi.*, p.name AS product_name, p.hsn_code,
               COALESCE(ib.current_qty, 0) AS available_qty
        FROM sales_order_items soi
        JOIN products p ON p.id = soi.product_id
        LEFT JOIN inventory_balances ib ON ib.item_type = 'FINISHED_GOOD' AND ib.item_id = p.id
        WHERE soi.order_id = %s
        """,
        (int(order_id),),
    )
    return {"order": order, "items": items}
