# utils/delivery_pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle
)
from reportlab.pdfgen import canvas
import webbrowser
import os
from typing import List, Dict, Any, Optional

# ---------------- NumberedCanvas with last-page signature drawing ----------------


class NumberedCanvas(canvas.Canvas):
    """
    Canvas that keeps page states and draws "Page x of y".
    If `NumberedCanvas.signature_data` is set (a dict), it will draw the signature
    area only on the last page (during the saved-state replay in save()).
    """
    signature_data: Optional[Dict[str, Any]] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            # draw page number and possibly last-page signatures
            self.draw_page_number(page_count)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        # Footer: Page x of n (right aligned)
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.black)
        w, h = A4
        right_x = w - 2*cm
        self.drawRightString(
            right_x, 1.4*cm, f"Page {self._pageNumber} of {page_count}")

        # If on last page and signature_data is provided, draw signature labels/space
        if self._pageNumber == page_count and isinstance(NumberedCanvas.signature_data, dict):
            sd = NumberedCanvas.signature_data
            try:
                left_margin = float(sd.get("left_margin", 2*cm))
                right_margin = float(sd.get("right_margin", 2*cm))
                bottom_margin = float(sd.get("bottom_margin", 2*cm))
                footer_h = float(sd.get("footer_h", 3.2*cm))
                labels = sd.get(
                    "labels", ["Created By", "Approved By", "Received By"])
                created_by_value = sd.get("created_by", "")
                # compute column widths and positions
                usable_width = w - left_margin - right_margin
                col_w = usable_width / 3.0
                # y coordinate where label will appear -- a little above bottom of footer
                y_label = bottom_margin + 0.9*cm
                # space reserved above label for signing (we won't draw box/line as requested)
                # Draw labels left aligned inside each column
                self.setFont("Helvetica-Bold", 9)
                self.setFillColor(colors.black)
                for i, lab in enumerate(labels[:3]):
                    x_center = left_margin + (i + 0.5) * col_w
                    # draw label text centered above the blank signature space
                    self.drawCentredString(x_center, y_label + 1.2*cm, lab)
                    # If created_by_value is provided, put it under the left label (optional)
                    if i == 0 and created_by_value:
                        self.setFont("Helvetica", 8)
                        # place created_by name under the signature space (closer to bottom)
                        self.drawCentredString(
                            x_center, y_label - 0.1*cm, str(created_by_value))
                        self.setFont("Helvetica-Bold", 9)
            except Exception:
                # fail silently — signatures are optional
                pass

# ---------------- Helper: normalize company_profile ----------------


def _company_profile_to_strings(cp: Optional[Any]) -> Dict[str, str]:
    out = {
        "company_name": "",
        "trn_no": "",
        "address_lines": "",
        "phone": "",
        "email": "",
        "website": "",
        "logo_path": ""
    }
    if not cp:
        return out
    try:
        if isinstance(cp, dict):
            out["company_name"] = cp.get("company_name") or ""
            out["trn_no"] = cp.get("trn_no") or ""
            parts = [cp.get("address_line1") or "", cp.get("address_line2") or "", cp.get(
                "city") or "", cp.get("state") or cp.get("country") or ""]
            out["address_lines"] = ", ".join([p for p in parts if p])
            out["phone"] = cp.get("phone1") or cp.get("phone2") or ""
            out["email"] = cp.get("email") or ""
            out["website"] = cp.get("website") or ""
            out["logo_path"] = cp.get("logo_path") or ""
        elif isinstance(cp, (list, tuple)):
            try:
                out["company_name"] = str(cp[1]) if len(
                    cp) > 1 and cp[1] else ""
                out["trn_no"] = str(cp[2]) if len(cp) > 2 and cp[2] else ""
                part1 = str(cp[3]) if len(cp) > 3 and cp[3] else ""
                part2 = str(cp[4]) if len(cp) > 4 and cp[4] else ""
                city = str(cp[5]) if len(cp) > 5 and cp[5] else ""
                state = str(cp[6]) if len(cp) > 6 and cp[6] else ""
                country = str(cp[7]) if len(cp) > 7 and cp[7] else ""
                out["address_lines"] = ", ".join(
                    [p for p in (part1, part2, city, state, country) if p])
                out["phone"] = str(cp[8]) if len(cp) > 8 and cp[8] else ""
                out["email"] = str(cp[10]) if len(cp) > 10 and cp[10] else ""
                out["website"] = str(cp[11]) if len(cp) > 11 and cp[11] else ""
                out["logo_path"] = str(cp[17]) if len(
                    cp) > 17 and cp[17] else ""
            except Exception:
                pass
    except Exception:
        pass
    return out

