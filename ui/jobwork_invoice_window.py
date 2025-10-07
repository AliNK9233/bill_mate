import os
import webbrowser
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QMessageBox, QComboBox, QCompleter, QFormLayout, QHeaderView
)
from PyQt5.QtGui import QIcon, QFont
from models.jobwork_model import save_jobwork_invoice, get_next_jobwork_invoice_number
from models.company_model import get_company_profile
from models.invoice_model import get_all_customers

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
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.drawRightString(A4[0] - 20 * mm, 15 * mm, f"Page {self._pageNumber} of {page_count}")


class JobWorkInvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Job Work Invoice")
        self.setGeometry(200, 100, 950, 600)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.customer_lookup = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title and Refresh Button
        header_layout = QHBoxLayout()
        title_label = QLabel("Job Work Invoice")
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

        # Customer Section
        customer_form_layout = QFormLayout()
        self.customer_select = QComboBox()
        self.customer_select.setEditable(False)
        self.load_customers()
        customer_form_layout.addRow(QLabel("Customer:"), self.customer_select)
        layout.addLayout(customer_form_layout)

        # Job Work Items Table
        self.job_table = QTableWidget()
        self.job_table.setColumnCount(2)
        self.job_table.setHorizontalHeaderLabels(["Description", "Amount (Rs.)"])
        self.job_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.job_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.job_table)
        self.job_table.itemChanged.connect(self.update_total)

        # Add/Remove Buttons
        btn_box = QHBoxLayout()
        add_btn = QPushButton("➕ Add Job Work Item")
        add_btn.clicked.connect(self.add_row)
        remove_btn = QPushButton("➖ Remove Selected Item")
        remove_btn.clicked.connect(self.remove_row)
        btn_box.addWidget(add_btn)
        btn_box.addWidget(remove_btn)
        layout.addLayout(btn_box)

        # Payment Section
        payment_layout = QHBoxLayout()
        payment_form = QFormLayout()
        self.paid_amount_input = QLineEdit()
        payment_form.addRow("Amount Paid (Rs.):", self.paid_amount_input)
        
        self.payment_method_select = QComboBox()
        self.payment_method_select.addItems(["Cash", "Card", "UPI", "Cheque"])
        self.payment_status_select = QComboBox()
        self.payment_status_select.addItems(["Unpaid", "Partial", "Paid"])
        
        payment_layout.addLayout(payment_form)
        payment_layout.addWidget(self.payment_method_select)
        payment_layout.addWidget(self.payment_status_select)
        layout.addLayout(payment_layout)

        # Summary Labels
        self.grand_total_label = QLabel("Grand Total: Rs. 0.00")
        self.grand_total_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(self.grand_total_label)

        # Generate Button
        generate_btn = QPushButton("📥 Generate PDF & Save Invoice")
        generate_btn.clicked.connect(self.generate_pdf)
        layout.addWidget(generate_btn)

        self.setLayout(layout)
        self.add_row()

    def refresh_data(self):
        self.load_customers()
        QMessageBox.information(self, "Refreshed", "Customer list has been updated.")

    def load_customers(self):
        self.customer_lookup.clear()
        self.customer_select.clear()
        self.customer_select.addItem("--- Select a Customer ---")
        customers = get_all_customers()
        for cust in customers:
            customer_id, name, phone, address, *_ = cust
            display_text = f"{name} ({phone})"
            self.customer_select.addItem(display_text)
            self.customer_lookup[display_text] = (phone, address, customer_id)

    def get_customer_details(self):
        selected_text = self.customer_select.currentText()
        if selected_text in self.customer_lookup:
            phone, _, customer_id = self.customer_lookup[selected_text]
            customer_name = selected_text.split(" (")[0].strip()
            return customer_name, phone, customer_id
        return None, None, None

    def add_row(self):
        row = self.job_table.rowCount()
        self.job_table.insertRow(row)
        self.job_table.setItem(row, 0, QTableWidgetItem(""))
        self.job_table.setItem(row, 1, QTableWidgetItem("0.00"))

    def remove_row(self):
        selected_row = self.job_table.currentRow()
        if selected_row >= 0:
            self.job_table.removeRow(selected_row)
            self.update_total()
        else:
            QMessageBox.warning(self, "No Selection", "Please select a row to remove.")

    def update_total(self):
        total = 0.0
        for row in range(self.job_table.rowCount()):
            try:
                amount = float(self.job_table.item(row, 1).text())
                total += amount
            except (ValueError, AttributeError):
                continue
        self.grand_total_label.setText(f"Grand Total: Rs. {total:.2f}")

    def generate_pdf(self):
        try:
            customer_name, customer_phone, customer_id = self.get_customer_details()
            if not customer_id:
                QMessageBox.warning(self, "Missing Customer", "Please select a customer.")
                return

            items = []
            for row in range(self.job_table.rowCount()):
                desc = self.job_table.item(row, 0).text().strip()
                amt_str = self.job_table.item(row, 1).text().strip()
                if desc and amt_str:
                    try:
                        items.append({"description": desc, "amount": float(amt_str)})
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Amount", f"Invalid amount in row {row+1}.")
                        return
            if not items:
                QMessageBox.warning(self, "Missing Items", "Please add at least one job work item.")
                return

            profile = get_company_profile()
            company_name = profile.get('name', "Your Company")
            address = profile.get('address', "Your Address")
            email = profile.get('email', "your.email@example.com")
            phone1 = profile.get('phone1', "9999988888")
            logo_path = profile.get('logo_path')
            signature_path = profile.get('signature_path')

            fallback_logo = os.path.abspath("data/logos/c_logo.png")
            logo_path = os.path.abspath(logo_path) if logo_path and os.path.exists(logo_path) else fallback_logo
            fallback_signature = os.path.abspath("data/logos/sign.png")
            signature_path = os.path.abspath(signature_path) if signature_path and os.path.exists(signature_path) else fallback_signature
            
            total_amount = sum(item['amount'] for item in items)
            paid_amount = float(self.paid_amount_input.text().strip() or 0.0)
            balance = total_amount - paid_amount
            status = self.payment_status_select.currentText()
            payment_method = self.payment_method_select.currentText()
            
            invoice_no = "JINV-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            invoice_date = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")

            save_jobwork_invoice(
                customer_id, total_amount, paid_amount, balance, 
                payment_method, status, items, invoice_no=invoice_no
            )

            filename = f"JobWork_Invoice_{invoice_no}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=40*mm, bottomMargin=30*mm)
            elements = []
            styles = getSampleStyleSheet()

            def header_footer(canvas, doc):
                canvas.saveState()
                width, height = A4
                canvas.setFont("Helvetica-Bold", 16)
                canvas.drawString(120, height - 45, company_name)
                canvas.setFont("Helvetica", 9)
                canvas.drawString(120, height - 60, address)
                canvas.drawString(120, height - 72, f"Email: {email} | Phone: {phone1}")
                if os.path.exists(logo_path):
                    canvas.drawImage(logo_path, 30, height - 90, width=40*mm, height=20*mm, preserveAspectRatio=True, mask='auto')

                canvas.setFont("Helvetica-Bold", 20)
                canvas.drawRightString(width - 40, height - 50, "INVOICE")
                canvas.setFont("Helvetica-Bold", 11)
                canvas.drawRightString(width - 40, height - 70, f"Invoice No: {invoice_no}")
                canvas.drawRightString(width - 40, height - 85, f"Date: {invoice_date}")
                
                canvas.setFont("Helvetica", 9)
                canvas.drawString(30, 60, "Thank you for your business!")
                canvas.restoreState()

            customer_data = [[Paragraph(f'<b>Billed To:</b><br/>{customer_name}<br/>Phone: {customer_phone}', styles['BodyText'])]]
            elements.append(Table(customer_data, colWidths=[180*mm]))
            elements.append(Spacer(1, 10 * mm))

            table_data = [["S.No", "Description", "Amount (Rs.)"]]
            for idx, item in enumerate(items, 1):
                table_data.append([idx, Paragraph(item['description'], styles['BodyText']), f"{item['amount']:.2f}"])
            
            item_table = Table(table_data, colWidths=[15*mm, 135*mm, 35*mm], repeatRows=1)
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black), ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ]))
            elements.append(item_table)
            
            totals_data = [['Grand Total:', f"Rs. {total_amount:.2f}"]]
            totals_table = Table(totals_data, colWidths=[35*mm, 35*mm])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            wrapper_table = Table([['', totals_table]], colWidths=[115*mm, 70*mm])
            elements.append(wrapper_table)
            
            elements.append(Spacer(1, 20 * mm))
            sign_para = Paragraph(f"For <b>{company_name}</b>", styles['BodyText'])
            signature_content = [[sign_para]]
            if os.path.exists(signature_path):
                sign_img = Image(signature_path, width=50*mm, height=15*mm)
                signature_content.append([sign_img])
            
            signature_block = Table(signature_content, colWidths=[50*mm])
            signature_block.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
            signature_wrapper = Table([['', signature_block]], colWidths=[130*mm, 50*mm])
            elements.append(signature_wrapper)
            
            doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer, canvasmaker=NumberedCanvas)

            QMessageBox.information(self, "Success", f"Job Work Invoice saved as {filename}")
            webbrowser.open(os.path.abspath(filename))
            self.reset_form()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to generate Job Work Invoice: {e}")
            
    def reset_form(self):
        self.customer_select.setCurrentIndex(0)
        self.job_table.setRowCount(0)
        self.paid_amount_input.clear()
        self.update_total()
        self.add_row()

