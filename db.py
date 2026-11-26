from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_connection(dbname=None):
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=dbname or Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        sslmode="require",
        cursor_factory=RealDictCursor,
    )


@contextmanager
def db_transaction():
    """Yield a cursor inside an atomic PostgreSQL transaction."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def fetch_all(query, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def fetch_one(query, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone()
    finally:
        conn.close()


def execute_query(query, params=None, returning=False):
    with db_transaction() as cur:
        cur.execute(query, params or ())
        if returning:
            return cur.fetchone()
        return cur.rowcount
