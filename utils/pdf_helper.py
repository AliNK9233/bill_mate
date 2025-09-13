# utils/pdf_helper.py
import os
import webbrowser
import sqlite3
from contextlib import closing
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image,
    PageBreak, NextPageTemplate
)
from models import invoice_model as invoice_model
from models.invoice_model import fetch_invoice

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
    if row is None:
        return default
    try:
        if isinstance(row, sqlite3.Row):
            return row[key] if key in row.keys() else default
        if hasattr(row, "get"):
            return row.get(key, default)
    except Exception:
        pass
    return default


def _get_company_profile():
    try:
        conn = invoice_model._connect()
        conn.row_factory = sqlite3.Row
        with closing(conn):
            cur = conn.cursor()
            cur.execute("SELECT * FROM company_profile WHERE id = 1 LIMIT 1")
            r = cur.fetchone()
            if not r:
                return {}
            # convert sqlite3.Row to plain dict for easier access
            return {k: (r[k] if k in r.keys() else None) for k in r.keys()}
    except Exception:
        return {}


def _get_salesman_phone_by_id(salesman_id):
    """Lookup salesman phone from salesman table using invoice_model._connect()"""
    if not salesman_id:
        return ""
    try:
        conn = invoice_model._connect()
        conn.row_factory = sqlite3.Row
        with closing(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT phone FROM salesman WHERE id = ? LIMIT 1", (salesman_id,))
            r = cur.fetchone()
            if r:
                if isinstance(r, sqlite3.Row):
                    return r["phone"] if "phone" in r.keys() else ""
                return r.get("phone", "")
    except Exception:
        pass
    return ""


cp = _get_company_profile()

# -------- main API --------


def generate_invoice_pdf(invoice_no: str,
                         copies: list | None = None,
                         open_after: bool = False,
                         out_dir: str = "reports") -> str:
    """
    Generate invoice PDF with multiple labeled copies (in one file).
    - invoice_no: invoice identifier to fetch from DB via fetch_invoice()
    - copies: list of labels, e.g. ["ORIGINAL COPY","DUPLICATE COPY"]. If empty or None -> single copy no labels.
    - open_after: if True, open generated PDF.
    - out_dir: output directory.
    Returns path to generated PDF file.
    """
    os.makedirs(out_dir, exist_ok=True)
    copies = ["ORIGINAL COPY", "DUPLICATE COPY"]
    header, items = fetch_invoice(invoice_no)
    if not header:
        raise ValueError(f"Invoice not found: {invoice_no}")

    # company info from DB
    company_name = (cp.get("company_name")
                    or "Rizq Al Ezzat Trading EST.").strip().upper()
    trn = (cp.get("trn_no") or cp.get("trn") or "").strip()
    addr1 = (cp.get("address_line1") or "").strip()
    addr2 = (cp.get("address_line2") or "").strip()
    city = (cp.get("city") or "").strip()
    state = (cp.get("state") or "").strip()
    country = (cp.get("country") or "").strip()
    email = (cp.get("email") or "").strip()
    phone1 = (cp.get("phone1") or "").strip()
    phone2 = (cp.get("phone2") or "").strip()
    website = (cp.get("website") or "").strip()

    # bank details from DB (not used currently)
    bank_name = (cp.get("bank_name") or "").strip()
    bank_branch = (cp.get("bank_branch") or cp.get("branch") or "").strip()
    account_name = (cp.get("account_name") or "").strip()
    account_number = (cp.get("account_number") or "").strip()
    iban = (cp.get("iban") or "").strip()
    swift_code = (cp.get("swift_code") or cp.get("swift") or "").strip()

    # invoice header fields
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
    salesman_id = _get_row_value(header, "salesman_id", None)
    cancel_reason = _get_row_value(header, "cancel_reason", "") or ""

    salesman_phone = _get_salesman_phone_by_id(salesman_id) or ""

    total_amount = _num(_get_row_value(header, "total_amount", 0.0))
    vat_amount = _num(_get_row_value(header, "vat_amount", 0.0))
    net_total = _num(_get_row_value(header, "net_total", 0.0))
    discount_val = _num(_get_row_value(header, "discount", 0.0))

    # styles
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
    # dedicated company name style for nicer wrapping
    styles.add(ParagraphStyle(name="CompanyName",
               parent=styles["Heading2"], fontSize=13, leading=15, spaceAfter=2, wordWrap="LTR"))

    # prepare copies
    if copies:
        copy_labels = [str(c).strip() for c in copies if str(c).strip()]
        if not copy_labels:
            copy_labels = []
    else:
        copy_labels = []

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

    # counters & flags
    if copy_labels:
        counters = {label: 0 for label in copy_labels}
        first_shown = {label: False for label in copy_labels}
    else:
        counters = {"single": 0}
        first_shown = {"single": False}

    # header factory
    def make_draw_header(mark_text: str | None, copy_key: str):
        def draw_header(canvas, doc_inner):
            canvas._current_copy = copy_key
            canvas.saveState()
            page_width, page_height = A4
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.22))
            inset = 20
            if mark_text:
                if not first_shown.get(copy_key, False):
                    canvas.drawRightString(
                        page_width - inset, page_height - inset, mark_text)
                    first_shown[copy_key] = True
            canvas.setFillColor(colors.black)
            canvas.setFont("Helvetica-Bold", 12)
            canvas.drawCentredString(
                page_width / 2.0, doc_inner.height + doc_inner.topMargin + 0.5*cm, "Tax Invoice")
            canvas.restoreState()
        return draw_header

    # footer uses current_copy to restart counters per copy
    def draw_footer(canvas, doc_inner):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        y = doc_inner.bottomMargin - 0.4*cm
        left_text = company_name
        canvas.drawString(doc_inner.leftMargin, y, left_text)

        copy_key = getattr(canvas, "_current_copy", None)
        if not copy_key:
            copy_key = "single" if not copy_labels else copy_labels[0]
        counters[copy_key] += 1
        page_label = counters[copy_key]
        right_x = doc_inner.leftMargin + doc_inner.width
        canvas.drawRightString(right_x, y, f"Page {page_label}")
        canvas.restoreState()

    # create templates
    if copy_labels:
        for label in copy_labels:
            tpl = PageTemplate(
                id=label,
                frames=[frame_body],
                onPage=make_draw_header(label, label),
                onPageEnd=draw_footer
            )
            doc.addPageTemplates([tpl])
    else:
        tpl = PageTemplate(
            id="single",
            frames=[frame_body],
            onPage=make_draw_header(None, "single"),
            onPageEnd=draw_footer
        )
        doc.addPageTemplates([tpl])

    # build header block function (so repeated per copy)
    def build_header_block():
        # logo left-top aligned and slightly smaller
        logo = None
        for path in ("data/logos/c_logo.png", "data/logos/billmate_logo.png"):
            try:
                if os.path.exists(path):
                    logo = Image(path, width=3.0*cm, height=3.0*cm)
                    logo.hAlign = "LEFT"
                    break
            except Exception:
                logo = None
        if logo is None:
            ph = Table([[Paragraph("Logo", styles["SmallLabel"])]],
                       colWidths=[3.0*cm], rowHeights=[3.0*cm])
            ph.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            logo = ph

        # company block - Paragraphs for better wrapping
        company_lines = [Paragraph(company_name, styles["CompanyName"])]

        # address lines: prefer address_line1 then address_line2; combine city/state/country
        if addr1:
            company_lines.append(Paragraph(addr1, styles["SmallLabel"]))
        if addr2:
            company_lines.append(Paragraph(addr2, styles["SmallLabel"]))

        loc_parts = " ".join(p for p in (city, state, country) if p)
        if loc_parts:
            company_lines.append(Paragraph(loc_parts, styles["SmallLabel"]))

        if trn:
            company_lines.append(
                Paragraph(f"TRN: {trn}", styles["SmallLabel"]))
        # contact line: email and primary phone(s)
        contact_parts = []
        if email:
            contact_parts.append(email)
        if phone1:
            contact_parts.append(phone1)
        elif phone2:
            contact_parts.append(phone2)

        if website:
            contact_parts.append(website)

        if contact_parts:
            company_lines.append(Paragraph(" | ".join(
                contact_parts), styles["SmallLabel"]))

        company_inner = Table([[c] for c in company_lines], colWidths=[None])
        company_inner.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0),
                               (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))

        invoice_meta = [
            [Paragraph("Invoice No.", styles["MetaLabel"]),
             Paragraph(str(inv_no), styles["MetaValue"])],
            [Paragraph("Invoice Date", styles["MetaLabel"]),
             Paragraph(inv_date_str, styles["MetaValue"])],
            [Paragraph("LPO No.", styles["MetaLabel"]), Paragraph(
                str(lpo_no or "-"), styles["MetaValue"])],
        ]
        meta_table = Table(invoice_meta, colWidths=[
                           2.8*cm, 3.0*cm], hAlign="RIGHT")
        meta_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))

        # Determine column widths favouring company
        logo_col_w = 3.2*cm
        company_col_w = 11.0*cm
        meta_col_w = doc.width - (logo_col_w + company_col_w)
        if meta_col_w < 3.0*cm:
            meta_col_w = 3.0*cm
            company_col_w = doc.width - (logo_col_w + meta_col_w)

        header_row = Table([[logo, company_inner, meta_table]], colWidths=[
                           logo_col_w, company_col_w, meta_col_w])
        header_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "LEFT"),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return header_row

    # seal flowable (moved slightly right so bank name fits)
    def seal_flowable():
        try:
            img_path = "data/logos/seal.png"
            if os.path.exists(img_path):
                img = Image(img_path, width=3.5*cm, height=3.5*cm)
                img.hAlign = "RIGHT"
                return img
        except Exception:
            pass
        ph = Table([[Paragraph("Seal", styles["SmallLabel"])]], colWidths=[
                   3.5*cm], rowHeights=[3.5*cm], hAlign="RIGHT")
        ph.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.lightgrey),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        return ph

    # flow builder for a single copy
    def build_copy_flowables():
        flow = []
        header_row = build_header_block()
        flow.append(header_row)
        flow.append(Spacer(1, 0.25*cm))

        # Bill To | Ship To | Remarks
        bill_to_tbl = Table([[Paragraph("Bill To", styles["MetaLabel"])], [Paragraph(
            bill_to_display.replace("\n", "<br/>") or "-", styles["MetaValue"])]], colWidths=[None])
        ship_to_tbl = Table([[Paragraph("Ship To", styles["MetaLabel"])], [Paragraph(
            ship_to_display.replace("\n", "<br/>") or "-", styles["MetaValue"])]], colWidths=[None])

        rm = remarks.strip()
        if cancel_reason:
            rm = f"Cancelled: {cancel_reason}" + (f"\n{rm}" if rm else "")

        sp_lines = []
        if salesman_name:
            sp_lines.append(f"Salesperson: {salesman_name}")
        if salesman_phone:
            sp_lines.append(f"Phone: {salesman_phone}")
        if sp_lines:
            rm = (rm + "\n" if rm else "") + ("\n".join(sp_lines))

        extra_lines = [[Paragraph("Remarks", styles["MetaLabel"])], [
            Paragraph(rm.replace("\n", "<br/>") or "-", styles["MetaValue"])]]
        extra_tbl = Table(extra_lines, colWidths=[None])

        for t in (bill_to_tbl, ship_to_tbl, extra_tbl):
            t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING",
                       (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("VALIGN", (0, 0), (-1, -1), "TOP")]))

        second_row = Table([[bill_to_tbl, ship_to_tbl, extra_tbl]], colWidths=[
                           6.0*cm, 6.0*cm, 6.0*cm])
        second_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        flow.append(second_row)
        flow.append(Spacer(1, 0.5*cm))
        flow.append(Paragraph("Items", styles["SectionTitle"]))

        # items table
        table_data = [["Sl No.", "Part No", "Description",
                       "Qty", "Rate", "Tax %", "Tax", "Amount"]]
        for idx, it in enumerate(items, start=1):
            part_no = it.get("item_code") or ""
            desc = it.get("item_name") or ""
            qty = _num(it.get("quantity"))
            rate = _num(it.get("rate"))
            vat_pct = _num(it.get("vat_percentage"))
            vat_amt = _num(it.get("vat_amount"))
            line_amount = _num(it.get("net_amount"))
            table_data.append([idx, part_no, desc, int(qty) if float(qty).is_integer(
            ) else qty, f"{rate:,.2f}", f"{int(vat_pct)}%", f"{vat_amt:,.2f}", f"{line_amount:,.2f}"])

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

        flow.append(tbl)
        flow.append(Spacer(1, 0.5*cm))

        # totals block
        tax_details = [[Paragraph("Tax Details", styles["MetaLabel"])],
                       [Paragraph(
                           f"Taxable Amount: {_fmt(total_amount)}", styles["MetaValue"])],
                       [Paragraph("VAT Rate: 5%", styles["MetaValue"])],
                       [Paragraph(f"Total VAT: {_fmt(vat_amount)}", styles["MetaValue"])]]
        tax_tbl = Table(tax_details, colWidths=[9.0*cm])
        tax_tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                         ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("VALIGN", (0, 0), (-1, -1), "TOP")]))

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
        totals_tbl.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0),
                            (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))

        row1 = Table([[tax_tbl, totals_tbl]], colWidths=[9.0*cm, 8.0*cm])
        row1.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(Spacer(1, 0.3*cm))
        flow.append(row1)
        flow.append(Spacer(1, 0.3*cm))

        # Bank details + seal (seal pushed right to allow long bank names)
        bank_details = [[Paragraph("Bank Details", styles["MetaLabel"])]]
        if bank_name:
            bank_details.append(
                [Paragraph(f"Bank: {bank_name}", styles["MetaValue"])])
        if bank_branch:
            bank_details.append(
                [Paragraph(f"Branch: {bank_branch}", styles["MetaValue"])])
        if account_name:
            bank_details.append(
                [Paragraph(f"A/C Name: {account_name}", styles["MetaValue"])])
        if account_number:
            bank_details.append(
                [Paragraph(f"A/C No: {account_number}", styles["MetaValue"])])
        if iban:
            bank_details.append(
                [Paragraph(f"IBAN: {iban}", styles["MetaValue"])])
        if swift_code:
            bank_details.append(
                [Paragraph(f"SWIFT: {swift_code}", styles["MetaValue"])])
        # wider to accomodate long names
        bank_tbl = Table(bank_details, colWidths=[10.5*cm])
        bank_tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                          ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("VALIGN", (0, 0), (-1, -1), "TOP")]))

        row2 = Table([[bank_tbl, seal_flowable()]],
                     colWidths=[10.5*cm, doc.width - 10.5*cm])
        row2.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING",
                      (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        flow.append(row2)

        return flow

    # compose story
    story = []
    if copy_labels:
        for idx, label in enumerate(copy_labels):
            counters[label] = 0
            first_shown[label] = False
            story.append(NextPageTemplate(label))
            if idx > 0:
                story.append(PageBreak())
            story.extend(build_copy_flowables())
    else:
        counters["single"] = 0
        first_shown["single"] = False
        story.append(NextPageTemplate("single"))
        story.extend(build_copy_flowables())

    # build pdf
    doc.build(story)

    if open_after:
        try:
            webbrowser.open_new(r"file://" + os.path.abspath(filename))
        except Exception:
            pass

    return filename
