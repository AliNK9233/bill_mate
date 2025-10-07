import os
import webbrowser
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QMessageBox, QComboBox, QCompleter, QFormLayout
)
from PyQt5.QtGui import QIcon, QFont
from models.invoice_model import save_invoice, get_next_invoice_number, get_all_customers
from models.stock_model import get_consolidated_stock, reduce_stock_quantity
from models.company_model import get_company_profile
from num2words import num2words

# --- ReportLab Imports for Professional PDF ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm


# Helper class for "Page X of Y" numbering
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add page numbers to each page"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.drawRightString(A4[0] - 20 * mm, 15 * mm, f"Page {self._pageNumber} of {page_count}")


class NormalInvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧾 Retail Invoice")
        self.setGeometry(200, 100, 1000, 600)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.invoice_items = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title and Refresh Button
        header_layout = QHBoxLayout()
        title_label = QLabel("🧾 Retail Invoice")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #0A3D62;")

        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.setFont(QFont("Segoe UI", 10))
        refresh_btn.setFixedWidth(150)
        refresh_btn.clicked.connect(self.refresh_data)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        # Customer Section (Phone field removed from UI)
        customer_form_layout = QFormLayout()
        self.customer_select = QComboBox()
        self.customer_select.setEditable(False)
        self.load_customer_options()
        customer_form_layout.addRow(QLabel("Customer:"), self.customer_select)
        layout.addLayout(customer_form_layout)

        # Item Search + Quantity
        item_layout = QHBoxLayout()
        self.item_search = QComboBox()
        self.load_item_options()
        self.item_search.setEditable(True)
        completer = QCompleter([self.item_search.itemText(i)
                                for i in range(self.item_search.count())])
        completer.setCaseSensitivity(False)
        self.item_search.setCompleter(completer)

        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("Qty")
        self.qty_input.returnPressed.connect(self.add_item_to_invoice)
        add_item_btn = QPushButton("➕ Add Item")
        add_item_btn.clicked.connect(self.add_item_to_invoice)

        item_layout.addWidget(self.item_search)
        item_layout.addWidget(self.qty_input)
        item_layout.addWidget(add_item_btn)
        layout.addLayout(item_layout)

        # Invoice Table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(4)
        self.invoice_table.setHorizontalHeaderLabels(["Item Name", "Qty", "Rate (₹)", "Total (₹)"])
        layout.addWidget(self.invoice_table)

        # Payment and Discount Section with Labels
        payment_layout = QHBoxLayout()
        payment_form = QFormLayout()
        self.paid_amount_input = QLineEdit()
        self.discount_input = QLineEdit()
        self.discount_input.setText("0")
        self.discount_input.textChanged.connect(self.update_invoice_total)
        
        payment_form.addRow("Amount Paid (₹):", self.paid_amount_input)
        payment_form.addRow("Discount (₹):", self.discount_input)

        self.payment_method_select = QComboBox()
        self.payment_method_select.addItems(["Cash", "Card", "UPI", "Cheque"])
        self.payment_status_select = QComboBox()
        self.payment_status_select.addItems(["Paid", "Partial", "Unpaid"])

        payment_layout.addLayout(payment_form)
        payment_layout.addWidget(self.payment_method_select)
        payment_layout.addWidget(self.payment_status_select)
        layout.addLayout(payment_layout)

        # Total Labels
        self.grand_total_label = QLabel("💳 Grand Total: ₹0.00")
        self.grand_total_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.grand_total_label)

        # Generate PDF Button
        generate_btn = QPushButton("📥 Generate PDF & Save Invoice")
        generate_btn.clicked.connect(self.generate_invoice_pdf)
        layout.addWidget(generate_btn)

        self.setLayout(layout)
        self.update_invoice_total()

    def refresh_data(self):
        self.load_customer_options()
        self.load_item_options()
        QMessageBox.information(self, "Refreshed", "Customer and stock lists have been updated.")

    def get_customer_details(self):
        selected_text = self.customer_select.currentText()
        if selected_text in self.customer_lookup:
            phone, _, customer_id = self.customer_lookup[selected_text]
            customer_name = selected_text.split(" (")[0].strip()
            return customer_name, phone, customer_id
        return None, None, None

    def load_customer_options(self):
        self.customer_lookup = {}
        self.customer_select.clear()
        self.customer_select.addItem("--- Select a Customer ---")
        customers = get_all_customers()
        for cust in customers:
            customer_id, name, phone, address, *_ = cust
            display_text = f"{name} ({phone})"
            self.customer_select.addItem(display_text)
            self.customer_lookup[display_text] = (phone, address, customer_id)

    def customer_changed(self):
        # No longer needs to update a phone field
        pass

    def load_item_options(self):
        items = get_consolidated_stock()
        self.item_lookup = {}
        self.item_search.clear()
        for row in items:
            if row[7] > 0:
                display_text = f"{row[2]} - {row[1]}"
                self.item_search.addItem(display_text)
                self.item_lookup[display_text] = row

    def add_item_to_invoice(self):
        selected_text = self.item_search.currentText()
        if selected_text not in self.item_lookup:
            QMessageBox.warning(self, "Invalid Item", "⚠️ Please select a valid item.")
            return

        try:
            qty = int(self.qty_input.text().strip())
            if qty <= 0: raise ValueError
        except:
            QMessageBox.warning(self, "Invalid Quantity", "⚠️ Enter a valid positive quantity.")
            return

        item = self.item_lookup[selected_text]
        if qty > item[7]:
            QMessageBox.warning(self, "Stock Error", f"⚠️ Only {item[7]} units available.")
            return

        row_pos = self.invoice_table.rowCount()
        self.invoice_table.insertRow(row_pos)
        self.invoice_table.setItem(row_pos, 0, QTableWidgetItem(item[1]))
        self.invoice_table.setItem(row_pos, 1, QTableWidgetItem(str(qty)))
        self.invoice_table.setItem(row_pos, 2, QTableWidgetItem(f"{item[6]:.2f}"))
        self.invoice_table.setItem(row_pos, 3, QTableWidgetItem(f"{item[6] * qty:.2f}"))

        self.invoice_items.append({
            "code": item[2], "name": item[1], "price": item[6], "qty": qty,
            "total": item[6] * qty, "hsn": item[4] if len(item) > 4 else "", "gst": 0
        })
        self.update_invoice_total()
        self.qty_input.clear()

    def update_invoice_total(self):
        sub_total = sum(item['total'] for item in self.invoice_items)
        try:
            discount = float(self.discount_input.text().strip() or 0.0)
        except ValueError:
            discount = 0.0
        
        grand_total = sub_total - discount
        self.grand_total_label.setText(f"💳 Grand Total: ₹{grand_total:.2f}")

    def generate_invoice_pdf(self):
        try:
            # 1. --- GATHER DATA ---
            profile = get_company_profile()
            company_name = profile.get('name', "Your Company Name")
            address = profile.get('address', "Your Company Address")
            email = profile.get('email', "your.email@example.com")
            phone1 = profile.get('phone1', "9999988888")
            phone2 = profile.get('phone2', "")
            logo_path = profile.get('logo_path')
            signature_path = profile.get('signature_path')

            fallback_logo = os.path.abspath("data/logos/c_logo.png")
            logo_path = os.path.abspath(logo_path) if logo_path and os.path.exists(logo_path) else fallback_logo
            
            fallback_signature = os.path.abspath("data/logos/sign.png")
            signature_path = os.path.abspath(signature_path) if signature_path and os.path.exists(signature_path) else fallback_signature

            customer_name, customer_phone, customer_id = self.get_customer_details()
            if not customer_id:
                QMessageBox.warning(self, "Missing Customer", "⚠️ Please select a customer.")
                return
            if not self.invoice_items:
                QMessageBox.warning(self, "Missing Items", "⚠️ Please add at least one item.")
                return

            # FIXED: Use a timestamp for a guaranteed unique invoice number
            invoice_no = "INV-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

            sub_total = sum(item['total'] for item in self.invoice_items)
            try:
                discount = float(self.discount_input.text().strip() or 0.0)
            except ValueError:
                discount = 0.0
            grand_total = sub_total - discount

            paid_amount = float(self.paid_amount_input.text().strip() or 0.0)
            balance = grand_total - paid_amount
            status = "Paid" if balance <= 0 else ("Partial" if paid_amount > 0 else "Unpaid")

            # 2. --- SAVE TO DATABASE ---
            # NOTE: Pass the unique invoice_no to the model
            save_invoice(
                customer_id=customer_id, total_amount=grand_total, paid_amount=paid_amount,
                balance=balance, payment_method=self.payment_method_select.currentText(),
                status=status, items=self.invoice_items, discount=discount, invoice_no=invoice_no
            )
            for it in self.invoice_items:
                reduce_stock_quantity(it["code"], int(it["qty"]))
            self.load_item_options()

            # 3. --- SETUP PDF DOCUMENT ---
            filename = f"Retail_Invoice_{invoice_no}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=40*mm, bottomMargin=30*mm)
            elements = []
            styles = getSampleStyleSheet()

            # 4. --- DEFINE HEADER AND FOOTER (FOOTER IS SIMPLIFIED) ---
            invoice_date = datetime.datetime.now().strftime("%d-%m-%Y")
            def header_footer(canvas, doc):
                canvas.saveState()
                width, height = A4
                # -- HEADER --
                canvas.setFont("Helvetica-Bold", 16)
                canvas.drawString(120, height - 45, company_name)
                canvas.setFont("Helvetica", 9)
                canvas.drawString(120, height - 60, address)
                canvas.drawString(120, height - 72, f"Phone: {phone1}, {phone2}")
                canvas.drawString(120, height - 84, f"Email: {email}")
                if os.path.exists(logo_path):
                    canvas.drawImage(logo_path, 30, height - 90, width=40*mm, height=20*mm, preserveAspectRatio=True, mask='auto')

                canvas.setFont("Helvetica-Bold", 20)
                canvas.drawRightString(width - 40, height - 50, "INVOICE")
                canvas.setFont("Helvetica-Bold", 11)
                canvas.drawRightString(width - 40, height - 70, f"Invoice No: {invoice_no}")
                canvas.drawRightString(width - 40, height - 85, f"Date: {invoice_date}")

                # -- FOOTER (PAGE NUMBER ONLY) --
                canvas.setFont("Helvetica", 9)
                canvas.drawString(30, 60, "Thank you for your business!")
                canvas.restoreState()

            # 5. --- BUILD PDF CONTENT FLOWABLES ---
            customer_data = [[Paragraph(f'<b>Billed To:</b><br/>{customer_name}<br/>Phone: {customer_phone}', styles['BodyText'])]]
            elements.append(Table(customer_data, colWidths=[180*mm]))
            elements.append(Spacer(1, 10 * mm))

            table_header = ["S.No", "Item Name", "Qty", "Unit", "Price", "Amount"]
            table_data = [table_header]
            for idx, item in enumerate(self.invoice_items, start=1):
                table_data.append([idx, Paragraph(item['name'], styles['BodyText']), item['qty'], item.get('unit', 'Nos'), f"{item['price']:.2f}", f"{item['total']:.2f}"])
            item_table = Table(table_data, colWidths=[15*mm, 80*mm, 15*mm, 20*mm, 25*mm, 30*mm], repeatRows=1)
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (1, 1), (1, -1), 'LEFT'), ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
            ]))
            elements.append(item_table)
            
            # --- TOTALS SECTION ---
            totals_data = [
                ['Subtotal:', f"₹{sub_total:.2f}"],
                ['Discount:', f"₹{discount:.2f}"],
                ['Grand Total:', f"₹{grand_total:.2f}"]
            ]
            totals_table = Table(totals_data, colWidths=[35*mm, 35*mm])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 2), (-1, 2), 12), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            wrapper_table = Table([['', totals_table]], colWidths=[115*mm, 70*mm])
            elements.append(wrapper_table)
            
            # --- SIGNATURE SECTION (LAST PAGE ONLY) ---
            elements.append(Spacer(1, 20 * mm))
            sign_para = Paragraph(f"For <b>{company_name}</b>", styles['BodyText'])
            signature_content = [[sign_para]]
            if os.path.exists(signature_path):
                sign_img = Image(signature_path, width=50 * mm, height=15 * mm)
                signature_content.append([sign_img])
            
            signature_block = Table(signature_content, colWidths=[50 * mm])
            signature_block.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
            signature_wrapper = Table([['', signature_block]], colWidths=[130 * mm, 50 * mm])
            elements.append(signature_wrapper)
            
            # 6. --- GENERATE THE PDF ---
            doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer, canvasmaker=NumberedCanvas)

            # 7. --- CLEANUP AND FINISH ---
            QMessageBox.information(self, "✅ Success", f"Invoice saved as {filename}")
            webbrowser.open(os.path.abspath(filename))
            
            self.invoice_table.setRowCount(0)
            self.invoice_items.clear()
            self.update_invoice_total()
            self.paid_amount_input.clear()
            self.discount_input.setText("0")
            self.customer_select.setCurrentIndex(0)

        except Exception as e:
            print(f"❌ Exception during PDF generation: {e}")
            QMessageBox.warning(self, "❌ Error", f"Failed to generate PDF: {e}")

