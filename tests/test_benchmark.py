"""
tests/test_benchmark.py
Integration tests verifying the benchmark workflow results.
Run: python -m pytest tests/test_benchmark.py -v
"""
import os, sys
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import fetch_one
from modules.inventory import get_item_balance


def resolve(table, col, val):
    row = fetch_one(f"SELECT id FROM {table} WHERE {col} = %s", (val,))
    assert row, f"Not found: {table}.{col}={val!r}"
    return row["id"]

def qty(item_type, code_col, code):
    tbl = {"RAW_MATERIAL":"raw_materials","PACKAGING_MATERIAL":"packaging_materials","FINISHED_GOOD":"products"}[item_type]
    item_id = resolve(tbl, code_col, code)
    bal = get_item_balance(item_type, item_id)
    return Decimal(str(bal["current_qty"])) if bal else Decimal("0")


@pytest.mark.order(1)
def test_flour_stock():
    assert qty("RAW_MATERIAL", "code", "RM-FLOUR") == Decimal("120"), "Flour should be 120 kg"

@pytest.mark.order(2)
def test_oil_stock():
    assert qty("RAW_MATERIAL", "code", "RM-OIL") == Decimal("19.5"), "Oil should be 19.5 L"

@pytest.mark.order(3)
def test_spice_stock():
    assert qty("RAW_MATERIAL", "code", "RM-SPICE") == Decimal("3.8"), "Spice mix should be 3.8 kg"

@pytest.mark.order(4)
def test_pouches_stock():
    assert qty("PACKAGING_MATERIAL", "code", "PM-POUCH") == Decimal("306"), "Pouches should be 306"

@pytest.mark.order(5)
def test_cartons_stock():
    assert qty("PACKAGING_MATERIAL", "code", "PM-CARTON") == Decimal("21"), "Cartons should be 21"

@pytest.mark.order(6)
def test_finished_goods_stock():
    assert qty("FINISHED_GOOD", "sku", "MUR-200") == Decimal("88"), "Finished goods should be 88 pkts after dispatch"

@pytest.mark.order(7)
def test_invoice_amounts():
    inv = fetch_one(
        "SELECT * FROM invoices WHERE order_id = (SELECT id FROM sales_orders WHERE order_no LIKE 'SO-00001')"
    )
    if not inv:
        inv = fetch_one("SELECT * FROM invoices WHERE taxable_amount = 7500 LIMIT 1")
    assert inv, "Invoice not found"
    assert Decimal(str(inv["taxable_amount"])) == Decimal("7500.00")
    assert Decimal(str(inv["cgst_amount"])) == Decimal("187.50")
    assert Decimal(str(inv["sgst_amount"])) == Decimal("187.50")
    assert Decimal(str(inv["total_amount"])) == Decimal("7875.00")
    assert Decimal(str(inv["outstanding_amount"])) == Decimal("3875.00")

@pytest.mark.order(8)
def test_production_costing():
    run = fetch_one("SELECT total_cost, cost_per_packet FROM production_runs ORDER BY id LIMIT 1")
    assert run, "Production run not found"
    assert Decimal(str(run["total_cost"])) == Decimal("5855.00")
    cpp = Decimal(str(run["cost_per_packet"])).quantize(Decimal("0.01"))
    assert cpp == Decimal("31.14"), f"Cost per packet should be 31.14, got {cpp}"

@pytest.mark.order(9)
def test_yield_variance():
    run = fetch_one("SELECT yield_variance_pct, yield_abnormal FROM production_runs ORDER BY id LIMIT 1")
    assert run, "Production run not found"
    assert Decimal(str(run["yield_variance_pct"])) == Decimal("-6.00")
    assert run["yield_abnormal"] is True

@pytest.mark.order(10)
def test_karnataka_order_shortage():
    order = fetch_one(
        "SELECT has_stock_shortage, shortage_note FROM sales_orders WHERE salesman_id = (SELECT id FROM users WHERE username='salesman_b') ORDER BY id LIMIT 1"
    )
    assert order, "Distributor B order not found"
    assert order["has_stock_shortage"] is True
    assert "32" in str(order["shortage_note"]) or "shortage" in str(order["shortage_note"]).lower()
