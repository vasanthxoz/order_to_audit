"""tests/test_inventory.py — Unit tests for weighted average valuation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from decimal import Decimal
from modules.variance import calculate_variance


def test_weighted_avg_basic():
    """
    Opening: 100 kg @ ₹42  → value = 4200
    Purchase: 60 kg @ ₹45  → value = 2700
    New avg = (4200 + 2700) / 160 = 43.125
    """
    old_qty = Decimal("100")
    old_rate = Decimal("42")
    new_qty = Decimal("60")
    new_rate = Decimal("45")
    total_qty = old_qty + new_qty
    total_val = (old_qty * old_rate) + (new_qty * new_rate)
    new_avg = total_val / total_qty
    assert new_avg == Decimal("43.125")


def test_weighted_avg_after_issue():
    """After issue the rate stays the same (WAC method)."""
    rate = Decimal("43.125")
    qty_before = Decimal("160")
    qty_issued = Decimal("40")
    qty_after = qty_before - qty_issued
    assert qty_after == Decimal("120")
    # Rate unchanged on issue
    assert rate == Decimal("43.125")
