from decimal import Decimal, ROUND_HALF_UP
from db import db_transaction, fetch_all
from modules.inventory import record_stock_movement
from modules.audit import log_audit


def _next_purchase_no(cur):
    cur.execute("SELECT COUNT(*) AS cnt FROM purchases")
    cnt = cur.fetchone()["cnt"] + 1
    return f"PO-{cnt:05d}"


def record_purchase(supplier_id, purchase_date, supplier_invoice_no, items, notes, user_id, username=""):
    """
    Record a purchase of raw/packaging materials and atomically increase stock
    using weighted average valuation.
    items: list of dicts {item_type, item_id, qty, rate, gst_rate}
    """
    if not items:
        raise ValueError("At least one purchase line item is required.")

    with db_transaction() as cur:
        purchase_no = _next_purchase_no(cur)
        subtotal = Decimal("0.00")
        gst_total = Decimal("0.00")

        prepared = []
        for it in items:
            item_type = it["item_type"]
            item_id = int(it["item_id"])
            qty = Decimal(str(it["qty"]))
            rate = Decimal(str(it["rate"]))
            gst_rate = Decimal(str(it.get("gst_rate", 0)))
            if qty <= 0 or rate < 0:
                raise ValueError("Quantity must be > 0 and rate >= 0.")

            line_sub = (qty * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_gst = (line_sub * gst_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_total = line_sub + line_gst
            subtotal += line_sub
            gst_total += line_gst

            table = "raw_materials" if item_type == "RAW_MATERIAL" else "packaging_materials"
            cur.execute(f"SELECT unit_id, name FROM {table} WHERE id = %s", (item_id,))
            mat = cur.fetchone()
            if not mat:
                raise ValueError(f"{item_type} #{item_id} not found.")

            prepared.append({
                "item_type": item_type,
                "item_id": item_id,
                "unit_id": mat["unit_id"],
                "name": mat["name"],
                "qty": qty,
                "rate": rate,
                "gst_rate": gst_rate,
                "line_total": line_total,
            })

        grand_total = subtotal + gst_total
        cur.execute(
            """
            INSERT INTO purchases (purchase_no, supplier_id, purchase_date, supplier_invoice_no, subtotal, gst_amount, total_amount, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (purchase_no, int(supplier_id), purchase_date, supplier_invoice_no, subtotal, gst_total, grand_total, notes, user_id),
        )
        purchase_id = cur.fetchone()["id"]

        for p in prepared:
            cur.execute(
                """
                INSERT INTO purchase_items (purchase_id, item_type, item_id, qty, rate, gst_rate, line_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (purchase_id, p["item_type"], p["item_id"], p["qty"], p["rate"], p["gst_rate"], p["line_total"]),
            )
            record_stock_movement(
                cur=cur,
                item_type=p["item_type"],
                item_id=p["item_id"],
                unit_id=p["unit_id"],
                movement_type="RECEIPT",
                qty_in=p["qty"],
                unit_rate=p["rate"],
                source_doc_type="PURCHASE",
                source_doc_id=purchase_id,
                source_doc_no=purchase_no,
                remarks=f"Purchase {purchase_no} ({p['name']})",
                user_id=user_id,
            )

        log_audit(cur, user_id, username, "CREATE_PURCHASE", "PURCHASE", purchase_id, f"Recorded {purchase_no} total Rs.{grand_total}")
        return {"id": purchase_id, "purchase_no": purchase_no, "total_amount": grand_total}


def list_purchases(start_date=None, end_date=None):
    where = []
    params = []
    if start_date:
        where.append("p.purchase_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("p.purchase_date <= %s")
        params.append(end_date)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return fetch_all(
        f"""
        SELECT p.*, s.name AS supplier_name, u.full_name AS created_by_name
        FROM purchases p
        JOIN suppliers s ON s.id = p.supplier_id
        LEFT JOIN users u ON u.id = p.created_by
        {clause}
        ORDER BY p.purchase_date DESC, p.id DESC
        """,
        tuple(params),
    )
