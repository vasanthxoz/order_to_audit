from decimal import Decimal, ROUND_HALF_UP
from db import db_transaction, fetch_all, fetch_one
from modules.inventory import record_stock_movement
from modules.variance import calculate_variance, get_tolerance_pct
from modules.audit import log_audit


def _next_batch_no(cur):
    cur.execute("SELECT COUNT(*) AS cnt FROM production_runs")
    cnt = cur.fetchone()["cnt"] + 1
    return f"BATCH-{cnt:05d}"


def execute_production_run(
    bom_id,
    production_date,
    good_packets,
    damaged_pouches,
    wastage_qty,
    cartons_used,
    raw_actuals,
    overheads=None,
    notes="",
    user_id=None,
    username="",
):
    """
    Execute a production run atomically:
    - Deducts raw materials & packaging materials from stock
    - Adds good_packets to finished goods stock
    - Computes material/yield variances against BOM & tolerance
    - Computes material, packaging, overhead, total cost & cost per packet
    """
    good_packets = Decimal(str(good_packets))
    damaged_pouches = Decimal(str(damaged_pouches or 0))
    wastage_qty = Decimal(str(wastage_qty or 0))
    cartons_used = Decimal(str(cartons_used or 0))

    if good_packets <= 0:
        raise ValueError("Good packets must be greater than zero.")

    tol = get_tolerance_pct()

    with db_transaction() as cur:
        cur.execute(
            """
            SELECT bh.*, p.unit_id AS product_unit_id, p.name AS product_name
            FROM bom_headers bh
            JOIN products p ON p.id = bh.product_id
            WHERE bh.id = %s
            """,
            (int(bom_id),),
        )
        bom = cur.fetchone()
        if not bom:
            raise ValueError("BOM not found.")

        cur.execute(
            """
            SELECT bi.*,
                   COALESCE(rm.code, pm.code) AS item_code,
                   COALESCE(rm.name, pm.name) AS item_name
            FROM bom_items bi
            LEFT JOIN raw_materials rm ON bi.item_type = 'RAW_MATERIAL' AND rm.id = bi.item_id
            LEFT JOIN packaging_materials pm ON bi.item_type = 'PACKAGING_MATERIAL' AND pm.id = bi.item_id
            WHERE bi.bom_id = %s
            ORDER BY bi.item_type ASC
            """,
            (int(bom_id),),
        )
        bom_items = cur.fetchall()

        batch_no = _next_batch_no(cur)
        expected_packets = Decimal(str(bom["expected_output_packets"]))
        yield_var_pct, yield_abnormal = calculate_variance(expected_packets, good_packets, tol)

        cur.execute(
            """
            INSERT INTO production_runs (
                batch_no, bom_id, product_id, production_date, expected_packets,
                good_packets, damaged_pouches, wastage_qty, cartons_used,
                yield_variance_pct, yield_abnormal, notes, supervisor_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                batch_no,
                int(bom_id),
                bom["product_id"],
                production_date,
                expected_packets,
                good_packets,
                damaged_pouches,
                wastage_qty,
                cartons_used,
                yield_var_pct,
                yield_abnormal,
                notes,
                user_id,
            ),
        )
        run_id = cur.fetchone()["id"]

        material_cost = Decimal("0.00")
        packaging_cost = Decimal("0.00")

        for bi in bom_items:
            item_type = bi["item_type"]
            item_id = bi["item_id"]
            planned_qty = Decimal(str(bi["standard_qty"]))
            damaged_qty = Decimal("0.000")

            if item_type == "RAW_MATERIAL":
                # raw_actuals keyed by item_id (int or str); only used for RAW_MATERIAL
                actual_qty = Decimal(str(
                    raw_actuals.get(item_id,
                    raw_actuals.get(str(item_id), planned_qty))
                ))
            else:
                code = (bi["item_code"] or "").upper()
                name_low = (bi["item_name"] or "").lower()
                if "POUCH" in code or "pouch" in name_low:
                    actual_qty = good_packets + damaged_pouches
                    damaged_qty = damaged_pouches
                elif "CARTON" in code or "carton" in name_low:
                    actual_qty = cartons_used
                else:
                    actual_qty = planned_qty

            mov = record_stock_movement(
                cur=cur,
                item_type=item_type,
                item_id=item_id,
                unit_id=bi["unit_id"],
                movement_type="ISSUE",
                qty_out=actual_qty,
                source_doc_type="PRODUCTION",
                source_doc_id=run_id,
                source_doc_no=batch_no,
                remarks=f"Issued for {batch_no} ({bi['item_name']})",
                user_id=user_id,
            )
            applied_rate = Decimal(str(mov["applied_rate"]))
            line_cost = (actual_qty * applied_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            if item_type == "RAW_MATERIAL":
                material_cost += line_cost
            else:
                packaging_cost += line_cost

            var_pct, is_abnormal = calculate_variance(planned_qty, actual_qty, tol)
            cur.execute(
                """
                INSERT INTO production_consumptions (
                    production_run_id, item_type, item_id, planned_qty, actual_qty,
                    damaged_qty, unit_rate, total_cost, variance_pct, is_abnormal
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (run_id, item_type, item_id, planned_qty, actual_qty, damaged_qty, applied_rate, line_cost, var_pct, is_abnormal),
            )

        overhead_cost = Decimal("0.00")
        if overheads:
            for oh in overheads:
                amt = Decimal(str(oh.get("amount", 0)))
                if amt > 0:
                    overhead_cost += amt
                    cur.execute(
                        """
                        INSERT INTO production_overheads (production_run_id, expense_type, description, amount, created_by)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (run_id, oh["expense_type"], oh.get("description", ""), amt, user_id),
                    )

        total_cost = (material_cost + packaging_cost + overhead_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cost_per_packet = (total_cost / good_packets).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        cur.execute(
            """
            UPDATE production_runs
            SET material_cost = %s, packaging_cost = %s, overhead_cost = %s,
                total_cost = %s, cost_per_packet = %s
            WHERE id = %s
            """,
            (material_cost, packaging_cost, overhead_cost, total_cost, cost_per_packet, run_id),
        )

        record_stock_movement(
            cur=cur,
            item_type="FINISHED_GOOD",
            item_id=bom["product_id"],
            unit_id=bom["product_unit_id"],
            movement_type="PRODUCTION_IN",
            qty_in=good_packets,
            unit_rate=cost_per_packet,
            source_doc_type="PRODUCTION",
            source_doc_id=run_id,
            source_doc_no=batch_no,
            remarks=f"Produced {good_packets} packets of {bom['product_name']}",
            user_id=user_id,
        )

        log_audit(
            cur,
            user_id,
            username,
            "CREATE_PRODUCTION",
            "PRODUCTION",
            run_id,
            f"Batch {batch_no}: {good_packets} good packets, total cost Rs.{total_cost}",
        )
        return {
            "id": run_id,
            "batch_no": batch_no,
            "yield_variance_pct": yield_var_pct,
            "total_cost": total_cost,
            "cost_per_packet": cost_per_packet,
        }


def add_production_overhead(production_run_id, expense_type, description, amount, user_id=None, username=""):
    """Add an overhead expense (labour, gas/power, other) to a production run and recalculate costing."""
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("Overhead amount must be greater than zero.")

    with db_transaction() as cur:
        cur.execute("SELECT * FROM production_runs WHERE id = %s FOR UPDATE", (int(production_run_id),))
        run = cur.fetchone()
        if not run:
            raise ValueError("Production run not found.")

        cur.execute(
            """
            INSERT INTO production_overheads (production_run_id, expense_type, description, amount, created_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(production_run_id), expense_type, description, amt, user_id),
        )

        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) AS oh_total FROM production_overheads WHERE production_run_id = %s",
            (int(production_run_id),),
        )
        new_oh = Decimal(str(cur.fetchone()["oh_total"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        new_total = (Decimal(str(run["material_cost"])) + Decimal(str(run["packaging_cost"])) + new_oh).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        good_pkts = Decimal(str(run["good_packets"]))
        new_cpp = (new_total / good_pkts).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        cur.execute(
            """
            UPDATE production_runs
            SET overhead_cost = %s, total_cost = %s, cost_per_packet = %s
            WHERE id = %s
            """,
            (new_oh, new_total, new_cpp, int(production_run_id)),
        )

        log_audit(
            cur,
            user_id,
            username,
            "ADD_OVERHEAD",
            "PRODUCTION",
            int(production_run_id),
            f"Added {expense_type} Rs.{amt} to {run['batch_no']}; new cost/pkt Rs.{new_cpp}",
        )
        return {"overhead_cost": new_oh, "total_cost": new_total, "cost_per_packet": new_cpp}


def list_production_runs():
    return fetch_all(
        """
        SELECT pr.*, p.name AS product_name, p.sku, u.full_name AS supervisor_name
        FROM production_runs pr
        JOIN products p ON p.id = pr.product_id
        LEFT JOIN users u ON u.id = pr.supervisor_id
        ORDER BY pr.production_date DESC, pr.id DESC
        """
    )


def get_production_run_details(run_id):
    run = fetch_one(
        """
        SELECT pr.*, p.name AS product_name, p.sku, u.full_name AS supervisor_name
        FROM production_runs pr
        JOIN products p ON p.id = pr.product_id
        LEFT JOIN users u ON u.id = pr.supervisor_id
        WHERE pr.id = %s
        """,
        (int(run_id),),
    )
    if not run:
        return None
    consumptions = fetch_all(
        """
        SELECT pc.*,
               COALESCE(rm.name, pm.name) AS item_name,
               COALESCE(rm.code, pm.code) AS item_code,
               un.code AS unit_code
        FROM production_consumptions pc
        LEFT JOIN raw_materials rm ON pc.item_type = 'RAW_MATERIAL' AND rm.id = pc.item_id
        LEFT JOIN packaging_materials pm ON pc.item_type = 'PACKAGING_MATERIAL' AND pm.id = pc.item_id
        LEFT JOIN units un ON un.id = COALESCE(rm.unit_id, pm.unit_id)
        WHERE pc.production_run_id = %s
        ORDER BY pc.item_type DESC, item_name
        """,
        (int(run_id),),
    )
    overheads = fetch_all(
        "SELECT * FROM production_overheads WHERE production_run_id = %s ORDER BY id",
        (int(run_id),),
    )
    return {"run": run, "consumptions": consumptions, "overheads": overheads}
