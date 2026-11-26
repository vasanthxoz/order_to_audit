"""
seed_database.py
Populates master data, creates demo users, sets opening stock for the benchmark.
Run after setup_database.py: python scripts/seed_database.py
"""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from config import Config

SEED_SQL = os.path.join(os.path.dirname(__file__), "..", "database", "seed.sql")


def get_conn():
    return psycopg2.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        cursor_factory=RealDictCursor
    )


def run_seed_sql(conn):
    with open(SEED_SQL, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("[seed] Master data SQL applied.")


def create_users(conn):
    users = [
        ("admin",       "Admin User",         "admin@factory.com",      "9999100001", "admin",        "admin123"),
        ("salesman_a",  "Salesman A",          "salesmana@factory.com",  "9999100002", "salesman",     "sales123"),
        ("salesman_b",  "Salesman B",          "salesmanb@factory.com",  "9999100003", "salesman",     "sales123"),
        ("supervisor",  "Production Supvr",   "supervisor@factory.com", "9999100004", "production_supervisor", "prod123"),
        ("auditor",     "Auditor Ravi",        "auditor@factory.com",    "9999100005", "auditor",      "audit123"),
        ("owner",       "Owner Murugan",       "owner@factory.com",      "9999100006", "owner",        "owner123"),
    ]
    with conn:
        with conn.cursor() as cur:
            for username, full_name, email, phone, role_name, password in users:
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    print(f"  [seed] User '{username}' already exists, skipping.")
                    continue
                cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
                role = cur.fetchone()
                if not role:
                    print(f"  [seed] Role '{role_name}' not found, skipping user '{username}'.")
                    continue
                cur.execute(
                    """
                    INSERT INTO users (username, full_name, email, phone, password_hash, role_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (username, full_name, email, phone, generate_password_hash(password), role["id"])
                )
                print(f"  [seed] Created user: {username} / {password}  ({role_name})")


def set_opening_stock(conn):
    """
    Set opening stock per benchmark spec:
      Flour 100 kg @ ₹42/kg, Oil 30 L @ ₹140/L, Spice mix 5 kg @ ₹200/kg
      Pouches 500 pcs @ ₹2.50, Cartons 30 pcs @ ₹15
      Finished: Murukku 200g — 50 pkts @ ₹0 (opening)
    """
    openings = [
        ("RAW_MATERIAL",      "RM-FLOUR",   Decimal("100.000"), Decimal("42.0000")),
        ("RAW_MATERIAL",      "RM-OIL",     Decimal("30.000"),  Decimal("140.0000")),
        ("RAW_MATERIAL",      "RM-SPICE",   Decimal("5.000"),   Decimal("200.0000")),
        ("PACKAGING_MATERIAL","PM-POUCH",   Decimal("500.000"), Decimal("2.5000")),
        ("PACKAGING_MATERIAL","PM-CARTON",  Decimal("30.000"),  Decimal("15.0000")),
        ("FINISHED_GOOD",     "MUR-200",    Decimal("50.000"),  Decimal("0.0000")),
    ]

    with conn:
        with conn.cursor() as cur:
            for item_type, code, qty, rate in openings:
                # Resolve item_id
                if item_type == "RAW_MATERIAL":
                    cur.execute("SELECT id, unit_id FROM raw_materials WHERE code = %s", (code,))
                elif item_type == "PACKAGING_MATERIAL":
                    cur.execute("SELECT id, unit_id FROM packaging_materials WHERE code = %s", (code,))
                else:
                    cur.execute("SELECT id, unit_id FROM products WHERE sku = %s", (code,))
                row = cur.fetchone()
                if not row:
                    print(f"  [seed] WARNING: {item_type} '{code}' not found, skipping opening stock.")
                    continue

                item_id = row["id"]
                unit_id = row["unit_id"]

                # Check if opening stock already set
                cur.execute(
                    "SELECT id, current_qty FROM inventory_balances WHERE item_type = %s AND item_id = %s",
                    (item_type, item_id)
                )
                bal = cur.fetchone()
                if bal and Decimal(str(bal["current_qty"])) > 0:
                    print(f"  [seed] Opening stock for {code} already set ({bal['current_qty']}), skipping.")
                    continue

                # Upsert inventory_balances
                if bal:
                    cur.execute(
                        """
                        UPDATE inventory_balances
                        SET opening_qty = %s, current_qty = %s, weighted_avg_rate = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (qty, qty, rate, bal["id"])
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO inventory_balances (item_type, item_id, unit_id, opening_qty, current_qty, weighted_avg_rate)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (item_type, item_id, unit_id, qty, qty, rate)
                    )

                # Append stock_ledger OPENING entry
                cur.execute(
                    """
                    INSERT INTO stock_ledger (
                        item_type, item_id, movement_type, qty_in, qty_out,
                        unit_rate, total_value, balance_qty,
                        source_doc_type, source_doc_no, remarks
                    )
                    VALUES (%s, %s, 'OPENING', %s, 0, %s, %s, %s, 'OPENING', 'OPENING', %s)
                    """,
                    (
                        item_type, item_id,
                        qty, rate, qty * rate, qty,
                        f"Opening stock for {code}"
                    )
                )
                print(f"  [seed] Opening stock set: {code} = {qty} @ ₹{rate}")


def create_bom(conn):
    """Create the benchmark BOM for Murukku 200g — 1 batch = 200 packets."""
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM products WHERE sku='MUR-200'")
            prod = cur.fetchone()
            if not prod:
                print("  [seed] Product MUR-200 not found, skipping BOM.")
                return
            cur.execute("SELECT COUNT(*) AS cnt FROM bom_headers WHERE product_id=%s", (prod["id"],))
            if cur.fetchone()["cnt"] > 0:
                print("  [seed] BOM for MUR-200 already exists, skipping.")
                return

            # Get user for created_by
            cur.execute("SELECT id FROM users WHERE username='admin'")
            admin = cur.fetchone()
            admin_id = admin["id"] if admin else None

            # Insert BOM header
            cur.execute(
                """
                INSERT INTO bom_headers (product_id, version, batch_name, expected_output_packets, is_active, created_by)
                VALUES (%s, 'v1.0', 'Murukku 200g Standard Batch', 200, TRUE, %s)
                RETURNING id
                """,
                (prod["id"], admin_id)
            )
            bom_id = cur.fetchone()["id"]

            # Resolve unit IDs
            def uid(code):
                cur.execute("SELECT id FROM units WHERE code=%s", (code,))
                r = cur.fetchone()
                return r["id"] if r else None

            kg_id  = uid("kg")
            L_id   = uid("L")
            pcs_id = uid("pcs")

            # Raw materials
            cur.execute("SELECT id FROM raw_materials WHERE code='RM-FLOUR'")
            flour = cur.fetchone()
            cur.execute("SELECT id FROM raw_materials WHERE code='RM-OIL'")
            oil = cur.fetchone()
            cur.execute("SELECT id FROM raw_materials WHERE code='RM-SPICE'")
            spice = cur.fetchone()

            # Packaging materials
            cur.execute("SELECT id FROM packaging_materials WHERE code='PM-POUCH'")
            pouch = cur.fetchone()
            cur.execute("SELECT id FROM packaging_materials WHERE code='PM-CARTON'")
            carton = cur.fetchone()

            bom_items = [
                ("RAW_MATERIAL",      flour["id"],  Decimal("40.000"),  kg_id),
                ("RAW_MATERIAL",      oil["id"],    Decimal("10.000"),  L_id),
                ("RAW_MATERIAL",      spice["id"],  Decimal("1.200"),   kg_id),
                ("PACKAGING_MATERIAL",pouch["id"],  Decimal("200.000"), pcs_id),
                ("PACKAGING_MATERIAL",carton["id"], Decimal("10.000"),  pcs_id),
            ]
            for item_type, item_id, std_qty, unit_id in bom_items:
                cur.execute(
                    """
                    INSERT INTO bom_items (bom_id, item_type, item_id, standard_qty, unit_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (bom_id, item_type, item_id, std_qty, unit_id)
                )
            print(f"  [seed] BOM created for MUR-200 (bom_id={bom_id}): 5 line items, expected 200 packets.")


def main():
    conn = get_conn()
    try:
        run_seed_sql(conn)
        create_users(conn)
        set_opening_stock(conn)
        create_bom(conn)
        print("\n[seed] ✅ Seed complete! Login credentials:")
        print("  admin / admin123       (Admin)")
        print("  salesman_a / sales123  (Salesman A)")
        print("  salesman_b / sales123  (Salesman B)")
        print("  supervisor / prod123   (Production Supervisor)")
        print("  auditor / audit123     (Auditor)")
        print("  owner / owner123       (Owner)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
