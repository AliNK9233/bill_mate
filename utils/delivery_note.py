# utils/delivery_note.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from models.invoice_model import fetch_invoice
import os
import tempfile
import webbrowser
from datetime import datetime


def generate_delivery_note_pdf(invoice_no: str, output_path: str = None, open_after: bool = False) -> str:
    """
    Generate a delivery note PDF for invoice_no.
    Returns the file path. If open_after True, tries to open the PDF.
    """
    header, items = fetch_invoice(invoice_no)
    if not header:
        raise ValueError("Invoice not found")

    # choose output filename
    if not output_path:
        tempdir = tempfile.gettempdir()
        output_path = os.path.join(tempdir, f"delivery_note_{invoice_no}.pdf")

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    margin = 18 * mm
    x = margin
    y = height - margin

    # Header area: company details (customize)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, "Your Company Name")
    c.setFont("Helvetica", 9)
    c.drawString(x, y - 14, "Address line 1, Address line 2")
    c.drawString(x, y - 26, "Phone: +971-xxx-xxx  Email: sales@example.com")

    # Delivery Note title & invoice info on right
    c.setFont("Helvetica-Bold", 18)
    c.drawString(width - margin - 160, y, "DELIVERY NOTE")
    c.setFont("Helvetica", 10)

    invoice_no_txt = header.get("invoice_no") if hasattr(
        header, "get") else header[1]
    invoice_date = header.get("invoice_date") if hasattr(
        header, "get") else header[2]
    dt = invoice_date
    try:
        # format date to friendly format
        from utils.sales_report_window import parse_db_date
        dd = parse_db_date(invoice_date)
        dt = dd.strftime("%Y-%m-%d") if dd else str(invoice_date)
    except Exception:
        dt = str(invoice_date)

    c.drawString(width - margin - 160, y - 24, f"Ref: {invoice_no_txt}")
    c.drawString(width - margin - 160, y - 38, f"Date: {dt}")

    # Bill to / Ship to box
    bill_to = header.get("bill_to") if hasattr(
        header, "get") else (header[4] if len(header) > 4 else "")
    ship_to = header.get("ship_to") if hasattr(
        header, "get") else (header[5] if len(header) > 5 else "")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y - 60, "Bill To:")
    c.setFont("Helvetica", 9)
    text_obj = c.beginText(x, y - 74)
    for line in str(bill_to).splitlines():
        text_obj.textLine(line)
    c.drawText(text_obj)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 280, y - 60, "Ship To:")
    c.setFont("Helvetica", 9)
    text_obj2 = c.beginText(x + 280, y - 74)
    for line in str(ship_to).splitlines():
        text_obj2.textLine(line)
    c.drawText(text_obj2)

    # Table header
    table_y = y - 150
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(x, table_y + 4, width - margin, table_y + 4)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, table_y, "S.No")
    c.drawString(x + 30, table_y, "Code")
    c.drawString(x + 100, table_y, "Description")
    c.drawString(x + 320, table_y, "Qty")
    c.drawString(x + 360, table_y, "UOM")

    # items
    c.setFont("Helvetica", 9)
    row_h = 14
    cur_y = table_y - 12
    for idx, it in enumerate(items, start=1):
        code = it.get('item_code') if isinstance(
            it, dict) else (it[3] if len(it) > 3 else "")
        name = it.get('item_name') if isinstance(
            it, dict) else (it[4] if len(it) > 4 else "")
        qty = it.get('quantity') if isinstance(
            it, dict) else (it[7] if len(it) > 7 else 0)
        uom = it.get('uom') if isinstance(
            it, dict) else (it[5] if len(it) > 5 else "")
        c.drawString(x, cur_y, str(idx))
        c.drawString(x + 30, cur_y, str(code))
        # wrap long description roughly
        c.drawString(x + 100, cur_y, str(name)[:60])
        c.drawRightString(x + 340, cur_y, str(qty))
        c.drawString(x + 360, cur_y, str(uom))
        cur_y -= row_h
        if cur_y < margin + 60:
            c.showPage()
            cur_y = height - margin - 40

    # Footer signature lines
    foot_y = margin + 40
    c.line(x, foot_y + 20, x + 140, foot_y + 20)
    c.drawString(x, foot_y + 4, "Prepared By / Verified By")

    c.line(width - margin - 140, foot_y + 20, width - margin, foot_y + 20)
    c.drawString(width - margin - 140, foot_y + 4,
                 "Received By (Name & Signature)")

    c.save()

    if open_after:
        try:
            webbrowser.open_new(output_path)
        except Exception:
            pass
    return output_path
