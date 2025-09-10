# utils/pdf_helper.py

import os
import webbrowser
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image
)
from models.invoice_model import fetch_invoice
from models.company_model import get_company_profile
# -------- helpers --------


def _num(v):
    try:
        return float(v or 0.0)
    except Exception:
        try:
            s = str(v).replace(",", "").strip()
            return float(s) if s else 0.0
        except Exception:
            return 0.0


def _fmt(v):
    return f"{_num(v):,.2f}"


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        return None


def _get_row_value(row, key, default=None):
    # Works with sqlite3.Row and plain dict
    if row is None:
        return default
    try:
        if isinstance(row, sqlite3.Row):
            return row[key] if key in row.keys() else default
        if hasattr(row, "__getitem__"):
            return row[key] if key in row else default
    except Exception:
        pass
    return default

# -------- main API --------


def generate_invoice_pdf(invoice_no: str, open_after: bool = False, out_dir: str = "reports") -> str:
    """
    Render an invoice PDF using the layout from ui.py, filled with DB data.
    - Header/footer with watermark (Original or Cancelled).
    - Top header row: logo | company block | invoice meta.
    - Bill To | Ship To | Remarks row.
    - Items table (8 columns) with repeat header on page breaks.
    - Totals block + Bank details + Seal.
    """
    os.makedirs(out_dir, exist_ok=True)

    header, items = fetch_invoice(invoice_no)
    if not header:
        raise ValueError(f"Invoice not found: {invoice_no}")

    # Header fields
    inv_no = _get_row_value(header, "invoice_no", invoice_no)
    inv_date_val = _get_row_value(header, "invoice_date", "")
    inv_dt = _parse_dt(inv_date_val)
    inv_date_str = inv_dt.strftime(
        "%d-%b-%Y") if inv_dt else str(inv_date_val or "")
    lpo_no = _get_row_value(header, "lpo_no", "")
    bill_to_display = _get_row_value(header, "bill_to", "") or ""
    ship_to_display = _get_row_value(header, "ship_to", "") or ""
    remarks = _get_row_value(header, "remarks", "") or ""
    salesman_name = _get_row_value(header, "salesman_name", "") or ""
    cancel_reason = _get_row_value(header, "cancel_reason", "") or ""

    total_amount = _num(_get_row_value(header, "total_amount", 0.0))
    vat_amount = _num(_get_row_value(header, "vat_amount", 0.0))
    net_total = _num(_get_row_value(header, "net_total", 0.0))
    discount_val = _num(_get_row_value(header, "discount", 0.0))

    # Styles as per ui.py
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallLabel",
               parent=styles["Normal"], textColor=colors.grey, fontSize=9, spaceAfter=2))
    styles.add(ParagraphStyle(name="Company",
               parent=styles["Heading2"], fontSize=12, spaceAfter=2))
    styles.add(ParagraphStyle(name="MetaLabel",
               parent=styles["Normal"], fontSize=9, textColor=colors.grey))
    styles.add(ParagraphStyle(name="MetaValue",
               parent=styles["Normal"], fontSize=10))
    styles.add(ParagraphStyle(name="SectionTitle",
               parent=styles["Heading3"], spaceAfter=6))

    # Header/footer callbacks (mirroring ui.py)
    def draw_header(canvas, doc):
        canvas.saveState()
        page_width, page_height = A4
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.25))
        inset = 20
        mark = "CANCELLED" if cancel_reason else "ORIGINAL COPY"
        canvas.drawRightString(page_width - inset, page_height - inset, mark)
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawCentredString(
            page_width / 2.0, doc.height + doc.topMargin + 0.5*cm, "Tax Invoice")
        canvas.restoreState()

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        y = doc.bottomMargin - 0.4*cm
        left_text = f"Salesperson: {salesman_name}" if salesman_name else "Confidential • Company Name"
        canvas.drawString(doc.leftMargin, y, left_text)
        canvas.drawRightString(doc.leftMargin + doc.width,
                               y, "Generated with ReportLab")
        canvas.restoreState()

    # Document + frame as per ui.py
    filename = os.path.join(out_dir, f"invoice_{inv_no}.pdf")
    doc = BaseDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    header_height = 0.1*cm
    footer_height = 1.0*cm
    frame_body = Frame(
        x1=doc.leftMargin,
        y1=doc.bottomMargin + footer_height,
        width=doc.width,
        height=doc.height - header_height - footer_height,
        id="body"
    )
    template = PageTemplate(
        id="main",
        frames=[frame_body],
        onPage=draw_header,
        onPageEnd=draw_footer
    )
    doc.addPageTemplates([template])

    story = []

    # 1) Header row: logo | company | meta
    logo = None
    for path in ("data/logos/c_logo.png", "data/logos/billmate_logo.png"):
        try:
            if os.path.exists(path):
                logo = Image(path, width=3.5*cm, height=3.5*cm)
                break
        except Exception:
            pass
    if logo is None:
        ph = Table([[Paragraph("Logo", styles["MetaLabel"])]],
                   colWidths=[3.5*cm], rowHeights=[3.5*cm])
        ph.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        logo = ph

    company_block = [
        [Paragraph("Rizq Al Ezzat Trading EST.", styles["Company"])],
        [Paragraph("P.O. Box : 1072", styles["SmallLabel"])],
        [Paragraph("Dubai, UAE", styles["SmallLabel"])],
        [Paragraph("TRN: TRN123456", styles["SmallLabel"])],
        [Paragraph("Email: rizq.alezzat@gmail.com | +97 503319123",
                   styles["SmallLabel"])],
    ]
    company_inner = Table(company_block, colWidths=[None])
    company_inner.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    invoice_meta = [
        [Paragraph("Invoice No.", styles["MetaLabel"]),
         Paragraph(str(inv_no), styles["MetaValue"])],
        [Paragraph("Invoice Date", styles["MetaLabel"]),
         Paragraph(inv_date_str, styles["MetaValue"])],
        [Paragraph("LPO No.", styles["MetaLabel"]), Paragraph(
            str(lpo_no or "-"), styles["MetaValue"])],
    ]
    meta_table = Table(invoice_meta, colWidths=[
                       3.0*cm, 4.2*cm], hAlign="RIGHT")
    meta_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    header_row = Table(
        data=[[logo, company_inner, meta_table]],
        colWidths=[4.2*cm, 10.0*cm, 4.8*cm]
    )
    header_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    # 2) Bill To | Ship To | Remarks row
    bill_to_tbl = Table([
        [Paragraph("Bill To", styles["MetaLabel"])],
        [Paragraph(bill_to_display.replace("\n", "<br/>")
                   or "-", styles["MetaValue"])],
    ], colWidths=[None])
    ship_to_tbl = Table([
        [Paragraph("Ship To", styles["MetaLabel"])],
        [Paragraph(ship_to_display.replace("\n", "<br/>")
                   or "-", styles["MetaValue"])],
    ], colWidths=[None])

    extra_lines = [[Paragraph("Remarks", styles["MetaLabel"])]]
    rm = remarks.strip()
    if cancel_reason:
        rm = f"Cancelled: {cancel_reason}" + (f"\n{rm}" if rm else "")
    extra_lines.append(
        [Paragraph(rm.replace("\n", "<br/>") or "-", styles["MetaValue"])])
    extra_tbl = Table(extra_lines, colWidths=[None])

    for t in (bill_to_tbl, ship_to_tbl, extra_tbl):
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

    second_row = Table(
        data=[[bill_to_tbl, ship_to_tbl, extra_tbl]],
        colWidths=[6.0*cm, 6.0*cm, 6.0*cm]
    )
    second_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(header_row)
    story.append(Spacer(1, 0.25*cm))
    story.append(second_row)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Items", styles["SectionTitle"]))

    # 3) Items table (repeat header on page breaks)
    table_data = [
        ["Sl No.", "Part No", "Description", "Qty",
            "Rate", "Tax %", "Tax", "Amount"]
    ]

    # items from fetch_invoice are dicts; .get is fine here
    for idx, it in enumerate(items, start=1):
        part_no = it.get("item_code") or ""
        desc = it.get("item_name") or ""
        qty = _num(it.get("quantity"))
        rate = _num(it.get("rate"))
        vat_pct = _num(it.get("vat_percentage"))
        vat_amt = _num(it.get("vat_amount"))
        line_amount = _num(it.get("net_amount"))
        table_data.append([
            idx,
            part_no,
            desc,
            int(qty) if float(qty).is_integer() else qty,
            f"{rate:,.2f}",
            f"{int(vat_pct)}%",
            f"{vat_amt:,.2f}",
            f"{line_amount:,.2f}",
        ])

    col_widths = [1.0*cm, 2.2*cm, 6.0*cm,
                  1.0*cm, 2.0*cm, 1.8*cm, 2.0*cm, 2.0*cm]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl_style = TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F3F7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("INNERGRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#C7D1DD")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7F8C8D")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    tbl.setStyle(tbl_style)

    story.append(tbl)
    story.append(Spacer(1, 0.5*cm))

    # 4) Totals block
    tax_details = [
        [Paragraph("Tax Details", styles["MetaLabel"])],
        [Paragraph(
            f"Taxable Amount: {_fmt(total_amount)}", styles["MetaValue"])],
        # Mixed rates possible
        [Paragraph("VAT Rate: —", styles["MetaValue"])],
        [Paragraph(f"Total VAT: {_fmt(vat_amount)}", styles["MetaValue"])],
    ]
    tax_tbl = Table(tax_details, colWidths=[9.0*cm])
    tax_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    totals_summary = [
        [Paragraph("Total", styles["MetaLabel"]), Paragraph(
            _fmt(total_amount), styles["MetaValue"])],
        [Paragraph("Discount", styles["MetaLabel"]), Paragraph(
            _fmt(discount_val), styles["MetaValue"])],
        [Paragraph("Taxable", styles["MetaLabel"]), Paragraph(
            _fmt(total_amount), styles["MetaValue"])],
        [Paragraph("VAT", styles["MetaLabel"]), Paragraph(
            _fmt(vat_amount), styles["MetaValue"])],
        [Paragraph("Net with Tax", styles["MetaLabel"]),
         Paragraph(_fmt(net_total), styles["MetaValue"])],
    ]
    totals_tbl = Table(totals_summary, colWidths=[
                       3.5*cm, 4.0*cm], hAlign="RIGHT")
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    row1 = Table([[tax_tbl, totals_tbl]], colWidths=[9.0*cm, 8.0*cm])
    row1.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(Spacer(1, 0.3*cm))
    story.append(row1)
    story.append(Spacer(1, 0.3*cm))

    # 5) Bank details + Seal
    bank_details = [
        [Paragraph("Bank Details", styles["MetaLabel"])],
        [Paragraph("Bank: ADIB", styles["MetaValue"])],
        [Paragraph("A/C No: 123456789012", styles["MetaValue"])],
        [Paragraph("SWIFTCODE: SBI1234", styles["MetaValue"])],
        [Paragraph("Branch: Andheri West, Mumbai", styles["MetaValue"])],
    ]
    bank_tbl = Table(bank_details, colWidths=[9.0*cm])
    bank_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    def seal_flowable():
        try:
            img_path = "data/logos/seal.png"
            if os.path.exists(img_path):
                img = Image(img_path, width=3.5*cm, height=3.5*cm)
                img.hAlign = "RIGHT"
                return img
        except Exception:
            pass
        ph = Table([[Paragraph("Seal", styles["MetaLabel"])]], colWidths=[
                   3.5*cm], rowHeights=[3.5*cm], hAlign="RIGHT")
        ph.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return ph

    row2 = Table([[bank_tbl, seal_flowable()]], colWidths=[9.0*cm, 8.0*cm])
    row2.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(row2)

    # Build
    doc.build(story)

    if open_after:
        try:
            webbrowser.open_new(r"file://" + os.path.abspath(filename))
        except Exception:
            pass

    return filename
