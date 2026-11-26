"""tests/test_production.py — Unit tests for variance calculation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from decimal import Decimal
from modules.variance import calculate_variance


def test_yield_variance_negative():
    var, abnormal = calculate_variance(200, 188, tolerance_pct=Decimal("3"))
    assert var == Decimal("-6.00")
    assert abnormal is True


def test_oil_variance_positive():
    var, abnormal = calculate_variance(10, 10.5, tolerance_pct=Decimal("3"))
    assert var == Decimal("5.00")
    assert abnormal is True


def test_within_tolerance():
    var, abnormal = calculate_variance(100, 102, tolerance_pct=Decimal("3"))
    assert var == Decimal("2.00")
    assert abnormal is False


def test_zero_planned_no_crash():
    var, abnormal = calculate_variance(0, 10, tolerance_pct=Decimal("3"))
    assert var == Decimal("0.00")
    assert abnormal is False
