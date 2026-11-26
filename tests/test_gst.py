"""tests/test_gst.py — Unit tests for GST calculation logic."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from decimal import Decimal
from modules.gst import compute_gst_split


def test_intra_state_cgst_sgst():
    r = compute_gst_split(7500, 5, "Tamil Nadu", "Tamil Nadu")
    assert r["supply_type"] == "INTRA_STATE"
    assert r["cgst_amount"] == Decimal("187.50")
    assert r["sgst_amount"] == Decimal("187.50")
    assert r["igst_amount"] == Decimal("0.00")
    assert r["line_total"] == Decimal("7875.00")


def test_inter_state_igst():
    r = compute_gst_split(7500, 5, "Karnataka", "Tamil Nadu")
    assert r["supply_type"] == "INTER_STATE"
    assert r["cgst_amount"] == Decimal("0.00")
    assert r["sgst_amount"] == Decimal("0.00")
    assert r["igst_amount"] == Decimal("375.00")
    assert r["line_total"] == Decimal("7875.00")


def test_zero_gst():
    r = compute_gst_split(1000, 0, "Tamil Nadu", "Tamil Nadu")
    assert r["cgst_amount"] == Decimal("0.00")
    assert r["line_total"] == Decimal("1000.00")
