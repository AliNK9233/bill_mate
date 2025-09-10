from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.pdfgen import canvas

# -------- Page x of y canvas --------


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        # Footer: Page x of n
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.black)
        w, h = A4
        self.drawRightString(
            # right-aligned
            w - 2*cm, 1.5*cm, f"Page {self._pageNumber} of {page_count}")

# -------- Header / Footer callbacks --------


def draw_header(c, doc):
    c.saveState()
    page_w, page_h = A4
    # Centered title
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(page_w/2.0, doc.height +
                        doc.topMargin + 0.6*cm, "Delivery Note")
    # Company block at left, logo at right (adjust if needed)
    y = doc.height + doc.topMargin + 0.2*cm
    c.setFont("Helvetica", 9)
    c.drawString(doc.leftMargin, y,
                 "BillMate Pvt Ltd, 123 MG Road, Bengaluru 560001")
    c.drawString(doc.leftMargin, y-11,
                 "GSTIN: 29ABCDE1234F1Z5 | Email: hello@billmate.example | +91-90000-00000")
    # Optional logo at right
    try:
        from reportlab.lib.utils import ImageReader
        logo = ImageReader("billmate_logo.ico")
        c.drawImage(logo, page_w - doc.rightMargin - 2.0*cm, y-6, width=1.8 *
                    cm, height=1.8*cm, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    c.restoreState()


def draw_footer(c, doc):
    # Page x of n is drawn by NumberedCanvas.save()
    pass


# -------- Document setup --------
doc = BaseDocTemplate(
    "delivery_note.pdf",
    pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2*cm, bottomMargin=2*cm
)

header_h = 1.4*cm
footer_h = 1.2*cm
frame = Frame(
    doc.leftMargin,
    doc.bottomMargin + footer_h,
    doc.width,
    doc.height - header_h - footer_h,
    id="body"
)
doc.addPageTemplates(PageTemplate(id="main", frames=[
                     frame], onPage=draw_header, onPageEnd=draw_footer))

# -------- Styles --------
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="Label", parent=styles["Normal"], textColor=colors.grey, fontSize=9))
styles.add(ParagraphStyle(name="Value", parent=styles["Normal"], fontSize=10))
styles.add(ParagraphStyle(
    name="HCell", parent=styles["Normal"], fontSize=9, textColor=colors.white))
styles.add(ParagraphStyle(name="SectionTitle",
           parent=styles["Heading3"], spaceAfter=6))

story = []

# -------- Metadata row (Invoice No., Sales Person, Created By, Bill To) --------
meta_left = Table([
    [Paragraph("<b>Invoice No.</b>", styles["Label"]),
     Paragraph("INV-2025-0456", styles["Value"])],
    [Paragraph("<b>Sales Person</b>", styles["Label"]),
     Paragraph("Rahul Sharma", styles["Value"])],
], colWidths=[3.2*cm, 6.0*cm])
meta_left.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
]))

meta_right = Table([
    [Paragraph("<b>Created By</b>", styles["Label"]),
     Paragraph("A. Kumar", styles["Value"])],
    [Paragraph("<b>Bill To</b>", styles["Label"]), Paragraph(
        "ACME Industries, 45 Industrial Estate, Chennai 600032", styles["Value"])],
], colWidths=[3.2*cm, 6.0*cm])
meta_right.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
]))

meta_row = Table([[meta_left, meta_right]], colWidths=[9.2*cm, 9.2*cm])
meta_row.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(meta_row)
story.append(Spacer(1, 0.3*cm))

# -------- Items table --------
items_header = ["Sl No.", "Item Code", "Item Name", "Unit", "Qty", "Remarks"]
data = [items_header]
for i in range(1, 36):
    data.append([
        i,
        f"ITM{i:04d}",
        f"Sample item {i}",
        "Nos",
        f"{(i % 5)+1}",
        "—"
    ])

col_widths = [1.2*cm, 3.0*cm, 8.0*cm, 2.0*cm, 2.0*cm, 3.0*cm]
tbl = Table(data, colWidths=col_widths, repeatRows=1)
tbl_style = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E88E5")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("ALIGN", (0, 0), (0, -1), "RIGHT"),          # Sl No. right
    ("ALIGN", (3, 1), (4, -1), "RIGHT"),          # Unit/Qty align
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D1DD")),
    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#7F8C8D")),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
])
tbl.setStyle(tbl_style)
story.append(tbl)
story.append(Spacer(1, 0.6*cm))

# -------- Signatures row (for hard copy) --------
sig_labels = [
    Paragraph("<b>Created By</b>", styles["Label"]),
    Paragraph("<b>Approved By</b>", styles["Label"]),
    Paragraph("<b>Received By</b>", styles["Label"]),
]
sig_boxes = []
for label in sig_labels:
    box = Table([
        [label],
        [Spacer(1, 2.2*cm)],  # signature space
        [Paragraph("Name & Sign", styles["Value"])]
    ], colWidths=[6.1*cm], rowHeights=[None, 2.2*cm, None])
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7F8C8D")),
        ("ALIGN", (0, 2), (-1, 2), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    sig_boxes.append(box)

sigs = Table([sig_boxes], colWidths=[6.1*cm, 6.1*cm, 6.1*cm])
sigs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
story.append(sigs)

# -------- Build --------
doc.build(story, canvasmaker=NumberedCanvas)
