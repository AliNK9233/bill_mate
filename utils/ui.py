from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image
)

# ----- Header & Footer callbacks -----
def draw_header(canvas, doc):
    canvas.saveState()
    # Super header (top-right, outside main body frame)
    page_width, page_height = A4
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.25))  # faded grey/black
    inset = 20  # avoid clipping at the physical edge
    canvas.drawRightString(page_width - inset, page_height - inset, "ORIGINAL COPY")
    # Centered title inside header area (above body frame)
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawCentredString(page_width / 2.0, doc.height + doc.topMargin + 0.5*cm, "Sample Report")
    canvas.restoreState()

def draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    y = doc.bottomMargin - 0.4*cm
    canvas.drawString(doc.leftMargin, y, "Confidential • Company Name")
    canvas.drawRightString(doc.leftMargin + doc.width, y, "Generated with ReportLab")
    canvas.restoreState()

# ----- Document & Frames -----
doc = BaseDocTemplate(
    "demo_sections_tables.pdf",
    pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2*cm, bottomMargin=2*cm
)

# Reserve header/footer space by reducing the body frame height
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

# ----- Styles -----
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="SmallLabel", parent=styles["Normal"], textColor=colors.grey, fontSize=9, spaceAfter=2))
styles.add(ParagraphStyle(name="Company", parent=styles["Heading2"], fontSize=14, spaceAfter=2))
styles.add(ParagraphStyle(name="MetaLabel", parent=styles["Normal"], fontSize=9, textColor=colors.grey))
styles.add(ParagraphStyle(name="MetaValue", parent=styles["Normal"], fontSize=10))
styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading3"], spaceAfter=6))

# ----- Story (Body content) -----
story = []

# 1) Header row: [logo] [company address block] [invoice meta]
# Note: Ensure Pillow is installed for image support; adjust logo path/size as needed.
logo = Image("billmate_logo.ico", width=3.5*cm, height=3.5*cm)
company_block = [
    [Paragraph("BillMate Pvt Ltd", styles["Company"])],
    [Paragraph("123 MG Road", styles["SmallLabel"])],
    [Paragraph("Bengaluru, Karnataka 560001", styles["SmallLabel"])],
    [Paragraph("GSTIN: 29ABCDE1234F1Z5", styles["SmallLabel"])],
    [Paragraph("Email: hello@billmate.example | +91-90000-00000", styles["SmallLabel"])],
]

invoice_meta = [
    [Paragraph("<b>Invoice No.</b>", styles["MetaLabel"]), Paragraph("INV-2025-0012", styles["MetaValue"])],
    [Paragraph("<b>Invoice Date</b>", styles["MetaLabel"]), Paragraph("10-Sep-2025", styles["MetaValue"])],
    [Paragraph("<b>LPO No.</b>", styles["MetaLabel"]), Paragraph("LPO-7788", styles["MetaValue"])],
]
meta_table = Table(invoice_meta, colWidths=[3.0*cm, 4.2*cm], hAlign="RIGHT")
meta_table.setStyle(TableStyle([
    ("ALIGN", (1,0), (1,-1), "RIGHT"),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 0),
    ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ("BOTTOMPADDING", (0,0), (-1,-1), 1),
]))

company_inner = Table(company_block, colWidths=[None])
company_inner.setStyle(TableStyle([
    ("LEFTPADDING", (0,0), (-1,-1), 0),
    ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
]))

header_row = Table(
    data=[[logo, company_inner, meta_table]],
    colWidths=[4.2*cm, 10.0*cm, 4.8*cm]  # adjust to fit your frame width
)
header_row.setStyle(TableStyle([
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ALIGN", (0,0), (0,0), "LEFT"),
    ("ALIGN", (1,0), (1,0), "LEFT"),
    ("ALIGN", (2,0), (2,0), "RIGHT"),
    ("LEFTPADDING", (0,0), (-1,-1), 4),
    ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ("TOPPADDING", (0,0), (-1,-1), 2),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    # Debug borders while learning:
    #("BOX", (0,0), (-1,-1), 0.5, colors.red),
    #("BOX", (0,0), (0,0), 0.3, colors.green),
    #("BOX", (1,0), (1,0), 0.3, colors.blue),
    #("BOX", (2,0), (2,0), 0.3, colors.orange),
]))

