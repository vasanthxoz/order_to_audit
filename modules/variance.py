from decimal import Decimal, ROUND_HALF_UP
from config import Config
from modules.masters import get_setting


def get_tolerance_pct():
    val = get_setting("variance_tolerance_pct", str(Config.VARIANCE_TOLERANCE_PCT))
    return Decimal(str(val))


def calculate_variance(planned, actual, tolerance_pct=None):
    """
    Variance (%) = ((Actual - Planned) / Planned) * 100
    Returns (variance_pct, is_abnormal).
    """
    planned_d = Decimal(str(planned))
    actual_d = Decimal(str(actual))
    if planned_d == 0:
        return Decimal("0.00"), False
    tol = Decimal(str(tolerance_pct)) if tolerance_pct is not None else get_tolerance_pct()
    var_pct = (((actual_d - planned_d) / planned_d) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    is_abnormal = abs(var_pct) > tol
    return var_pct, is_abnormal
