from decimal import Decimal
from db import db_transaction, fetch_all, fetch_one


def list_boms():
    return fetch_all(
        """
        SELECT bh.*, p.name AS product_name, p.sku
        FROM bom_headers bh
        JOIN products p ON p.id = bh.product_id
        WHERE bh.is_active = TRUE
        ORDER BY p.name, bh.id DESC
        """
    )


def get_bom_with_items(bom_id):
    header = fetch_one(
        """
        SELECT bh.*, p.name AS product_name, p.sku, p.packets_per_carton, p.unit_id AS product_unit_id
        FROM bom_headers bh
        JOIN products p ON p.id = bh.product_id
        WHERE bh.id = %s
        """,
        (int(bom_id),),
    )
    if not header:
        return None
    items = fetch_all(
        """
        SELECT bi.*, u.code AS unit_code,
               COALESCE(rm.name, pm.name) AS item_name,
               COALESCE(rm.code, pm.code) AS item_code,
               COALESCE(ib.current_qty, 0) AS available_qty,
               COALESCE(ib.weighted_avg_rate, 0) AS current_rate
        FROM bom_items bi
        JOIN units u ON u.id = bi.unit_id
        LEFT JOIN raw_materials rm ON bi.item_type = 'RAW_MATERIAL' AND rm.id = bi.item_id
        LEFT JOIN packaging_materials pm ON bi.item_type = 'PACKAGING_MATERIAL' AND pm.id = bi.item_id
        LEFT JOIN inventory_balances ib ON ib.item_type = bi.item_type AND ib.item_id = bi.item_id
        WHERE bi.bom_id = %s
        ORDER BY bi.item_type DESC, item_name
        """,
        (int(bom_id),),
    )
    return {"header": header, "bom_items": items}


def create_bom(product_id, version, batch_name, expected_output_packets, items, user_id):
    with db_transaction() as cur:
        cur.execute(
            """
            INSERT INTO bom_headers (product_id, version, batch_name, expected_output_packets, is_active, created_by)
            VALUES (%s, %s, %s, %s, TRUE, %s)
            RETURNING id
            """,
            (int(product_id), version.strip(), batch_name.strip(), Decimal(str(expected_output_packets)), user_id),
        )
        bom_id = cur.fetchone()["id"]
        for it in items:
            cur.execute(
                """
                INSERT INTO bom_items (bom_id, item_type, item_id, standard_qty, unit_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (bom_id, it["item_type"], int(it["item_id"]), Decimal(str(it["standard_qty"])), int(it["unit_id"])),
            )
        return bom_id
