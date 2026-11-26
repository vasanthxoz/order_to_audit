from decimal import Decimal, InvalidOperation


def to_decimal(value, field_name="value", min_value=None, allow_zero=True):
    """Parse a value into Decimal with validation."""
    if value is None or str(value).strip() == "":
        raise ValueError(f"{field_name} is required.")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")

    if not allow_zero and dec == 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    if min_value is not None and dec < Decimal(str(min_value)):
        raise ValueError(f"{field_name} must be at least {min_value}.")
    return dec


def require_non_empty(value, field_name):
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required.")
    return cleaned


def validate_gstin(gstin):
    cleaned = (gstin or "").strip().upper()
    if not cleaned:
        return ""
    if len(cleaned) != 15 or not cleaned.isalnum():
        raise ValueError("GSTIN must be a 15-character alphanumeric code.")
    return cleaned
