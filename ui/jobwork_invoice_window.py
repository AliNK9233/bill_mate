from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QComboBox, QMessageBox, QHeaderView
)
from PyQt5.QtGui import QIcon, QFont
from models.invoice_model import save_invoice, get_next_invoice_number, get_all_customers, save_customer
from models.company_model import get_company_profile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import datetime
import os


class JobWorkInvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧾 Job Work Invoice")
        self.setGeometry(200, 100, 950, 600)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))
        self.customer_lookup = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # 🌟 Title
        title_label = QLabel("🧾 Job Work Invoice")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #0A3D62;")
        layout.addWidget(title_label)

        # 🧑 Customer Section
        customer_box = QHBoxLayout()
        self.customer_select = QComboBox()
        self.customer_select.setEditable(True)
        self.load_customers()
        self.customer_select.setPlaceholderText("👤 Select or Add Customer")
        self.customer_select.currentIndexChanged.connect(
            self.on_customer_selected)

        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("📞 Phone Number")
        customer_box.addWidget(self.customer_select, 3)
        customer_box.addWidget(self.customer_phone_input, 2)
        layout.addLayout(customer_box)

        # 📋 Job Work Items Table
        self.job_table = QTableWidget()
        self.job_table.setColumnCount(2)
        self.job_table.setHorizontalHeaderLabels(["Description", "Amount (₹)"])
        self.job_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.job_table.setStyleSheet(
            "QHeaderView::section {background-color: #007ACC; color: white;}")
        layout.addWidget(self.job_table)

        # ➕➖ Add/Remove Buttons
        btn_box = QHBoxLayout()
        add_btn = QPushButton("➕ Add Job Work Item")
        add_btn.setStyleSheet(
            "background-color: #007ACC; color: white; font-weight: bold;")
        add_btn.clicked.connect(self.add_row)

        remove_btn = QPushButton("➖ Remove Selected Item")
        remove_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold;")
        remove_btn.clicked.connect(self.remove_row)

        btn_box.addWidget(add_btn)
        btn_box.addWidget(remove_btn)
        layout.addLayout(btn_box)

        # 💵 Payment Section
        payment_box = QHBoxLayout()
        self.paid_amount_input = QLineEdit()
        self.paid_amount_input.setPlaceholderText("💸 Enter Paid Amount")

        self.payment_method_select = QComboBox()
        self.payment_method_select.addItems(["Cash", "Card", "UPI", "Cheque"])

        self.payment_status_select = QComboBox()
        self.payment_status_select.addItems(["Unpaid", "Partial", "Paid"])
        payment_box.addWidget(self.paid_amount_input, 2)
        payment_box.addWidget(self.payment_method_select, 1)
        payment_box.addWidget(self.payment_status_select, 1)
        layout.addLayout(payment_box)

        # 💰 Total
        self.total_label = QLabel("💰 Total: ₹0.00")
        self.total_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(self.total_label)

        # 📥 Generate & Reset Buttons
        action_box = QHBoxLayout()
        generate_btn = QPushButton("📥 Generate PDF & Save Invoice")
        generate_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold;")
        generate_btn.clicked.connect(self.generate_pdf)

        reset_btn = QPushButton("🔄 Reset Form")
        reset_btn.setStyleSheet("background-color: #95a5a6; color: white;")
        reset_btn.clicked.connect(self.reset_form)

        action_box.addWidget(generate_btn, 2)
        action_box.addWidget(reset_btn, 1)
        layout.addLayout(action_box)

        self.setLayout(layout)

    def load_customers(self):
        """ Load customer names from DB. """
        self.customer_lookup.clear()
        self.customer_select.clear()
        customers = get_all_customers()
        for cust in customers:
            name, phone, *_ = cust
            display_text = f"{name} ({phone})"
            self.customer_select.addItem(display_text)
            self.customer_lookup[display_text] = (name, phone)
        self.customer_select.addItem("➕ Add New Guest Customer")

    def on_customer_selected(self):
        """ Auto-fill phone for existing customers. """
        selected = self.customer_select.currentText()
        if selected == "➕ Add New Guest Customer":
            self.customer_phone_input.clear()
        elif selected in self.customer_lookup:
            _, phone = self.customer_lookup[selected]
            self.customer_phone_input.setText(phone)

    def add_row(self):
        """ Add a blank row for a new job work item. """
        row = self.job_table.rowCount()
        self.job_table.insertRow(row)
        self.job_table.setItem(row, 0, QTableWidgetItem("Enter Description"))
        self.job_table.setItem(row, 1, QTableWidgetItem("0.00"))
        self.job_table.itemChanged.connect(self.update_total)

    def remove_row(self):
        """ Remove selected job work item. """
        selected_row = self.job_table.currentRow()
        if selected_row >= 0:
            self.job_table.removeRow(selected_row)
            self.update_total()
        else:
            QMessageBox.warning(self, "⚠️ No Selection",
                                "Please select a row to remove.")

    def update_total(self):
        """ Update total amount dynamically. """
        total = 0.0
        for row in range(self.job_table.rowCount()):
            try:
                amount = float(self.job_table.item(row, 1).text())
                total += amount
            except Exception:
                continue
        self.total_label.setText(f"💰 Total: ₹{total:.2f}")

    def reset_form(self):
        """ Reset all fields and table. """
        self.customer_select.setCurrentIndex(0)
        self.customer_phone_input.clear()
        self.job_table.setRowCount(0)
        self.paid_amount_input.clear()
        self.total_label.setText("💰 Total: ₹0.00")

    def generate_pdf(self):
        try:
            # 🏢 Get company profile details
            profile = get_company_profile()
            if not profile:
                QMessageBox.critical(
                    self, "❌ Error", "Company profile is missing. Please set it up first.")
                return

            # Extract fields safely
            company_name = profile.get("name", "Company Name")
            gst_no = profile.get("gst_no", "")
            address = profile.get("address", "")
            phone1 = profile.get("phone1", "")
            phone2 = profile.get("phone2", "")
            email = profile.get("email", "")
            website = profile.get("website", "")
            bank_name = profile.get("bank_name", "")
            bank_account = profile.get("bank_account", "")
            ifsc_code = profile.get("ifsc_code", "")
            branch_address = profile.get("branch_address", "")

            # 🔥 Force logo path
            logo_path = "data/logos/rayani_logo.png"
            if not os.path.exists(logo_path):
                logo_path = ""  # Fallback if logo file is missing

            # 🧑 Customer Details
            customer_name = self.customer_select.currentText().strip()
            customer_phone = self.customer_phone_input.text().strip()

            if not customer_name or self.job_table.rowCount() == 0:
                QMessageBox.warning(
                    self, "⚠️ Missing Data",
                    "Please enter customer name and at least one job work item."
                )
                return

            # 📋 Collect job work items
            self.job_items = []
            for row in range(self.job_table.rowCount()):
                description = self.job_table.item(row, 0).text().strip()
                try:
                    amount = float(self.job_table.item(
                        row, 1).text().strip() or "0")
                except ValueError:
                    amount = 0.0
                if description:
                    self.job_items.append((description, amount))

            if not self.job_items:
                QMessageBox.warning(self, "⚠️ No Items",
                                    "Add at least one job work item.")
                return

            total_amount = sum(amount for _, amount in self.job_items)
            paid_amount = float(self.paid_amount_input.text().strip() or "0")
            balance = total_amount - paid_amount
            status = "Paid" if balance <= 0 else "Partial" if paid_amount > 0 else "Unpaid"
            payment_method = self.payment_method_select.currentText()

            # ✅ Save customer to DB
            customer_id = save_customer(customer_name, customer_phone, "", "")
            if not customer_id:
                raise Exception("Could not save customer to database.")

            # ✅ Save invoice to DB
            invoice_no = get_next_invoice_number()
            save_invoice(
                customer_id=customer_id,
                total_amount=total_amount,
                paid_amount=paid_amount,
                balance=balance,
                payment_method=payment_method,
                status=status,
                items=[]
            )

            # 📄 Generate PDF
            filename = f"JobWork_Invoice_{invoice_no}.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4

            # --- 🖼 Header with Logo & Company Info ---
            if logo_path and os.path.exists(logo_path):
                c.drawImage(logo_path, 40, height - 110,
                            width=80, height=80, mask='auto')

            c.setFont("Helvetica-Bold", 16)
            c.drawString(140, height - 50, company_name)
            c.setFont("Helvetica", 10)
            c.drawString(140, height - 65, f"GST No: {gst_no}")
            c.drawString(140, height - 80, f"Address: {address}")
            c.drawString(140, height - 95,
                         f"Phone: {phone1}, {phone2} | Email: {email}")
            c.drawString(140, height - 110, f"Website: {website}")

            # 🏦 Bank Details
            c.drawString(140, height - 125,
                         f"Bank: {bank_name}, A/C: {bank_account}")
            c.drawString(140, height - 140,
                         f"IFSC: {ifsc_code}, Branch: {branch_address}")

            # 📑 Invoice Details
            c.setFont("Helvetica-Bold", 12)
            c.drawRightString(width - 40, height - 50,
                              f"Invoice No: {invoice_no}")
            c.drawRightString(width - 40, height - 65,
                              f"Date: {datetime.date.today()}")

            # 🧑 Customer Info
            y = height - 170
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Billed To:")
            c.setFont("Helvetica", 10)
            c.drawString(130, y, customer_name)
            y -= 15
            c.drawString(130, y, f"Phone: {customer_phone}")

            # 📋 Job Work Items
            y -= 30
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Job Work Details:")
            y -= 20
            c.setFont("Helvetica", 10)
            for idx, (desc, amt) in enumerate(self.job_items, 1):
                c.drawString(60, y, f"{idx}. {desc}")
                c.drawRightString(width - 60, y, f"₹{amt:.2f}")
                y -= 15

            # 💵 Totals
            y -= 20
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, f"Total Amount (₹):")
            c.drawRightString(width - 50, y, f"{total_amount:.2f}")

            if paid_amount > 0:
                y -= 20
                c.setFont("Helvetica", 10)
                c.drawString(50, y, f"Paid Amount (₹):")
                c.drawRightString(width - 50, y, f"{paid_amount:.2f}")

            y -= 20
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, f"Balance (₹):")
            c.drawRightString(width - 50, y, f"{balance:.2f}")

            # --- Footer ---
            y -= 50
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(50, y, "Thank you for your business!")
            c.save()

            QMessageBox.information(
                self, "✅ Success", f"Job Work Invoice saved as {filename}"
            )

            # 🔄 Reset UI
            self.job_table.setRowCount(0)
            self.paid_amount_input.clear()
            self.update_total()

        except Exception as e:
            QMessageBox.critical(
                self, "❌ Error", f"Failed to generate Job Work PDF:\n{e}"
            )
