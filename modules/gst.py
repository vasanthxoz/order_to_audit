from decimal import Decimal, ROUND_HALF_UP
from config import Config


def get_financial_year(dt):
    """Return Indian FY string e.g. '2026-27' for a given date."""
    year = dt.year
    if dt.month >= 4:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


def compute_gst_split(taxable_amount, gst_rate, customer_state, factory_state=None):
    """
    Apply CGST/SGST for intra-state sales (Tamil Nadu -> Tamil Nadu)
    and IGST for inter-state sales (Tamil Nadu -> Karnataka, etc.).
    """
    taxable = Decimal(str(taxable_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rate = Decimal(str(gst_rate))
    f_state = (factory_state or Config.FACTORY_STATE).strip().lower()
    c_state = (customer_state or "").strip().lower()

    if c_state == f_state:
        half_rate = (rate / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst = (taxable * half_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = (taxable * half_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {
            "supply_type": "INTRA_STATE",
            "cgst_rate": half_rate,
            "cgst_amount": cgst,
            "sgst_rate": half_rate,
            "sgst_amount": sgst,
            "igst_rate": Decimal("0.00"),
            "igst_amount": Decimal("0.00"),
            "total_gst": cgst + sgst,
            "line_total": taxable + cgst + sgst,
        }

    igst = (taxable * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "supply_type": "INTER_STATE",
        "cgst_rate": Decimal("0.00"),
        "cgst_amount": Decimal("0.00"),
        "sgst_rate": Decimal("0.00"),
        "sgst_amount": Decimal("0.00"),
        "igst_rate": rate,
        "igst_amount": igst,
        "total_gst": igst,
        "line_total": taxable + igst,
    }