# ---------------- Main PDF generator ----------------


def generate_delivery_note_pdf(output_path: str,
                               header: Dict[str, Any],
                               items: List[Dict[str, Any]],
                               company_profile: Optional[Any] = None,
                               open_after: bool = False) -> str:
    """
    Generate a delivery note PDF similar to the provided style.

    header: dict supporting keys like invoice_no, sales_person, created_by, bill_to, date
    items: list of dicts {sl_no, item_code, item_name, unit, qty, remarks (optional)}
    company_profile: tuple/row/dict from models.company_model.get_company_profile()
    open_after: try to open the file after creation
    """
    # defensively normalize header keys (try multiple possible names)
    invoice_no = ""
    sales_person = ""
    created_by = ""
    bill_to = ""
    date_str = ""
    if header:
        try:
            if hasattr(header, "get"):
                invoice_no = header.get("invoice_no") or header.get(
                    "inv_no") or header.get("invoice_no_display") or ""
                sales_person = header.get("sales_person") or header.get(
                    "salesperson") or header.get("salesman_name") or ""
                created_by = header.get(
                    "created_by") or header.get("prepared_by") or ""
                bill_to = header.get("bill_to") or header.get(
                    "bill_to_display") or header.get("customer_name") or ""
                date_str = header.get("date") or header.get(
                    "invoice_date") or ""
        except Exception:
            pass
        if not invoice_no and isinstance(header, (list, tuple)):
            try:
                invoice_no = header[1] if len(header) > 1 else ""
            except Exception:
                invoice_no = ""
    # ensure strings
    invoice_no = str(invoice_no or "")
    sales_person = str(sales_person or "")
    created_by = str(created_by or "")
    bill_to = str(bill_to or "")
    date_str = str(date_str or "")

    # company strings
    cp = _company_profile_to_strings(company_profile)

    # doc setup: reserve footer_h height (we will draw signatures only on final page)
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    header_h = 1.6*cm
    footer_h = 3.2*cm  # reserve enough space for signatures
    body_frame = Frame(
        doc.leftMargin,
        doc.bottomMargin + footer_h,
        doc.width,
        doc.height - header_h - footer_h,
        id="body"
    )
    doc.addPageTemplates(PageTemplate(id="main", frames=[
                         body_frame], onPage=_make_header_drawer(cp)))

    # styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Label", parent=styles["Normal"], textColor=colors.grey, fontSize=9))
    styles.add(ParagraphStyle(
        name="Value", parent=styles["Normal"], fontSize=10))
    styles.add(ParagraphStyle(
        name="HCell", parent=styles["Normal"], fontSize=9, textColor=colors.white))
    styles.add(ParagraphStyle(name="SectionTitle",
               parent=styles["Heading3"], spaceAfter=6))

    story = []

    # Company block (top of doc body)
    try:
        left_parts = []
        if cp.get("company_name"):
            left_parts.append(
                Paragraph(f"<b>{cp['company_name']}</b>", styles["Value"]))
        if cp.get("address_lines"):
            left_parts.append(Paragraph(cp['address_lines'], styles["Label"]))
        contact_line = " | ".join([p for p in (
            cp.get("trn_no") or "", cp.get("phone") or "", cp.get("email") or "") if p])
        if contact_line:
            left_parts.append(Paragraph(contact_line, styles["Label"]))
        comp_table = Table([[left_parts]], colWidths=[doc.width])
        comp_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(comp_table)
    except Exception:
        pass

    story.append(Spacer(1, 0.2*cm))

    # meta row (left/right)
    meta_left = Table([
        [Paragraph("<b>Invoice No.</b>", styles["Label"]),
         Paragraph(invoice_no or "-", styles["Value"])],
        [Paragraph("<b>Sales Person</b>", styles["Label"]),
         Paragraph(sales_person or "-", styles["Value"])]
    ], colWidths=[3.2*cm, 6.0*cm])
    meta_left.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))

    meta_right = Table([
        [Paragraph("<b>Created By</b>", styles["Label"]),
         Paragraph(created_by or "-", styles["Value"])],
        [Paragraph("<b>Bill To</b>", styles["Label"]),
         Paragraph(bill_to or "-", styles["Value"])]
    ], colWidths=[3.2*cm, 6.0*cm])
    meta_right.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))

    meta_row = Table([[meta_left, meta_right]], colWidths=[
                     doc.width/2.0, doc.width/2.0])
    meta_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_row)
    story.append(Spacer(1, 0.3*cm))

    # items table
    items_header = ["Sl No.", "Item Code",
                    "Item Name", "Unit", "Qty", "Remarks"]
    data = [items_header]
    for it in items:
        sl = it.get("sl_no") if it.get("sl_no") is not None else ""
        code = it.get("item_code") or ""
        name = it.get("item_name") or ""
        unit = it.get("unit") or it.get("uom") or ""
        qty = it.get("qty") or ""
        remarks = it.get("remarks") or ""
        data.append([str(sl), str(code), str(name),
                    str(unit), str(qty), str(remarks)])

    col_widths = [1.2*cm, 3.0*cm, 8.0*cm, 2.0*cm, 2.0*cm, 3.0*cm]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E88E5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D1DD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    tbl.setStyle(tbl_style)
    story.append(tbl)

    # Add a small spacer so table doesn't butt to footer
    story.append(Spacer(1, 0.4*cm))

    # Before building, set signature data on NumberedCanvas so it can draw the signatures
    NumberedCanvas.signature_data = {
        "left_margin": doc.leftMargin,
        "right_margin": doc.rightMargin,
        "bottom_margin": doc.bottomMargin,
        "footer_h": footer_h,
        "labels": ["Created By", "Approved By", "Received By"],
        "created_by": created_by
    }

    # Build the document: NumberedCanvas.save will draw signatures on the last page only
    try:
        doc.build(story, canvasmaker=NumberedCanvas)
    except Exception as e:
        raise RuntimeError(f"Failed to build PDF: {e}")

    # optionally open
    if open_after:
        try:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")
        except Exception:
            pass

    return output_path

