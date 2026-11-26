from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from config import Config


def generate_invoice_pdf(invoice, items, customer):
    """Generate a GST Tax Invoice PDF using ReportLab and return bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"<b>{Config.FACTORY_NAME}</b>", styles["Title"]))
    elements.append(Paragraph(
        f"{Config.FACTORY_ADDRESS}<br/>GSTIN: <b>{Config.FACTORY_GSTIN}</b> | State: {Config.FACTORY_STATE} ({Config.FACTORY_STATE_CODE})",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("<b>TAX INVOICE</b>", styles["Heading2"]))

    meta_data = [
        ["Invoice No:", invoice["invoice_no"], "Invoice Date:", str(invoice["invoice_date"])],
        ["Financial Year:", invoice["financial_year"], "Status:", invoice["status"]],
        ["Customer:", customer["name"], "Place of Supply:", invoice["place_of_supply"]],
        ["Customer GSTIN:", customer.get("gstin") or "Unregistered", "Supply Type:", invoice["supply_type"].replace("_", " ")],
    ]
    meta_table = Table(meta_data, colWidths=[32 * mm, 58 * mm, 35 * mm, 55 * mm])
    meta_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 6 * mm))

    table_data = [["#", "Product", "HSN", "Qty", "Rate", "Taxable", "CGST", "SGST", "IGST", "Total"]]
    for idx, it in enumerate(items, start=1):
        table_data.append([
            str(idx),
            it["product_name"],
            it["hsn_code"],
            f"{it['qty_packets']}",
            f"{it['unit_price']:.2f}",
            f"{it['taxable_amount']:.2f}",
            f"{it['cgst_amount']:.2f}",
            f"{it['sgst_amount']:.2f}",
            f"{it['igst_amount']:.2f}",
            f"{it['line_total']:.2f}",
        ])

    table_data.append([
        "", "TOTAL", "", "", "",
        f"{invoice['taxable_amount']:.2f}",
        f"{invoice['cgst_amount']:.2f}",
        f"{invoice['sgst_amount']:.2f}",
        f"{invoice['igst_amount']:.2f}",
        f"{invoice['total_amount']:.2f}",
    ])

    item_table = Table(table_data, colWidths=[8 * mm, 42 * mm, 18 * mm, 14 * mm, 16 * mm, 18 * mm, 16 * mm, 16 * mm, 16 * mm, 18 * mm])
    item_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph(
        f"Paid: Rs. {invoice['paid_amount']:.2f} | Outstanding Balance: <b>Rs. {invoice['outstanding_amount']:.2f}</b>",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph("This is a computer-generated GST Tax Invoice.", styles["Italic"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_report_pdf(title, headers, rows, subtitle=""):
    """Generate a tabular report PDF using ReportLab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{Config.FACTORY_NAME}</b>", styles["Heading3"]), Paragraph(f"<b>{title}</b>", styles["Heading2"])]
    if subtitle:
        elements.append(Paragraph(subtitle, styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))

    data = [headers] + [[str(cell if cell is not None else "") for cell in row] for row in rows]
    col_count = max(len(headers), 1)
    avail_width = 190 * mm
    col_widths = [avail_width / col_count] * col_count

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(tbl)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
