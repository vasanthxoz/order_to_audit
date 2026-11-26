"""
setup_database.py
Creates the PostgreSQL database and applies schema.sql.
Run once: python scripts/setup_database.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import Config

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")


def setup():
    print(f"[setup] Connecting to PostgreSQL at {Config.DB_HOST}:{Config.DB_PORT} as {Config.DB_USER}...")

    # Create DB if not exists
    conn = psycopg2.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        dbname="postgres",
        user=Config.DB_USER, password=Config.DB_PASSWORD
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (Config.DB_NAME,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{Config.DB_NAME}"')
        print(f"[setup] Database '{Config.DB_NAME}' created.")
    else:
        print(f"[setup] Database '{Config.DB_NAME}' already exists.")
    cur.close()
    conn.close()

    # Apply schema
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn2 = psycopg2.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER, password=Config.DB_PASSWORD
    )
    with conn2:
        with conn2.cursor() as cur2:
            cur2.execute(schema_sql)
    conn2.close()
    print("[setup] Schema applied successfully.")


if __name__ == "__main__":
    setup()
