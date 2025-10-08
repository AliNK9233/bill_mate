import os
import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from models.invoice_model import get_invoice_details_by_no, get_invoice_items_by_no
from models.company_model import get_company_profile

# Helper class for "Page X of Y" numbering
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.drawRightString(A4[0] - 20 * mm, 15 * mm, f"Page {self._pageNumber} of {page_count}")

def _generate_tax_pdf(invoice_no, header_data, items, company_profile):
    """Generates a PDF for a Tax Invoice."""
    filename = f"Tax_Invoice_{invoice_no}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=40*mm, bottomMargin=30*mm)
    elements = []
    styles = getSampleStyleSheet()

    # --- Extract data ---
    company_name = company_profile.get('name', '')
    signature_path = os.path.abspath(company_profile.get('signature_path', 'data/logos/sign.png'))
    
    # --- Header & Footer Function ---
    def header_footer(canvas, doc):
        canvas.saveState()
        width, height = A4
        # Header
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(120, height - 45, company_name)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(120, height - 60, company_profile.get('address', ''))
        canvas.drawString(120, height - 72, f"GSTIN: {company_profile.get('gst_no', '')}")
        canvas.drawString(120, height - 84, f"Email: {company_profile.get('email', '')} | Phone: {company_profile.get('phone1', '')}")
        logo_path = os.path.abspath(company_profile.get('logo_path', 'data/logos/c_logo.png'))
        if os.path.exists(logo_path):
            canvas.drawImage(logo_path, 30, height - 90, width=40*mm, height=20*mm, preserveAspectRatio=True, mask='auto')

        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawRightString(width - 40, height - 50, "TAX INVOICE")
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawRightString(width - 40, height - 70, f"Invoice No: {invoice_no}")
        canvas.drawRightString(width - 40, height - 85, f"Date: {header_data['date']}")
        
        # Footer
        canvas.setFont("Helvetica", 9)
        canvas.drawString(30, 60, "Thank you for your business!")
        canvas.restoreState()

    # --- Build PDF Content ---
    customer_name = header_data.get('customer_name', '')
    elements.append(Paragraph(f'<b>Billed To:</b><br/>{customer_name}', styles['BodyText']))
    elements.append(Spacer(1, 10 * mm))

    table_header = ["S.No", "Item", "HSN", "Qty", "Price", "GST", "Tax", "Amount"]
    table_data = [table_header]
    item_total = 0
    tax_total = 0
    for idx, item in enumerate(items, start=1):
        total = item.get('total', 0)
        gst = item.get('gst_percent', 0)
        tax_amt = total * (gst / 100)
        item_total += total
        tax_total += tax_amt
        table_data.append([
            idx, Paragraph(item['item_name'], styles['BodyText']), item.get('hsn_code', ''),
            item['qty'], f"{item['price']:.2f}", f"{gst}%", f"{tax_amt:.2f}", f"{total:.2f}"
        ])
    
    item_table = Table(table_data, colWidths=[10*mm, 65*mm, 20*mm, 15*mm, 25*mm, 15*mm, 20*mm, 25*mm], repeatRows=1)
    # Apply styles (omitted for brevity, but would be here)
    elements.append(item_table)
    
    # --- Totals ---
    discount = header_data.get('discount', 0.0)
    grand_total = header_data.get('total_amount', 0.0)
    totals_data = [['Item Total:', f"Rs. {item_total:.2f}"], ['Total Tax:', f"Rs. {tax_total:.2f}"],
                   ['Discount:', f"Rs. {discount:.2f}"], ['Grand Total:', f"Rs. {grand_total:.2f}"]]
    totals_table = Table(totals_data, colWidths=[35*mm, 35*mm], style=[('ALIGN', (0,0), (-1,-1), 'RIGHT')])
    elements.append(Table([['', totals_table]], colWidths=[115*mm, 70*mm]))
    
    # --- Signature ---
    elements.append(Spacer(1, 20 * mm))
    sign_para = Paragraph(f"For <b>{company_name}</b>", styles['BodyText'])
    signature_content = [[sign_para]]
    if os.path.exists(signature_path):
        signature_content.append([Image(signature_path, width=50*mm, height=15*mm)])
    signature_block = Table(signature_content, colWidths=[50*mm], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')])
    elements.append(Table([['', signature_block]], colWidths=[130*mm, 50*mm]))

    doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer, canvasmaker=NumberedCanvas)
    return os.path.abspath(filename)


