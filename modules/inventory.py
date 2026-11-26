from decimal import Decimal, ROUND_HALF_UP
from db import fetch_all, fetch_one


def record_stock_movement(
    cur,
    item_type,
    item_id,
    unit_id,
    movement_type,
    qty_in=Decimal("0"),
    qty_out=Decimal("0"),
    unit_rate=None,
    source_doc_type="SYSTEM",
    source_doc_id=None,
    source_doc_no=None,
    remarks="",
    user_id=None,
):
    """
    Atomically update inventory_balances and append an immutable stock_ledger row.
    Maintains weighted average valuation on receipts and prevents negative stock on issues.
    """
    qty_in = Decimal(str(qty_in))
    qty_out = Decimal(str(qty_out))

    cur.execute(
        """
        SELECT id, current_qty, weighted_avg_rate
        FROM inventory_balances
        WHERE item_type = %s AND item_id = %s
        FOR UPDATE
        """,
        (item_type, int(item_id)),
    )
    bal = cur.fetchone()

    if not bal:
        cur.execute(
            """
            INSERT INTO inventory_balances (item_type, item_id, unit_id, opening_qty, current_qty, weighted_avg_rate)
            VALUES (%s, %s, %s, 0, 0, 0)
            RETURNING id, current_qty, weighted_avg_rate
            """,
            (item_type, int(item_id), int(unit_id)),
        )
        bal = cur.fetchone()

    current_qty = Decimal(str(bal["current_qty"]))
    current_rate = Decimal(str(bal["weighted_avg_rate"]))

    if qty_in > 0:
        in_rate = Decimal(str(unit_rate)) if unit_rate is not None else current_rate
        new_qty = current_qty + qty_in
        if movement_type == "OPENING":
            new_rate = in_rate
            cur.execute(
                "UPDATE inventory_balances SET opening_qty = %s WHERE id = %s",
                (qty_in, bal["id"]),
            )
        elif new_qty > 0:
            total_val = (current_qty * current_rate) + (qty_in * in_rate)
            new_rate = (total_val / new_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        else:
            new_rate = current_rate
        applied_rate = in_rate
        total_value = (qty_in * applied_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif qty_out > 0:
        if current_qty < qty_out:
            raise ValueError(
                f"Insufficient stock for {item_type} #{item_id}: available {current_qty}, requested {qty_out}."
            )
        new_qty = current_qty - qty_out
        new_rate = current_rate
        applied_rate = current_rate
        total_value = (qty_out * applied_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        raise ValueError("Either qty_in or qty_out must be positive.")

    cur.execute(
        """
        UPDATE inventory_balances
        SET current_qty = %s, weighted_avg_rate = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (new_qty, new_rate, bal["id"]),
    )

    cur.execute(
        """
        INSERT INTO stock_ledger (
            item_type, item_id, movement_type, qty_in, qty_out,
            unit_rate, total_value, balance_qty,
            source_doc_type, source_doc_id, source_doc_no, remarks, user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            item_type,
            int(item_id),
            movement_type,
            qty_in,
            qty_out,
            applied_rate,
            total_value,
            new_qty,
            source_doc_type,
            source_doc_id,
            source_doc_no,
            remarks,
            user_id,
        ),
    )
    return {"balance_qty": new_qty, "weighted_avg_rate": new_rate, "applied_rate": applied_rate}


def get_item_balance(item_type, item_id):
    return fetch_one(
        """
        SELECT ib.*, u.code AS unit_code
        FROM inventory_balances ib
        JOIN units u ON u.id = ib.unit_id
        WHERE ib.item_type = %s AND ib.item_id = %s
        """,
        (item_type, int(item_id)),
    )


def get_stock_summary(item_type=None):
    where = "WHERE ib.item_type = %s" if item_type else ""
    params = (item_type,) if item_type else ()
    return fetch_all(
        f"""
        SELECT
            ib.item_type,
            ib.item_id,
            COALESCE(rm.code, pm.code, p.sku) AS item_code,
            COALESCE(rm.name, pm.name, p.name) AS item_name,
            u.code AS unit_code,
            ib.opening_qty,
            COALESCE(SUM(CASE WHEN sl.movement_type IN ('RECEIPT', 'PRODUCTION_IN') THEN sl.qty_in ELSE 0 END), 0) AS total_receipts,
            COALESCE(SUM(CASE WHEN sl.movement_type IN ('ISSUE', 'DISPATCH_OUT') THEN sl.qty_out ELSE 0 END), 0) AS total_issues,
            COALESCE(SUM(CASE WHEN sl.movement_type = 'ADJUSTMENT' THEN (sl.qty_in - sl.qty_out) ELSE 0 END), 0) AS total_adjustments,
            ib.current_qty,
            ib.weighted_avg_rate,
            ROUND(ib.current_qty * ib.weighted_avg_rate, 2) AS stock_value,
            COALESCE(rm.reorder_level, pm.reorder_level, p.reorder_level, 0) AS reorder_level
        FROM inventory_balances ib
        JOIN units u ON u.id = ib.unit_id
        LEFT JOIN raw_materials rm ON ib.item_type = 'RAW_MATERIAL' AND rm.id = ib.item_id
        LEFT JOIN packaging_materials pm ON ib.item_type = 'PACKAGING_MATERIAL' AND pm.id = ib.item_id
        LEFT JOIN products p ON ib.item_type = 'FINISHED_GOOD' AND p.id = ib.item_id
        LEFT JOIN stock_ledger sl ON sl.item_type = ib.item_type AND sl.item_id = ib.item_id
        {where}
        GROUP BY ib.id, ib.item_type, ib.item_id, rm.code, pm.code, p.sku, rm.name, pm.name, p.name,
                 u.code, ib.opening_qty, ib.current_qty, ib.weighted_avg_rate,
                 rm.reorder_level, pm.reorder_level, p.reorder_level
        ORDER BY ib.item_type, item_name
        """,
        params,
    )


def get_stock_ledger(item_type=None, limit=300):
    where = "WHERE sl.item_type = %s" if item_type else ""
    params = (item_type, limit) if item_type else (limit,)
    return fetch_all(
        f"""
        SELECT sl.*,
               COALESCE(rm.name, pm.name, p.name) AS item_name,
               u.full_name AS user_name
        FROM stock_ledger sl
        LEFT JOIN raw_materials rm ON sl.item_type = 'RAW_MATERIAL' AND rm.id = sl.item_id
        LEFT JOIN packaging_materials pm ON sl.item_type = 'PACKAGING_MATERIAL' AND pm.id = sl.item_id
        LEFT JOIN products p ON sl.item_type = 'FINISHED_GOOD' AND p.id = sl.item_id
        LEFT JOIN users u ON u.id = sl.user_id
        {where}
        ORDER BY sl.movement_date DESC, sl.id DESC
        LIMIT %s
        """,
        params,
    )


def get_low_stock_alerts():
    return [row for row in get_stock_summary() if Decimal(str(row["current_qty"])) <= Decimal(str(row["reorder_level"]))]
