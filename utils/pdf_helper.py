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
    Image, KeepTogether, PageBreak, NextPageTemplate
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
    """
    Convert raw rows from fetch_invoice() to a list of dicts used by the PDF builder.

    Expects item tuple layout similar to:
      (serial, code, name, uom, per_box_qty, qty, rate, subtotal, vat_pct, vat_amt, net)

    If your fetch_invoice() places per_box_qty at a different index, change the
    index below (currently it uses index 4).
    """
    out = []
    for it in items or []:
        try:
            serial = it[0] if len(it) > 0 else ""
            code = it[1] if len(it) > 1 else ""
            name = it[2] if len(it) > 2 else ""
            uom = it[3] if len(it) > 3 else ""
            # <-- per_box_qty: adjust index if your DB returns differently
            per_box_qty = int(it[4]) if len(
                it) > 4 and it[4] not in (None, "") else 1
            qty = _safe_float(it[5] if len(it) > 5 else 0)
            rate = _safe_float(it[6] if len(it) > 6 else 0)
            subtotal = _safe_float(it[7] if len(it) > 7 else qty * rate)
            vat_pct = _safe_float(it[8] if len(it) > 8 else 0)
            vat_amt = _safe_float(it[9] if len(
                it) > 9 else subtotal * (vat_pct / 100.0))
            net = _safe_float(it[10] if len(it) > 10 else subtotal + vat_amt)
        except Exception:
            serial = code = name = uom = ""
            per_box_qty = 1
            qty = rate = subtotal = vat_pct = vat_amt = net = 0.0
        out.append({
            "serial": serial,
            "code": code,
            "name": name,
            "uom": uom,
            "qty": qty,
            "rate": rate,
            "subtotal": subtotal,
            "vat_pct": vat_pct,
            "vat_amt": vat_amt,
            "net": net
        })
    return out