# ---------------- helper to make header drawer with company profile capture ----------------


def _make_header_drawer(cp: Dict[str, str]):
    """
    Returns a function draw_header(c, doc) which draws the title and optional logo,
    using the provided normalized company profile dict `cp`.
    """
    def _draw_header(c: canvas.Canvas, doc):
        c.saveState()
        page_w, page_h = A4
        # Title centered
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_w / 2.0, doc.height +
                            doc.topMargin + 0.6*cm, "Delivery Note")

        # Company info left (small)
        c.setFont("Helvetica", 9)
        x = doc.leftMargin
        y = doc.height + doc.topMargin + 0.2*cm
        try:
            if cp.get("company_name"):
                c.drawString(x, y, cp["company_name"])
                y -= 11
            if cp.get("address_lines"):
                c.setFont("Helvetica", 8.5)
                # wrap address if long; simplistic: draw as single line
                c.drawString(x, y, cp["address_lines"])
                y -= 11
            contact = " | ".join([p for p in (cp.get("trn_no") or "", cp.get(
                "phone") or "", cp.get("email") or "") if p])
            if contact:
                c.setFont("Helvetica", 8.5)
                c.drawString(x, y, contact)
        except Exception:
            pass

        # logo on the right if available (favor cp["logo_path"])
        try:
            logo_path = cp.get("logo_path") or "data/logos/billmate_logo.png"
            if logo_path and os.path.exists(logo_path):
                # draw scaled
                c.drawImage(logo_path, page_w - doc.rightMargin - 2.0*cm, doc.height + doc.topMargin - 0.3*cm,
                            width=1.8*cm, height=1.8*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

        c.restoreState()
    return _draw_header
