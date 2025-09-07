# utils/pdf_helper.py
import os
import subprocess
from datetime import datetime, timedelta
from typing import Any, List, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Frame, PageTemplate
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfgen import canvas

# Project model helpers (must exist)
from models.invoice_model import fetch_invoice
from models.company_model import get_company_profile

# optional number-to-words lib
try:
    from num2words import num2words
except Exception:
    def num2words(n, lang="en_IN"):
        return str(n)

DB_DEFAULT_LOGO = os.path.abspath("data/logos/c_logo.png")


def _safe_float(v: Any, default: float = 0.0) -> float:
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


def _format_currency(v: Any) -> str:
    return f"{_safe_float(v):,.2f}"


def _normalize_row(row, header_keys):
    """Accept tuple/list or dict-like row; return dict with header_keys mapping."""
    if row is None:
        return {k: None for k in header_keys}
    if hasattr(row, "get"):
        # already mapping-like
        return row
    d = {}
    for i, k in enumerate(header_keys):
        try:
            d[k] = row[i]
        except Exception:
            d[k] = None
    return d


class NumberedCanvas(canvas.Canvas):
    """
    Canvas subclass that supports 'Page X of Y' by doing a two-pass save.
    """

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add page info to each saved page (two pass)."""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            # draw page number centered at bottom
            self.draw_page_number(self._pageNumber, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_num, total_pages):
        footer_y = 15 * mm
        page_text = f"Page {page_num} of {total_pages}"
        self.setFont("Helvetica", 8)
        self.drawCentredString(A4[0] / 2.0, footer_y, page_text)


def _ensure_logo_path(path: str):
    if not path:
        return DB_DEFAULT_LOGO if os.path.exists(DB_DEFAULT_LOGO) else None
    if os.path.exists(path):
        return path
    return DB_DEFAULT_LOGO if os.path.exists(DB_DEFAULT_LOGO) else None


def generate_invoice_pdf(invoice_no: str, open_after: bool = False) -> str:
    """
    Generate a professional multi-page invoice PDF using Platypus.
    - invoice_no: invoice identifier used to fetch invoice from DB.
    - open_after: if True, open the file with the system default PDF viewer.
    Returns absolute path to the generated PDF.
    """
    if not invoice_no:
        raise ValueError("invoice_no is required")

    header_row, items_rows = fetch_invoice(invoice_no)
    if not header_row:
        raise ValueError(f"Invoice '{invoice_no}' not found")

    # Standardized keys for header & items (adapt if your schema differs)
    header_keys = [
        "id", "invoice_no", "invoice_date", "customer_id", "bill_to", "ship_to", "lpo_no",
        "discount", "total_amount", "vat_amount", "net_total", "created_at", "updated_at",
        "balance", "paid_amount", "status", "salesman_id"
    ]
    item_keys = [
        "serial_no", "item_code", "item_name", "uom", "per_box_qty",
        "quantity", "rate", "sub_total", "vat_percentage", "vat_amount", "net_amount"
    ]

    header = _normalize_row(header_row, header_keys)
    items = [_normalize_row(it, item_keys) for it in (items_rows or [])]

    # company profile
    company_row = get_company_profile()
    if hasattr(company_row, "get"):
        company = company_row
    else:
        # map tuple to fields
        comp_keys = [
            "id", "company_name", "trn_no", "address_line1", "address_line2",
            "city", "state", "country", "phone1", "phone2", "email", "website",
            "bank_name", "account_name", "account_number", "iban", "swift_code", "logo_path"
        ]
        company = {}
        for i, k in enumerate(comp_keys):
            try:
                company[k] = company_row[i]
            except Exception:
                company[k] = None

    company_name = company.get("company_name") or "COMPANY NAME"
    address_lines = []
    for k in ("address_line1", "address_line2", "city", "state", "country"):
        v = company.get(k)
        if v:
            address_lines.append(str(v))
    phone = company.get("phone1") or company.get("phone2") or ""
    email = company.get("email") or ""
    trn_no = company.get("trn_no") or ""
    bank_name = company.get("bank_name") or ""
    account_name = company.get("account_name") or ""
    account_number = company.get("account_number") or ""
    iban = company.get("iban") or ""
    swift = company.get("swift_code") or ""
    logo_path = _ensure_logo_path(company.get("logo_path"))

    # document filename and path
    safe_invoice_no = "".join(ch for ch in str(
        invoice_no) if ch.isalnum() or ch in "-_.")
    out_filename = f"Invoice_{safe_invoice_no}.pdf"
    out_path = os.path.abspath(out_filename)

    # page / style setup
    PAGE_SIZE = A4
    PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
    margin = 14 * mm

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 8
    bold = ParagraphStyle("bold", parent=normal,
                          fontName="Helvetica-Bold", fontSize=9)
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)
    centered = ParagraphStyle("centered", parent=normal, alignment=TA_CENTER)
    small = ParagraphStyle("small", parent=normal, fontSize=7)

    # Header callback (drawn on each page)
    def header_canvas(c: canvas.Canvas, doc):
        c.saveState()
        top_y = PAGE_HEIGHT - margin

        # logo left
        if logo_path:
            try:
                logo_w = 30 * mm
                logo_h = 30 * mm
                c.drawImage(logo_path, margin, top_y - logo_h, width=logo_w,
                            height=logo_h, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass

        # invoice meta box (right)
        box_w = 110 * mm
        box_h = 48
        box_x = PAGE_WIDTH - margin - box_w
        box_y = top_y - box_h + 6
        c.setLineWidth(0.6)
        c.rect(box_x, box_y, box_w, box_h)

        inv_date = header.get("invoice_date")
        if isinstance(inv_date, datetime):
            date_str = inv_date.strftime("%Y-%m-%d")
        else:
            date_str = str(inv_date or "")

        c.setFont("Helvetica", 8)
        c.drawString(box_x + 6, box_y + box_h - 12, "Date:")
        c.drawString(box_x + 6, box_y + box_h - 26, "Doc No.:")
        c.drawString(box_x + 6, box_y + box_h - 40, "LPO No.:")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(box_x + 56, box_y + box_h - 12, date_str)
        c.drawString(box_x + 56, box_y + box_h - 26,
                     str(header.get("invoice_no") or invoice_no))
        c.drawString(box_x + 56, box_y + box_h - 40,
                     str(header.get("lpo_no") or ""))

        # company text to the right of logo (top-left area)
        c.setFont("Helvetica-Bold", 12)
        comp_x = margin + 34 * mm
        comp_y = top_y - 6
        c.drawString(comp_x, comp_y, company_name)
        c.setFont("Helvetica", 8)
        comp_y -= 10
        for line in address_lines[:3]:
            c.drawString(comp_x, comp_y, line)
            comp_y -= 9
        if phone:
            c.drawString(comp_x, comp_y, f"Phone: {phone}")
            comp_y -= 9
        if email:
            c.drawString(comp_x, comp_y, f"Email: {email}")

        # centered title
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(PAGE_WIDTH / 2.0, top_y - 42, "TAX INVOICE")

        c.restoreState()

    # Footer callback (bank details left, page no handled by NumberedCanvas)
    def footer_canvas(c: canvas.Canvas, doc):
        c.saveState()
        footer_y = margin + 18
        # Bank details left
        bank_x = margin
        c.setFont("Helvetica-Bold", 9)
        c.drawString(bank_x, footer_y + 34, "BANK DETAILS:")
        c.setFont("Helvetica", 8)
        c.drawString(bank_x, footer_y + 22,
                     f"ACCOUNT NAME: {account_name or ''}")
        c.drawString(bank_x, footer_y + 10, f"ACCOUNT IBAN: {iban or ''}")
        c.drawString(bank_x, footer_y - 2,
                     f"ACCOUNT No.: {account_number or ''}")
        c.drawString(bank_x, footer_y - 14, f"BANK NAME: {bank_name or ''}")
        c.drawString(bank_x, footer_y - 26, f"SWIFTCODE: {swift or ''}")
        c.restoreState()
        # Page number will be drawn by NumberedCanvas.save()

    # Doc setup with page template (header & footer will be invoked)
    top_margin_space = 90  # space left for header area
    bottom_margin_space = 70
    doc = SimpleDocTemplate(
        out_path,
        pagesize=PAGE_SIZE,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin + top_margin_space,
        bottomMargin=margin + bottom_margin_space
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="normal")
    template = PageTemplate(id="invoice", frames=[frame], onPage=header_canvas)
    doc.addPageTemplates([template])

    flow: List = []

    # Bill To / Ship To / Salesman block
    bill_text = Paragraph(
        f"<b>Bill to:</b><br/>{(header.get('bill_to') or '-').replace('\\n', '<br/>')}", normal)
    ship_text = Paragraph(
        f"<b>Ship to:</b><br/>{(header.get('ship_to') or '-').replace('\\n', '<br/>')}", normal)
    salesman = header.get("salesman_id") or ""
    salesman_p = Paragraph(f"<b>Salesman:</b><br/>{str(salesman)}", normal)
    bs_table = Table([[bill_text, ship_text, salesman_p]], colWidths=[
                     doc.width*0.45, doc.width*0.45, doc.width*0.10])
    bs_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(bs_table)
    flow.append(Spacer(1, 8))

    # Items table: columns distributed proportionally
    cols = ["Sl No.", "Item code", "Item Name", "Unit",
            "Qty.", "Rate", "Sub total", "Vat %", "Net amount"]
    data = [cols]
    # Set a simple char limit for item_name to avoid overflowing—long descriptions will wrap within Paragraph

    def _trim_text(text, limit=240):
        s = str(text or "")
        if len(s) <= limit:
            return s
        return s[:limit-3] + "..."

    for idx, it in enumerate(items or [], start=1):
        qty = _safe_float(it.get("quantity"))
        rate = _safe_float(it.get("rate"))
        sub_total = _safe_float(it.get("sub_total")) if it.get(
            "sub_total") is not None else qty * rate
        vat_pct = _safe_float(it.get("vat_percentage") or 0.0)
        vat_amt = _safe_float(it.get("vat_amount") or (
            sub_total * (vat_pct / 100.0)))
        net_amount = _safe_float(it.get("net_amount") or (sub_total + vat_amt))
        row = [
            str(idx),
            str(it.get("item_code") or ""),
            Paragraph(_trim_text(it.get("item_name") or ""), normal),
            str(it.get("uom") or ""),
            _format_currency(qty),
            _format_currency(rate),
            _format_currency(sub_total),
            f"{vat_pct:.2f}",
            _format_currency(net_amount)
        ]
        data.append(row)

    # if no items, add placeholder
    if len(data) == 1:
        data.append(["", "", Paragraph("-", normal), "",
                    "0.00", "0.00", "0.00", "0.00", "0.00"])

    # column widths relative
    col_widths = [
        doc.width * 0.06,  # Sl No.
        doc.width * 0.10,  # Item code
        doc.width * 0.34,  # Item Name
        doc.width * 0.08,  # Unit
        doc.width * 0.08,  # Qty
        doc.width * 0.10,  # Rate
        doc.width * 0.10,  # Sub total
        doc.width * 0.06,  # Vat %
        doc.width * 0.10   # Net amount
    ]
    items_table = Table(data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7e7e7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("ALIGN", (4, 1), (8, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (2, 1), (2, -1), 6),
        ("RIGHTPADDING", (2, 1), (2, -1), 6),
    ]))
    flow.append(items_table)
    flow.append(Spacer(1, 12))

    # Totals & Tax details computed for last page
    subtotal = sum(_safe_float(it.get("sub_total") or (_safe_float(
        it.get("quantity")) * _safe_float(it.get("rate")))) for it in items)
    total_vat_amount = sum(_safe_float(it.get("vat_amount") or 0)
                           for it in items)
    discount = _safe_float(header.get("discount") or 0.0)
    net_total = _safe_float(header.get("net_total") or (
        subtotal + total_vat_amount - discount))
    paid_amount = _safe_float(header.get("paid_amount") or 0.0)
    balance = _safe_float(header.get("balance") or (net_total - paid_amount))

    # Tax details left table
    tax_table = Table([
        [Paragraph("<b>Tax details</b>", bold), ""],
        ["Taxable Amount", _format_currency(subtotal)],
        ["VAT Rate %",
            f"{(items[0].get('vat_percentage') if items else 0) or 0}%"],
        ["Total VAT", _format_currency(total_vat_amount)]
    ], colWidths=[doc.width * 0.6 * 0.6, doc.width * 0.6 * 0.4])
    tax_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    # Totals right table
    totals_table = Table([
        ["Total", _format_currency(subtotal)],
        ["Discount", _format_currency(discount)],
        ["Taxable", _format_currency(subtotal - discount)],
        ["VAT 5%", _format_currency(total_vat_amount)],
        [Paragraph("<b>Net Value</b>", bold),
         Paragraph(f"<b>{_format_currency(net_total)}</b>", right)]
    ], colWidths=[doc.width * 0.25, doc.width * 0.25])
    totals_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f7f7f7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    combined = Table([[tax_table, totals_table]], colWidths=[
                     doc.width * 0.6, doc.width * 0.4])
    combined.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    # Place combined totals near bottom: ensure it's placed after items; Platypus will flow pages automatically.
    flow.append(Spacer(1, 6))
    flow.append(combined)
    flow.append(Spacer(1, 8))

    # Amount in words and bank lines
    try:
        words = num2words(net_total, lang="en_IN").title() + " Only"
    except Exception:
        words = f"{_format_currency(net_total)}"
    flow.append(Paragraph(f"<b>Amount (in words):</b> {words}", normal))
    flow.append(Spacer(1, 6))

    bank_lines = [
        f"ACCOUNT NAME: {account_name or ''}",
        f"ACCOUNT IBAN: {iban or ''}",
        f"ACCOUNT No.: {account_number or ''}",
        f"BANK NAME: {bank_name or ''}",
        f"SWIFTCODE: {swift or ''}"
    ]
    for bl in bank_lines:
        flow.append(Paragraph(bl, small))
    flow.append(Spacer(1, 6))

    # Build PDF using NumberedCanvas so page count is available for "Page X of Y"
    doc.build(flow, canvasmaker=NumberedCanvas)

    # after build optionally open
    if open_after:
        try:
            if os.name == "nt":
                os.startfile(out_path)
            else:
                subprocess.Popen(["xdg-open", out_path])
        except Exception as e:
            # return path even if open fails; caller can handle
            raise RuntimeError(f"PDF generated but failed to open viewer: {e}")

    return out_path


if __name__ == "__main__":
    # simple test
    from utils.pdf_helper import generate_invoice_pdf
    pdf_path = generate_invoice_pdf("STSIV25-06761", open_after=True)
    print(f"Generated: {pdf_path}")
