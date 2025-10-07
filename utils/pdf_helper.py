# utils/pdf_helper.py
import os
import sqlite3
import subprocess
import platform
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from models import delivery_model

EXPORT_DIR = "data/exports"
DEFAULT_LOGO = "data/logos/c_logo.png"
DEFAULT_SIGN = "data/logos/sign.png"


class HRLine(Flowable):
    """Simple horizontal line flowable"""

    def __init__(self, width=None, thickness=1, color=colors.black):
        Flowable.__init__(self)
        self.width = width
        self.thickness = thickness
        self.color = color

    def draw(self):
        w = self.width or self._available_width
        self.canv.setLineWidth(self.thickness)
        self.canv.setStrokeColor(self.color)
        self.canv.line(0, 0, w, 0)


def _safe_image(path, max_width_mm=None, max_height_mm=None):
    """
    Return a ReportLab Image or None if not found.
    Optionally scale to fit mm sizes.
    """
    if not path:
        return None
    if not os.path.exists(path):
        return None
    try:
        img = Image(path)
        if max_width_mm or max_height_mm:
            max_w = (max_width_mm * mm) if max_width_mm else None
            max_h = (max_height_mm * mm) if max_height_mm else None
            iw, ih = img.wrap(0, 0)
            scale = 1.0
            if max_w and iw > max_w:
                scale = min(scale, max_w / iw)
            if max_h and ih > max_h:
                scale = min(scale, max_h / ih)
            if scale != 1.0:
                img.drawWidth = iw * scale
                img.drawHeight = ih * scale
        return img
    except Exception:
        return None


def _open_file_with_default_app(path):
    """
    Cross-platform open with default PDF viewer.
    """
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore
        elif platform.system() == "Darwin":
            subprocess.call(["open", path])
        else:
            # assume linux/unix
            subprocess.call(["xdg-open", path])
    except Exception:
        # best-effort; do not fail
        pass