# 2) Second row: Bill To | Ship To | Extra
bill_to_block = [
    [Paragraph("<b>Bill To</b>", styles["MetaLabel"])],
    [Paragraph("ACME Industries", styles["MetaValue"])],
    [Paragraph("45 Industrial Estate", styles["MetaValue"])],
    [Paragraph("Chennai, TN 600032", styles["MetaValue"])],
    [Paragraph("GSTIN: 33ACME1234Z5", styles["MetaValue"])],
]
ship_to_block = [
    [Paragraph("<b>Ship To</b>", styles["MetaLabel"])],
    [Paragraph("ACME Warehouse", styles["MetaValue"])],
    [Paragraph("Plot 22, SIPCOT", styles["MetaValue"])],
    [Paragraph("Chennai, TN 600058", styles["MetaValue"])],
    [Paragraph("Contact: +91-98888-88888", styles["MetaValue"])],
]
extra_block = [
    [Paragraph("<b>Remarks</b>", styles["MetaLabel"])],
    [Paragraph("Deliver between 10am–5pm", styles["MetaValue"])],
    [Paragraph("Reference: RFQ-2025-04", styles["MetaValue"])],
    [Paragraph("Payment: 30 days", styles["MetaValue"])],
    [Paragraph("Mode: NEFT", styles["MetaValue"])],
]

bill_to_tbl = Table(bill_to_block, colWidths=[None])
ship_to_tbl = Table(ship_to_block, colWidths=[None])
extra_tbl = Table(extra_block, colWidths=[None])
for t in (bill_to_tbl, ship_to_tbl, extra_tbl):
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 2),
        ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 1),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))

second_row = Table(
    data=[[bill_to_tbl, ship_to_tbl, extra_tbl]],
    colWidths=[6.0*cm, 6.0*cm, 6.0*cm]  # three equal columns
)
second_row.setStyle(TableStyle([
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 4),
    ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ("TOPPADDING", (0,0), (-1,-1), 4),
    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    # Debug borders while learning:
    # ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
]))

# Items section title
story.append(header_row)
story.append(Spacer(1, 0.25*cm))
story.append(second_row)
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph("Items", styles["SectionTitle"]))

# Items table
table_data = [
    ["Sl No.", "Part No", "Description", "Qty", "Rate", "Tax %", "Tax", "Amount"],
]
for i in range(1, 36):
    sl_no = i
    part = f"P{i:03d}"
    desc = f"Widget {i} — multi-use component"
    qty = i % 5 + 1
    rate = 125.0 + i
    tax = 5
    tax_amount = qty * rate * (tax/100.0)
    amount = qty * rate * (1 + tax/100.0)
    table_data.append([sl_no, part, desc, qty, f"{rate:,.2f}", f"{tax}%", f"{tax_amount:,.2f}", f"{amount:,.2f}"])

# Column widths tuned for A4 with ~4 cm total margins (~17 cm frame width)
col_widths = [1.0*cm, 2.2*cm, 6.0*cm, 1.0*cm, 2.0*cm, 1.8*cm, 2.0*cm, 2.0*cm]

tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
tbl_style = TableStyle([
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F0F3F7")),
    ("TEXTCOLOR", (0,0), (-1,0), colors.black),
    ("ALIGN", (3,1), (-1,-1), "RIGHT"),    # numeric columns right-aligned (Qty..Amount)
    ("ALIGN", (2,0), (2,-1), "LEFT"),      # description left
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LINEBELOW", (0,0), (-1,0), 0.6, colors.black),
    ("INNERGRID", (0,1), (-1,-1), 0.25, colors.HexColor("#C7D1DD")),
    ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#7F8C8D")),
    ("LEFTPADDING", (0,0), (-1,-1), 4),
    ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ("TOPPADDING", (0,0), (-1,-1), 3),
    ("BOTTOMPADDING", (0,0), (-1,-1), 3),
])
tbl.setStyle(tbl_style)
story.append(tbl)
story.append(Spacer(1, 0.5*cm))

