import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-order-to-audit-2026")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "order_to_audit")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    FACTORY_NAME = os.getenv("FACTORY_NAME", "Sri Murugan South Indian Snacks Pvt. Ltd.")
    FACTORY_STATE = os.getenv("FACTORY_STATE", "Tamil Nadu")
    FACTORY_STATE_CODE = os.getenv("FACTORY_STATE_CODE", "33")
    FACTORY_GSTIN = os.getenv("FACTORY_GSTIN", "33AABCS1234F1Z5")
    FACTORY_ADDRESS = os.getenv(
        "FACTORY_ADDRESS",
        "No. 42, SIDCO Industrial Estate, Madurai, Tamil Nadu - 625007",
    )

    VARIANCE_TOLERANCE_PCT = Decimal(os.getenv("VARIANCE_TOLERANCE_PCT", "3.0"))