# ---------- PDF generation ----------
def generate_invoice_pdf(invoice_no: str, open_after: bool = False) -> str:
    """
    Generate a single PDF containing two sequential copies: ORIGINAL then DUPLICATE.
    Returns absolute path to the generated PDF.
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

    # styles
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

    # Header/footer heights
    header_height = 82 * mm
    footer_height = 24 * mm

    # frame for main content (items + totals)
    frame = Frame(left_margin, bottom_margin + footer_height, content_w,
                  PAGE_H - top_margin - bottom_margin - header_height - footer_height,
                  leftPadding=6, rightPadding=6, topPadding=6, bottomPadding=6)

    doc = BaseDocTemplate(out_path, pagesize=A4, leftMargin=left_margin,
                          rightMargin=right_margin, topMargin=top_margin, bottomMargin=bottom_margin)

    # draw header factory
    def make_draw_header(copy_label: str):
        def draw_header(canvas, doc):
            canvas.saveState()
            logo_path = company.get("logo_path") or DEFAULT_LOGO
            logo_w = 34 * mm
            logo_h = 34 * mm

            # Title centered row
            canvas.setFont("Helvetica-Bold", 16)
            title_y = PAGE_H - (top_margin - 6)
            canvas.drawCentredString(PAGE_W / 2.0, title_y, "TAX INVOICE")

            # Copy label (top-right)
            canvas.setFont("Helvetica-Bold", 9)
            canvas.setFillColor(colors.HexColor("#333333"))
            canvas.drawRightString(PAGE_W - right_margin,
                                   title_y - 14, copy_label.upper())
            canvas.setFillColor(colors.black)

            # Row below title: logo left, company details right
            content_top = title_y - 22
            logo_y = content_top - logo_h + 6
            if logo_path and os.path.exists(logo_path):
                try:
                    canvas.drawImage(logo_path, left_margin, logo_y, width=logo_w,
                                     height=logo_h, preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass

            # company block (right aligned)
            cx_right = PAGE_W - right_margin
            company_lines = []
            if company.get("company_name"):
                company_lines.append(company.get("company_name"))
            addr_parts = [company.get("address_line1")
                          or "", company.get("address_line2") or ""]
            addr_text = ", ".join([p for p in addr_parts if p])
            if addr_text:
                company_lines.append(addr_text)
            contact = []
            if company.get("phone1"):
                contact.append(f"Phone: {company.get('phone1')}")
            if company.get("email"):
                contact.append(f"Email: {company.get('email')}")
            if contact:
                company_lines.append(" | ".join(contact))
            if company.get("trn_no"):
                company_lines.append(f"TRN: {company.get('trn_no')}")

            canvas.setFont("Helvetica-Bold", 11)
            ypos = content_top - 2
            if company_lines:
                canvas.drawRightString(cx_right, ypos, _safe(company_lines[0]))
                canvas.setFont("Helvetica", 8.5)
                ypos -= 11
                for ln in company_lines[1:]:
                    canvas.drawRightString(cx_right, ypos, _safe(ln))
                    ypos -= 10

            # thin separator below header
            canvas.setStrokeColor(colors.HexColor("#cccccc"))
            canvas.setLineWidth(0.6)
            sep_y = logo_y - 6
            canvas.line(left_margin, sep_y, PAGE_W - right_margin, sep_y)

            # 3-column Bill/Ship/Sales block
            box_top = sep_y - 6
            box_height = 60 * mm / 3
            box_y = box_top - box_height
            canvas.setLineWidth(0.4)
            canvas.setStrokeColor(colors.HexColor("#dddddd"))
            canvas.rect(left_margin, box_y, content_w,
                        box_height, stroke=1, fill=0)

            # Left column: Bill To
            left_x = left_margin + 6
            left_w = content_w * 0.36
            tx = left_x
            ty = box_top - 12
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawString(tx, ty, "Bill To:")
            canvas.setFont("Helvetica", 8)
            ty -= 11
            bill_text = header.get("bill_to") or ""
            if isinstance(bill_text, dict):
                lines = []
                if bill_text.get("name"):
                    lines.append(bill_text.get("name"))
                if bill_text.get("address_line1"):
                    lines.append(bill_text.get("address_line1"))
                if bill_text.get("address_line2"):
                    lines.append(bill_text.get("address_line2"))
                if bill_text.get("trn_no"):
                    lines.append(f"TRN: {bill_text.get('trn_no')}")
            else:
                lines = [l.strip()
                         for l in str(bill_text).splitlines() if l.strip()]
            for ln in lines[:4]:
                canvas.drawString(tx, ty, _safe(ln))
                ty -= 10

            # Middle column: Ship To and Salesperson
            mid_x = left_margin + left_w + 8
            tx = mid_x
            ty = box_top - 12
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawString(tx, ty, "Ship To:")
            canvas.setFont("Helvetica", 8)
            ty -= 11
            ship_text = header.get("ship_to") or ""
            if isinstance(ship_text, dict):
                lines = []
                if ship_text.get("name"):
                    lines.append(ship_text.get("name"))
                if ship_text.get("address_line1"):
                    lines.append(ship_text.get("address_line1"))
                if ship_text.get("address_line2"):
                    lines.append(ship_text.get("address_line2"))
            else:
                lines = [l.strip()
                         for l in str(ship_text).splitlines() if l.strip()]
            for ln in lines[:3]:
                canvas.drawString(tx, ty, _safe(ln))
                ty -= 10
            salesman_display = header.get("salesman_id") or ""
            if salesman_display:
                canvas.setFont("Helvetica-Bold", 8)
                canvas.drawString(tx, box_y + 6, "Sales Person:")
                canvas.setFont("Helvetica", 8)
                canvas.drawString(tx + 60, box_y + 6, _safe(salesman_display))

            # Right column: Invoice metadata
            tx = PAGE_W - right_margin - 6
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawRightString(
                tx, box_top - 12, f"Invoice No.: {_safe(header.get('invoice_no'))}")
            canvas.setFont("Helvetica", 8)
            inv_date = header.get("invoice_date") or ""
            try:
                if isinstance(inv_date, datetime):
                    dstr = inv_date.strftime("%d-%b-%Y")
                else:
                    dstr = str(inv_date).split("T")[0] if "T" in str(
                        inv_date) else str(inv_date)
            except Exception:
                dstr = _safe(inv_date)
            canvas.drawRightString(tx, box_top - 24, f"Invoice Date: {dstr}")
            canvas.drawRightString(
                tx, box_top - 36, f"LPO No.: {_safe(header.get('lpo_no'))}")

            canvas.restoreState()
        return draw_header

    # Footer drawing
    def draw_footer(canvas, doc):
        canvas.saveState()
        footer_y = bottom_margin - 6
        bank_parts = []
        if company.get("bank_name"):
            bank_parts.append(f"BANK: {company.get('bank_name')}")
        if company.get("account_name"):
            bank_parts.append(f"A/C: {company.get('account_name')}")
        if company.get("account_number"):
            bank_parts.append(f"No.: {company.get('account_number')}")
        if company.get("iban"):
            bank_parts.append(f"IBAN: {company.get('iban')}")
        bank_line1 = "   ".join(bank_parts[:2])
        bank_line2 = "   ".join(bank_parts[2:]) if len(bank_parts) > 2 else ""
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#333333"))
        canvas.drawString(left_margin, footer_y + 10, bank_line1)
        if bank_line2:
            canvas.drawString(left_margin, footer_y, bank_line2)
        canvas.drawRightString(PAGE_W - right_margin,
                               footer_y + 10, f"Page {doc.page}")
        if company.get("website"):
            canvas.setFont("Helvetica-Oblique", 7.5)
            canvas.drawCentredString(
                PAGE_W / 2.0, footer_y - 6, _safe(company.get("website")))
        canvas.restoreState()

    # Create two page templates: ORIGINAL and DUPLICATE
    tpl_orig = PageTemplate(id="ORIGINAL", frames=[frame], onPage=make_draw_header(
        "ORIGINAL"), onPageEnd=draw_footer)
    tpl_dup = PageTemplate(id="DUPLICATE", frames=[frame], onPage=make_draw_header(
        "DUPLICATE"), onPageEnd=draw_footer)
    doc.addPageTemplates([tpl_orig, tpl_dup])

    # Helper to build single copy content
    def build_single_copy():
        s = []
        s.append(Spacer(1, 4))

        # Bill/Ship/Salesman boxes (table)
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
        s.append(bs_table)
        s.append(Spacer(1, 6))

        # Items table
        col_w_mm = [10, 22, 80, 18, 30, 18, 22, 14, 28]
        col_w_pts = [w * mm for w in col_w_mm]
        total_w = sum(col_w_pts)
        scale = content_w / total_w if total_w > 0 else 1.0
        col_w = [w * scale for w in col_w_pts]

        header_titles = ["Sl No.", "Item code", "Item Name", "Unit",
                         "Qty.", "Rate", "Sub total", "Vat %", "Net amount"]
        table_data = [header_titles]
        for i, it in enumerate(items, start=1):
            name = _safe(it["name"])
            if len(name) > 72:
                name = name[:69] + "..."
            per_box = int(it.get("per_box_qty", 1) or 1)
            qty = float(it.get("qty") or 0)
            # if qty is fractional we still compute total_units gracefully
            try:
                total_units = int(per_box * qty)
            except Exception:
                total_units = per_box * qty
            # display as requested: CTN {per_box_qty} x {qty} = {total_units}
            qty_display = f"CTN {per_box} x {int(qty)} = {total_units}"
            table_data.append([
                str(i),
                _safe(it["code"]),
                name,
                _safe(it["uom"]),
                qty_display,
                _fmt(it["rate"]),
                _fmt(it["subtotal"]),
                f"{_fmt(it['vat_pct'])}",
                _fmt(it["net"])
            ])

        main_table = Table(table_data, colWidths=col_w, repeatRows=1)
        main_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efefef")),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("ALIGN", (4, 0), (4, -1), "CENTER"),
            ("ALIGN", (5, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        s.append(main_table)
        s.append(Spacer(1, 8))

        # Totals and tax (KeepTogether)
        taxable = sum(it["subtotal"] for it in items)
        vat_total = sum(it["vat_amt"] for it in items)
        net_total = header.get("net_total") or (taxable + vat_total)
        discount = header.get("discount") or 0.0

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
        totals_table.setStyle(TableStyle(
            [("VALIGN", (0, 0), (-1, -1), "TOP")]))

        try:
            words = num2words(float(net_total), lang="en").title() + " Only"
        except Exception:
            words = ""
        words_para = Paragraph(
            f"<b>Amount (in words):</b> {words}", style_small)

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

        footer_block = [Spacer(1, 8), totals_table, Spacer(
            1, 8), words_para, Spacer(1, 6)]
        footer_block.extend(bank_paras)

        s.append(KeepTogether(footer_block))

        return s

    # Build story: ORIGINAL copy then DUPLICATE copy
    story = []
    # first copy uses ORIGINAL template automatically (first page uses first template added)
    story.extend(build_single_copy())

    # switch to DUPLICATE template and break page, then append identical content
    story.append(NextPageTemplate("DUPLICATE"))
    story.append(PageBreak())
    story.extend(build_single_copy())

    # build
    doc.build(story)

    # optionally open the file
    if open_after:
        try:
            if os.name == "nt":
                os.startfile(out_path)
            else:
                subprocess.Popen(["xdg-open", out_path])
        except Exception:
            pass

    return out_path
