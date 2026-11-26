import csv
from io import StringIO


def generate_csv_bytes(headers, rows):
    """Export tabular data to UTF-8 CSV bytes."""
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if v is None else str(v) for v in row])
    return buf.getvalue().encode("utf-8-sig")
