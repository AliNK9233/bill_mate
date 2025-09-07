# utils/pdf_helper.py
import os
import subprocess
from datetime import datetime, timedelta
from typing import Any, List, Tuple, Dict

from num2words import num2words
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, KeepTogether, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# model helpers from your app (assumed)
from models.invoice_model import fetch_invoice
from models.company_model import get_company_profile

DEFAULT_LOGO = os.path.abspath("data/logos/c_logo.png")


# ---------- small helpers ----------
def _safe(v, default=""):
    if v is None:
        return default
    return str(v)


def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        cleaned = s.replace(",", "").replace("₹", "").replace("$", "")
        return float(cleaned) if cleaned != "" else float(default)
    except Exception:
        return float(default)


def _fmt(v) -> str:
    return f"{_safe_float(v):,.2f}"


def _normalize_header(header: Tuple) -> Dict[str, Any]:
    if header is None:
        return {}
    try:
        if hasattr(header, "get"):
            return header
    except Exception:
        pass
    d = {}
    d["id"] = header[0] if len(header) > 0 else None
    d["invoice_no"] = header[1] if len(header) > 1 else ""
    d["invoice_date"] = header[2] if len(header) > 2 else ""
    d["customer_id"] = header[3] if len(header) > 3 else ""
    d["bill_to"] = header[4] if len(header) > 4 else ""
    d["ship_to"] = header[5] if len(header) > 5 else ""
    d["lpo_no"] = header[6] if len(header) > 6 else ""
    d["discount"] = _safe_float(header[7] if len(header) > 7 else 0.0)
    d["total_amount"] = _safe_float(header[8] if len(header) > 8 else 0.0)
    d["vat_amount"] = _safe_float(header[9] if len(header) > 9 else 0.0)
    d["net_total"] = _safe_float(header[10] if len(
        header) > 10 else (d["total_amount"] + d["vat_amount"]))
    d["created_at"] = header[11] if len(header) > 11 else ""
    d["updated_at"] = header[12] if len(header) > 12 else ""
    d["balance"] = _safe_float(header[13] if len(header) > 13 else 0.0)
    d["paid_amount"] = _safe_float(header[14] if len(header) > 14 else 0.0)
    d["status"] = header[15] if len(header) > 15 else ""
    d["salesman_id"] = header[16] if len(header) > 16 else ""
    return d


def _items_to_dicts(items: List[Tuple]) -> List[Dict[str, Any]]:
    out = []
    for it in items or []:
        try:
            serial = it[0] if len(it) > 0 else ""
            code = it[1] if len(it) > 1 else ""
            name = it[2] if len(it) > 2 else ""
            uom = it[3] if len(it) > 3 else ""
            qty = _safe_float(it[5] if len(it) > 5 else 0)
            rate = _safe_float(it[6] if len(it) > 6 else 0)
            subtotal = _safe_float(it[7] if len(it) > 7 else qty * rate)
            vat_pct = _safe_float(it[8] if len(it) > 8 else 0)
            vat_amt = _safe_float(it[9] if len(
                it) > 9 else subtotal * (vat_pct / 100.0))
            net = _safe_float(it[10] if len(it) > 10 else subtotal + vat_amt)
        except Exception:
            serial = code = name = uom = ""
            qty = rate = subtotal = vat_pct = vat_amt = net = 0.0
        out.append({
            "serial": serial, "code": code, "name": name, "uom": uom,
            "qty": qty, "rate": rate, "subtotal": subtotal, "vat_pct": vat_pct, "vat_amt": vat_amt, "net": net
        })
    return out