# Totals block
# ---- Row 1: Left = Tax Details, Right = Totals summary ----
tax_details = [
    [Paragraph("<b>Tax Details</b>", styles["MetaLabel"])],
    [Paragraph("Taxable Amount: 7,095.57", styles["MetaValue"])],
    [Paragraph("VAT Rate: 5%", styles["MetaValue"])],
    [Paragraph("Total VAT: 354.83", styles["MetaValue"])],
]
tax_tbl = Table(tax_details, colWidths=[9.0*cm])
tax_tbl.setStyle(TableStyle([
    ("LEFTPADDING", (0,0), (-1,-1), 2),
    ("RIGHTPADDING", (0,0), (-1,-1), 2),
    ("TOPPADDING", (0,0), (-1,-1), 1),
    ("BOTTOMPADDING", (0,0), (-1,-1), 1),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
]))

totals_summary = [
    [Paragraph("<b>Total</b>", styles["MetaLabel"]), Paragraph("7,095.57", styles["MetaValue"])],
    [Paragraph("<b>Discount</b>", styles["MetaLabel"]), Paragraph("0.00", styles["MetaValue"])],
    [Paragraph("<b>Taxable</b>", styles["MetaLabel"]), Paragraph("7,095.57", styles["MetaValue"])],
    [Paragraph("<b>VAT 5%</b>", styles["MetaLabel"]), Paragraph("354.83", styles["MetaValue"])],
    [Paragraph("<b>Net with Tax</b>", styles["MetaLabel"]), Paragraph("7,450.40", styles["MetaValue"])],
]
totals_tbl = Table(totals_summary, colWidths=[3.5*cm, 4.0*cm], hAlign="RIGHT")
totals_tbl.setStyle(TableStyle([
    ("ALIGN", (1,0), (1,-1), "RIGHT"),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 2),
    ("RIGHTPADDING", (0,0), (-1,-1), 2),
    ("TOPPADDING", (0,0), (-1,-1), 1),
    ("BOTTOMPADDING", (0,0), (-1,-1), 1),
]))

row1 = Table([[tax_tbl, totals_tbl]], colWidths=[9.0*cm, 8.0*cm])
row1.setStyle(TableStyle([
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    # Debug outline while learning:
    # ("BOX", (0,0), (-1,-1), 0.25, colors.grey),
]))

story.append(Spacer(1, 0.3*cm))
story.append(row1)
story.append(Spacer(1, 0.3*cm))

# ---- Row 2: Left = Bank Details, Right = Seal image (if available) ----
bank_details = [
    [Paragraph("<b>Bank Details</b>", styles["MetaLabel"])],
    [Paragraph("Bank: State Bank of India", styles["MetaValue"])],
    [Paragraph("A/C No: 123456789012", styles["MetaValue"])],
    [Paragraph("IFSC: SBIN0001234", styles["MetaValue"])],
    [Paragraph("Branch: Andheri West, Mumbai", styles["MetaValue"])],
]
bank_tbl = Table(bank_details, colWidths=[9.0*cm])
bank_tbl.setStyle(TableStyle([
    ("LEFTPADDING", (0,0), (-1,-1), 2),
    ("RIGHTPADDING", (0,0), (-1,-1), 2),
    ("TOPPADDING", (0,0), (-1,-1), 1),
    ("BOTTOMPADDING", (0,0), (-1,-1), 1),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
]))

# Try to load seal image; if missing, show a placeholder box with label
def seal_flowable():
    try:
        img = Image("seal.png", width=3.5*cm, height=3.5*cm)
        img.hAlign = "RIGHT"
        return img
    except Exception:
        ph = Table([[Paragraph("Seal", styles["MetaLabel"])]], colWidths=[3.5*cm], rowHeights=[3.5*cm], hAlign="RIGHT")
        ph.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.6, colors.lightgrey),
            ("ALIGN", (0,0), (-1,-1), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))
        return ph

seal = seal_flowable()
row2 = Table([[bank_tbl, seal]], colWidths=[9.0*cm, 8.0*cm])
row2.setStyle(TableStyle([
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    # ("BOX", (0,0), (-1,-1), 0.25, colors.grey),
]))

story.append(row2)

# Build the document
doc.build(story)