def _generate_normal_pdf(invoice_no, header_data, items, company_profile):
    """Generates a PDF for a Normal (Non-Tax) Invoice."""
    filename = f"Retail_Invoice_{invoice_no}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=40*mm, bottomMargin=30*mm)
    elements = []
    styles = getSampleStyleSheet()

    company_name = company_profile.get('name', '')
    signature_path = os.path.abspath(company_profile.get('signature_path', 'data/logos/sign.png'))

    def header_footer(canvas, doc):
        # Similar header as tax, but with "INVOICE" title
        # (Code omitted for brevity, but would be nearly identical to _generate_tax_pdf header)
        canvas.saveState()
        width, height = A4
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(120, height - 45, company_name)
        # ... rest of header ...
        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawRightString(width - 40, height - 50, "INVOICE") # Main difference
        # ... rest of header ...
        canvas.restoreState()

    customer_name = header_data.get('customer_name', '')
    elements.append(Paragraph(f'<b>Billed To:</b><br/>{customer_name}', styles['BodyText']))
    elements.append(Spacer(1, 10 * mm))

    table_header = ["S.No", "Item Name", "Qty", "Unit", "Price", "Amount"]
    table_data = [table_header]
    sub_total = 0
    for idx, item in enumerate(items, start=1):
        total = item.get('total', 0)
        sub_total += total
        table_data.append([idx, Paragraph(item['item_name'], styles['BodyText']), item['qty'], 
                           item.get('unit', 'Nos'), f"{item['price']:.2f}", f"{total:.2f}"])

    item_table = Table(table_data, colWidths=[15*mm, 80*mm, 15*mm, 20*mm, 25*mm, 30*mm], repeatRows=1)
    elements.append(item_table)
    
    discount = header_data.get('discount', 0.0)
    grand_total = header_data.get('total_amount', 0.0)
    totals_data = [['Subtotal:', f"Rs. {sub_total:.2f}"], ['Discount:', f"Rs. {discount:.2f}"],
                   ['Grand Total:', f"Rs. {grand_total:.2f}"]]
    totals_table = Table(totals_data, colWidths=[35*mm, 35*mm], style=[('ALIGN', (0,0), (-1,-1), 'RIGHT')])
    elements.append(Table([['', totals_table]], colWidths=[115*mm, 70*mm]))

    # Signature (same as tax version)
    elements.append(Spacer(1, 20 * mm))
    sign_para = Paragraph(f"For <b>{company_name}</b>", styles['BodyText'])
    signature_content = [[sign_para]]
    if os.path.exists(signature_path):
        signature_content.append([Image(signature_path, width=50*mm, height=15*mm)])
    signature_block = Table(signature_content, colWidths=[50*mm], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')])
    elements.append(Table([['', signature_block]], colWidths=[130*mm, 50*mm]))

    doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer, canvasmaker=NumberedCanvas)
    return os.path.abspath(filename)


def generate_invoice_pdf(invoice_no):
    """
    Main function to generate a PDF for a given invoice number.
    It automatically determines if it's a tax or normal invoice.
    """
    header_data = get_invoice_details_by_no(invoice_no)
    items = get_invoice_items_by_no(invoice_no)
    company_profile = get_company_profile()

    if not header_data or not items or not company_profile:
        raise FileNotFoundError(f"Could not retrieve all necessary data for invoice '{invoice_no}'.")

    # Check if any item has GST to determine the invoice type
    is_tax_invoice = any(item.get('gst_percent', 0) > 0 for item in items)

    if is_tax_invoice:
        return _generate_tax_pdf(invoice_no, header_data, items, company_profile)
    else:
        return _generate_normal_pdf(invoice_no, header_data, items, company_profile)