# ---------- PDF generation ----------
def generate_invoice_pdf(invoice_no: str, open_after: bool = False) -> str:
    """
    Generate invoice PDF. Returns absolute path. Header/footer are fixed; table repeats header on subsequent pages.
    """
    if not invoice_no:
        raise ValueError("invoice_no required")

    header_row, items_rows = fetch_invoice(invoice_no)
    if not header_row:
        raise ValueError(f"Invoice '{invoice_no}' not found")

    header = _normalize_header(header_row)
    items = _items_to_dicts(items_rows)
    company_row = get_company_profile() or {}

    # normalize company row
    if hasattr(company_row, "get"):
        company = company_row
    else:
        cols = ["id", "company_name", "trn_no", "address_line1", "address_line2", "city", "state", "country",
                "phone1", "phone2", "email", "website", "bank_name", "account_name", "account_number", "iban", "swift_code", "logo_path"]
        company = {}
        for i, k in enumerate(cols):
            try:
                company[k] = company_row[i]
            except Exception:
                company[k] = ""

    # output path
    safe_no = "".join(ch for ch in str(header.get("invoice_no")
                      or invoice_no) if ch.isalnum() or ch in "-_.")
    out_name = f"Invoice_{safe_no}.pdf"
    out_path = os.path.abspath(out_name)

    # styles (compact SAP-like)
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(
        "normal", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11)
    style_bold = ParagraphStyle(
        "bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12)
    style_title = ParagraphStyle(
        "title", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=16, alignment=1)
    style_small = ParagraphStyle(
        "small", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=9)

    PAGE_W, PAGE_H = A4
    left_margin = 12 * mm
    right_margin = 12 * mm
    top_margin = 18 * mm
    bottom_margin = 16 * mm
    content_w = PAGE_W - left_margin - right_margin

    # Header height reserved
    header_height = 72 * mm  # reserve approx area for logo + invoice meta + title
    footer_height = 20 * mm

    # frame for main content (items + totals)
    frame = Frame(left_margin, bottom_margin + footer_height, content_w, PAGE_H - top_margin - bottom_margin -
                  header_height - footer_height, leftPadding=6, rightPadding=6, topPadding=6, bottomPadding=6)

    doc = BaseDocTemplate(out_path, pagesize=A4, leftMargin=left_margin,
                          rightMargin=right_margin, topMargin=top_margin, bottomMargin=bottom_margin)

    # Draw header and footer (fixed)
    def draw_header(canvas, doc):
        canvas.saveState()
        logo_path = company.get("logo_path") or DEFAULT_LOGO
        logo_w = 34 * mm
        logo_h = 34 * mm
        header_top = PAGE_H - top_margin + 6

        # left: logo
        if logo_path and os.path.exists(logo_path):
            try:
                canvas.drawImage(logo_path, left_margin, header_top - logo_h,
                                 width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        # left: company details next to logo
        cx = left_margin + logo_w + 6
        cy = header_top - 6
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(cx, cy, _safe(company.get("company_name") or ""))
        canvas.setFont("Helvetica", 8.5)
        y = cy - 12
        for ln in (_safe(company.get("address_line1")), _safe(company.get("address_line2")), f"Phone: {_safe(company.get('phone1'))}", f"Email: {_safe(company.get('email'))}"):
            if ln:
                canvas.drawString(cx, y, ln)
                y -= 10

        # right: invoice meta box
        box_w = 88 * mm
        box_h = 30 * mm
        bx = PAGE_W - right_margin - box_w
        by = header_top - box_h
        canvas.setLineWidth(0.6)
        canvas.rect(bx, by, box_w, box_h)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(bx + 6, by + box_h - 10,
                          f"Invoice No.: {_safe(header.get('invoice_no'))}")
        inv_date = header.get("invoice_date") or ""
        try:
            if isinstance(inv_date, datetime):
                dstr = inv_date.strftime("%Y-%m-%d")
            else:
                dstr = str(inv_date).split("T")[0] if "T" in str(
                    inv_date) else str(inv_date)
        except Exception:
            dstr = _safe(inv_date)
        canvas.drawString(bx + 6, by + box_h - 22, f"Invoice Date: {dstr}")
        canvas.drawString(bx + 6, by + box_h - 34,
                          f"LPO No.: {_safe(header.get('lpo_no'))}")

        # centered title under header boxes
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawCentredString(PAGE_W / 2.0, by - 6, "TAX INVOICE")
        canvas.restoreState()

    def draw_footer(canvas, doc):
        canvas.saveState()
        footer_y = bottom_margin + 6
        canvas.setFont("Helvetica", 8)
        bank_line = f"BANK: {_safe(company.get('bank_name'))}   IBAN: {_safe(company.get('iban'))}   AC: {_safe(company.get('account_number'))}"
        canvas.drawString(left_margin, footer_y + 6, bank_line)
        canvas.drawRightString(PAGE_W - right_margin,
                               footer_y + 6, f"Page {doc.page}")
        canvas.restoreState()

    template = PageTemplate(
        id="tpl", frames=[frame], onPage=draw_header, onPageEnd=draw_footer)
    doc.addPageTemplates([template])

    # Build story
    story = []
    story.append(Spacer(1, 4))

    # Bill/Ship/Salesman boxes (single row)
    bill_w = content_w * 0.46
    ship_w = content_w * 0.34
    sales_w = content_w * 0.20
    bill = Paragraph(
        f"<b>Bill To:</b><br/>{_safe(header.get('bill_to'))}", style_normal)
    ship = Paragraph(
        f"<b>Ship To:</b><br/>{_safe(header.get('ship_to'))}", style_normal)
    sales = Paragraph(
        f"<b>Salesman:</b><br/>{_safe(header.get('salesman_id'))}", style_normal)
    bs_table = Table([[bill, ship, sales]], colWidths=[
                     bill_w, ship_w, sales_w])
    bs_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f6f7f7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bs_table)
    story.append(Spacer(1, 6))

    # Items table
    # column widths (mm) tuned to sample (converted later to points)
    col_w_mm = [10, 22, 80, 18, 18, 22, 28, 14, 28]
    col_w_pts = [w * mm for w in col_w_mm]
    # scale to content width
    total_w = sum(col_w_pts)
    scale = content_w / total_w if total_w > 0 else 1.0
    col_w = [w * scale for w in col_w_pts]

    header_titles = ["Sl No.", "Item code", "Item Name", "Unit",
                     "Qty.", "Rate", "Sub total", "Vat %", "Net amount"]
    table_data = [header_titles]
    for it in items:
        name = _safe(it["name"])
        if len(name) > 72:
            name = name[:69] + "..."
        table_data.append([
            str(it["serial"] or ""),
            _safe(it["code"]),
            name,
            _safe(it["uom"]),
            _fmt(it["qty"]),
            _fmt(it["rate"]),
            _fmt(it["subtotal"]),
            f"{_fmt(it['vat_pct'])}",
            _fmt(it["net"])
        ])

    # Main table with repeat header
    main_table = Table(table_data, colWidths=col_w, repeatRows=1)
    main_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efefef")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(main_table)
    story.append(Spacer(1, 8))

    # Totals and tax - keep together so it appears on same page
    taxable = sum(it["subtotal"] for it in items)
    vat_total = sum(it["vat_amt"] for it in items)
    net_total = header.get("net_total") or (taxable + vat_total)
    discount = header.get("discount") or 0.0

    # Left tax details
    left_tbl = [
        ["Tax details", ""],
        ["Taxable Amount", _fmt(taxable)],
        ["VAT Rate %", "5%"],
        ["Total VAT", _fmt(vat_total)]
    ]
    left_table = Table(left_tbl, colWidths=[
                       content_w * 0.5 * 0.6, content_w * 0.5 * 0.4])
    left_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f7f7")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    # Right totals
    right_tbl = [
        ["Total", _fmt(taxable)],
        ["Discount", _fmt(discount)],
        ["Taxable", _fmt(taxable - discount)],
        ["VAT 5%", _fmt(vat_total)],
        ["Net Value", _fmt(net_total)]
    ]
    right_table = Table(right_tbl, colWidths=[
                        content_w * 0.4 * 0.6, content_w * 0.4 * 0.4])
    right_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f7f7")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    totals_table = Table([[left_table, right_table]], colWidths=[
                         content_w * 0.6, content_w * 0.4])
    totals_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    # Amount in words and bank details
    try:
        words = num2words(float(net_total), lang="en").title() + " Only"
    except Exception:
        words = ""
    words_para = Paragraph(f"<b>Amount (in words):</b> {words}", style_small)

    bank_lines = []
    if company.get("account_name"):
        bank_lines.append(f"ACCOUNT NAME: {company.get('account_name')}")
    if company.get("iban"):
        bank_lines.append(f"ACCOUNT IBAN: {company.get('iban')}")
    if company.get("account_number"):
        bank_lines.append(f"ACCOUNT No.: {company.get('account_number')}")
    if company.get("bank_name"):
        bank_lines.append(f"BANK NAME: {company.get('bank_name')}")
    if company.get("swift_code"):
        bank_lines.append(f"SWIFTCODE: {company.get('swift_code')}")
    bank_paras = [Paragraph(bl, style_small) for bl in bank_lines]

    # Ensure totals + words + bank details stay together on the final page (KeepTogether)
    footer_block = [Spacer(1, 8), totals_table, Spacer(
        1, 8), words_para, Spacer(1, 6)]
    footer_block.extend(bank_paras)

    story.append(KeepTogether(footer_block))

    # Build doc
    doc.build(story)

    # open after generation
    if open_after:
        try:
            if os.name == "nt":
                os.startfile(out_path)
            else:
                subprocess.Popen(["xdg-open", out_path])
        except Exception:
            pass

    return out_path
