from decimal import Decimal
from db import fetch_all, fetch_one, execute_query, db_transaction


def list_units():
    return fetch_all("SELECT * FROM units ORDER BY id")


def list_customers():
    return fetch_all("SELECT * FROM customers WHERE is_active = TRUE ORDER BY name")


def get_customer(customer_id):
    return fetch_one("SELECT * FROM customers WHERE id = %s", (int(customer_id),))


def create_customer(name, customer_type, gstin, state, state_code, phone, email, address, credit_limit=0):
    return execute_query(
        """
        INSERT INTO customers (name, customer_type, gstin, state, state_code, phone, email, address, credit_limit)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            name.strip(),
            customer_type.strip(),
            (gstin or "").strip().upper(),
            state.strip(),
            state_code.strip(),
            (phone or "").strip(),
            (email or "").strip(),
            (address or "").strip(),
            Decimal(str(credit_limit or 0)),
        ),
        returning=True,
    )


def list_suppliers():
    return fetch_all("SELECT * FROM suppliers WHERE is_active = TRUE ORDER BY name")


def create_supplier(name, gstin, state, state_code, phone, email, address):
    return execute_query(
        """
        INSERT INTO suppliers (name, gstin, state, state_code, phone, email, address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            name.strip(),
            (gstin or "").strip().upper(),
            state.strip(),
            state_code.strip(),
            (phone or "").strip(),
            (email or "").strip(),
            (address or "").strip(),
        ),
        returning=True,
    )


def list_products():
    return fetch_all(
        """
        SELECT p.*, u.code AS unit_code,
               COALESCE(pli.selling_price, 0) AS default_price,
               COALESCE(ib.current_qty, 0) AS current_stock
        FROM products p
        JOIN units u ON u.id = p.unit_id
        LEFT JOIN price_lists pl ON pl.is_default = TRUE AND pl.is_active = TRUE
        LEFT JOIN price_list_items pli ON pli.price_list_id = pl.id AND pli.product_id = p.id
        LEFT JOIN inventory_balances ib ON ib.item_type = 'FINISHED_GOOD' AND ib.item_id = p.id
        WHERE p.is_active = TRUE
        ORDER BY p.name
        """
    )


def get_product_selling_price(product_id):
    row = fetch_one(
        """
        SELECT pli.selling_price, p.gst_rate, p.hsn_code, p.name, p.packets_per_carton
        FROM products p
        LEFT JOIN price_lists pl ON pl.is_default = TRUE AND pl.is_active = TRUE
        LEFT JOIN price_list_items pli ON pli.price_list_id = pl.id AND pli.product_id = p.id
        WHERE p.id = %s
        """,
        (int(product_id),),
    )
    return row


def create_product(sku, name, category, pack_size_grams, pack_label, packets_per_carton, hsn_code, gst_rate, unit_id, selling_price, reorder_level=20):
    with db_transaction() as cur:
        cur.execute(
            """
            INSERT INTO products (sku, name, category, pack_size_grams, pack_label, packets_per_carton, hsn_code, gst_rate, unit_id, reorder_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                sku.strip().upper(),
                name.strip(),
                category.strip(),
                Decimal(str(pack_size_grams)),
                pack_label.strip(),
                int(packets_per_carton),
                hsn_code.strip(),
                Decimal(str(gst_rate)),
                int(unit_id),
                Decimal(str(reorder_level)),
            ),
        )
        prod_id = cur.fetchone()["id"]
        cur.execute("SELECT id FROM price_lists WHERE is_default = TRUE LIMIT 1")
        pl = cur.fetchone()
        if pl:
            cur.execute(
                """
                INSERT INTO price_list_items (price_list_id, product_id, selling_price)
                VALUES (%s, %s, %s)
                ON CONFLICT (price_list_id, product_id) DO UPDATE SET selling_price = EXCLUDED.selling_price
                """,
                (pl["id"], prod_id, Decimal(str(selling_price))),
            )
        cur.execute(
            """
            INSERT INTO inventory_balances (item_type, item_id, unit_id, opening_qty, current_qty, weighted_avg_rate)
            VALUES ('FINISHED_GOOD', %s, %s, 0, 0, 0)
            ON CONFLICT (item_type, item_id) DO NOTHING
            """,
            (prod_id, int(unit_id)),
        )
        return prod_id


def list_raw_materials():
    return fetch_all(
        """
        SELECT rm.*, u.code AS unit_code,
               COALESCE(ib.current_qty, 0) AS current_stock,
               COALESCE(ib.weighted_avg_rate, 0) AS weighted_avg_rate
        FROM raw_materials rm
        JOIN units u ON u.id = rm.unit_id
        LEFT JOIN inventory_balances ib ON ib.item_type = 'RAW_MATERIAL' AND ib.item_id = rm.id
        WHERE rm.is_active = TRUE
        ORDER BY rm.name
        """
    )


def create_raw_material(code, name, unit_id, hsn_code, gst_rate, reorder_level=10):
    with db_transaction() as cur:
        cur.execute(
            """
            INSERT INTO raw_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (code.strip().upper(), name.strip(), int(unit_id), (hsn_code or "").strip(), Decimal(str(gst_rate)), Decimal(str(reorder_level))),
        )
        rm_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO inventory_balances (item_type, item_id, unit_id, opening_qty, current_qty, weighted_avg_rate)
            VALUES ('RAW_MATERIAL', %s, %s, 0, 0, 0)
            ON CONFLICT (item_type, item_id) DO NOTHING
            """,
            (rm_id, int(unit_id)),
        )
        return rm_id


def list_packaging_materials():
    return fetch_all(
        """
        SELECT pm.*, u.code AS unit_code,
               COALESCE(ib.current_qty, 0) AS current_stock,
               COALESCE(ib.weighted_avg_rate, 0) AS weighted_avg_rate
        FROM packaging_materials pm
        JOIN units u ON u.id = pm.unit_id
        LEFT JOIN inventory_balances ib ON ib.item_type = 'PACKAGING_MATERIAL' AND ib.item_id = pm.id
        WHERE pm.is_active = TRUE
        ORDER BY pm.name
        """
    )


def create_packaging_material(code, name, unit_id, hsn_code, gst_rate, reorder_level=50):
    with db_transaction() as cur:
        cur.execute(
            """
            INSERT INTO packaging_materials (code, name, unit_id, hsn_code, gst_rate, reorder_level)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (code.strip().upper(), name.strip(), int(unit_id), (hsn_code or "").strip(), Decimal(str(gst_rate)), Decimal(str(reorder_level))),
        )
        pm_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO inventory_balances (item_type, item_id, unit_id, opening_qty, current_qty, weighted_avg_rate)
            VALUES ('PACKAGING_MATERIAL', %s, %s, 0, 0, 0)
            ON CONFLICT (item_type, item_id) DO NOTHING
            """,
            (pm_id, int(unit_id)),
        )
        return pm_id


def get_setting(key, default=None):
    row = fetch_one("SELECT value FROM system_settings WHERE key = %s", (key,))
    return row["value"] if row else default


def update_setting(key, value):
    execute_query(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        (key, str(value)),
    )