def generate_challan_pdf(challan_id, open_pdf=True):
    """
    Generate a Delivery Challan PDF for challan_id.
    Returns the file path or raises RuntimeError on failure.
    """
    data = delivery_model.get_challan(challan_id)
    if not data:
        raise RuntimeError(f"Challan id {challan_id} not found.")

    hdr = data["header"]
    items = data["items"]

    # Ensure export dir
    os.makedirs(EXPORT_DIR, exist_ok=True)

    challan_no = hdr.get(
        "challan_no") or f"DC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    filename = f"{challan_no}.pdf"
    out_path = os.path.join(EXPORT_DIR, filename)

    # Company profile (try to load from DB)
    company = None
    try:
        conn = sqlite3.connect(delivery_model.DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM company_profile LIMIT 1")
        row = c.fetchone()
        if row:
            cols = [d[0] for d in c.description]
            company = dict(zip(cols, row))
        conn.close()
    except Exception:
        company = None

    # Document setup
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=18*mm,
        bottomMargin=18*mm
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    bold = ParagraphStyle(
        "bold", parent=styles["Normal"], fontSize=10, leading=12)
    heading_style = ParagraphStyle(
        "heading", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=16, leading=20)
    small = ParagraphStyle(
        "small", parent=styles["Normal"], fontSize=9, leading=11)

    elements = []

    # Title
    elements.append(Paragraph("<b>DELIVERY CHALLAN</b>", heading_style))
    elements.append(Spacer(1, 6))

    # Top row: logo left, company address center/right
    logo_img = None
    if company and company.get("logo_path"):
        logo_img = _safe_image(company.get("logo_path"),
                               max_width_mm=40, max_height_mm=25)
    if not logo_img:
        logo_img = _safe_image(DEFAULT_LOGO, max_width_mm=40, max_height_mm=25)

    # Build company block text
    comp_lines = []
    if company:
        if company.get("name"):
            comp_lines.append(f"<b>{company.get('name')}</b>")
        if company.get("address"):
            comp_lines.append(company.get("address").replace("\n", "<br/>"))
        # GST column: prefer gst_no, then gstin
        gst = company.get("gst_no") or company.get("gstin") or ""
        if gst:
            comp_lines.append(f"GST: {gst}")
        if company.get("phone1"):
            comp_lines.append(f"Phone: {company.get('phone1')}")
        if company.get("email"):
            comp_lines.append(f"Email: {company.get('email')}")
    else:
        comp_lines = ["<b>Company</b>", "Address not set"]

    comp_paragraph = Paragraph("<br/>".join(comp_lines), small)

    # Layout: table with 2 columns: logo | company details + challan meta on right
    top_table_data = []
    left_col = logo_img or ""
    right_col = comp_paragraph
    # We'll compose a nested table to show comp + challan meta side by side
    meta_lines = [
        f"<b>Challan No:</b> {hdr.get('challan_no') or ''}",
        f"<b>Date/Time:</b> {hdr.get('created_at') or ''}"
    ]
    meta_par = Paragraph("<br/>".join(meta_lines), small)
    top_table_data = [[left_col, right_col, meta_par]]
    top_tbl = Table(top_table_data, colWidths=[50*mm, 90*mm, 50*mm])
    top_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(top_tbl)
    elements.append(Spacer(1, 6))
    elements.append(HRLine(width=doc.width, thickness=1))
    elements.append(Spacer(1, 6))

    # Delivery to / transport block
    to_lines = []
    to_addr = hdr.get("to_address") or ""
    to_gst = hdr.get("to_gst_no") or ""
    transporter = hdr.get("transporter_name") or ""
    vehicle = hdr.get("vehicle_no") or ""
    delivery_loc = hdr.get("delivery_location") or ""

    to_lines.append(f"<b>Delivery To:</b>")
    to_lines.append(to_addr.replace("\n", "<br/>"))
    if to_gst:
        to_lines.append(f"GST: {to_gst}")
    if transporter or vehicle or delivery_loc:
        trans_parts = []
        if transporter:
            trans_parts.append(f"Transporter: {transporter}")
        if vehicle:
            trans_parts.append(f"Vehicle No: {vehicle}")
        if delivery_loc:
            trans_parts.append(f"Delivery Location: {delivery_loc}")
        to_lines.append("<br/>".join(trans_parts))

    elements.append(Paragraph("<br/>".join(to_lines), small))
    elements.append(Spacer(1, 8))

    # Items table header and rows
    table_data = []
    header_row = ["Item Code", "Item Name", "HSN", "Qty", "Unit"]
    table_data.append([Paragraph(f"<b>{c}</b>", small) for c in header_row])

    # Rows
    total_qty = 0.0
    for it in items:
        code = it.get("item_code") or ""
        name = it.get("item_name") or ""
        hsn = it.get("hsn_code") or ""
        qty = it.get("qty") or 0
        unit = it.get("unit") or ""
        total_qty += float(qty or 0)
        table_data.append([str(code), str(name), str(
            hsn), f"{float(qty or 0):.3f}", str(unit or "")])

    # Table style: alternate background
    col_widths = [30*mm, 80*mm, 25*mm, 25*mm, 20*mm]
    items_table = Table(table_data, colWidths=col_widths, hAlign="LEFT")
    items_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-3, 1), (-2, -1), "RIGHT"),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 6))

    # Total qty row (right-aligned)
    total_par = Paragraph(f"<b>Total Qty: {total_qty:.3f}</b>",
                          ParagraphStyle("right", parent=small, alignment=TA_RIGHT))
    elements.append(total_par)
    elements.append(Spacer(1, 8))

    # Description / reason
    desc = hdr.get("description") or ""
    elements.append(Paragraph("<b>Description / Reason:</b>", small))
    elements.append(Paragraph(desc.replace("\n", "<br/>"), small))
    elements.append(Spacer(1, 18))

   # Signature + company name footer
    # Layout: left empty, right signature block with "For <Company>" and signature image below it
    sign_img = _safe_image(DEFAULT_SIGN, max_width_mm=50, max_height_mm=30)

    comp_name = (company.get("name") if company else "") or ""
    sign_text = f"For <b>{comp_name}</b>" if comp_name else "For Company"
    sign_par = Paragraph(sign_text, small)

    # Stack: company name, then signature image (if any)
    nested = []
    nested.append([sign_par])
    if sign_img:
        nested.append([sign_img])

    nested_tbl = Table(nested, colWidths=[60*mm])
    nested_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    final_footer = Table(
        [[Paragraph("", small), nested_tbl]],
        colWidths=[110*mm, 70*mm]
    )
    final_footer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(final_footer)

    # Build PDF
    doc.build(elements)

    # Optionally open using default viewer
    if open_pdf:
        _open_file_with_default_app(out_path)

    return out_path
