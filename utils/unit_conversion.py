from decimal import Decimal, ROUND_HALF_UP


UNIT_FACTORS_TO_BASE = {
    "kg": ("g", Decimal("1000")),
    "g": ("g", Decimal("1")),
    "L": ("ml", Decimal("1000")),
    "ml": ("ml", Decimal("1")),
    "pcs": ("pcs", Decimal("1")),
    "pkt": ("pkt", Decimal("1")),
    "ctn": ("pkt", Decimal("20")),
}


def convert_quantity(qty, from_unit, to_unit, packets_per_carton=20):
    """Convert quantity between compatible units (kg/g, L/ml, pkt/ctn, pcs)."""
    q = Decimal(str(qty))
    if from_unit == to_unit:
        return q

    factors = dict(UNIT_FACTORS_TO_BASE)
    factors["ctn"] = ("pkt", Decimal(str(packets_per_carton)))

    if from_unit not in factors or to_unit not in factors:
        raise ValueError(f"Unsupported unit conversion: {from_unit} -> {to_unit}")

    from_base, from_factor = factors[from_unit]
    to_base, to_factor = factors[to_unit]
    if from_base != to_base:
        raise ValueError(f"Incompatible units: {from_unit} and {to_unit}")

    return (q * from_factor / to_factor).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
