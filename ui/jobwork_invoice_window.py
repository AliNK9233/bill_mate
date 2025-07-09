from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit,
    QHBoxLayout, QComboBox, QMessageBox
)
from PyQt5.QtGui import QIcon, QFont
from models.invoice_model import save_invoice, get_next_invoice_number, save_customer
from models.company_model import get_company_profile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import datetime


class JobWorkInvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧾 Job Work Invoice Generator")
        self.setGeometry(200, 100, 800, 500)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("🧾 Job Work Invoice")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title_label)

        # 🧑 Customer Details
        customer_layout = QHBoxLayout()
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("👤 Customer Name")
        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("📞 Phone Number")
        customer_layout.addWidget(self.customer_name_input)
        customer_layout.addWidget(self.customer_phone_input)
        layout.addLayout(customer_layout)

        # 📝 Job Description
        self.job_description = QTextEdit()
        self.job_description.setPlaceholderText("📝 Enter Job Work Description")
        layout.addWidget(self.job_description)

        # 💰 Job Amount
        self.job_amount_input = QLineEdit()
        self.job_amount_input.setPlaceholderText("💰 Enter Job Work Amount")
        layout.addWidget(self.job_amount_input)

        # 💵 Payment Section
        payment_layout = QHBoxLayout()
        self.paid_amount_input = QLineEdit()
        self.paid_amount_input.setPlaceholderText("💸 Amount Paid")

        self.payment_method_select = QComboBox()
        self.payment_method_select.addItems(["Cash", "Card", "UPI", "Cheque"])

        self.payment_status_select = QComboBox()
        self.payment_status_select.addItems(["Paid", "Partial", "Unpaid"])

        payment_layout.addWidget(self.paid_amount_input)
        payment_layout.addWidget(self.payment_method_select)
        payment_layout.addWidget(self.payment_status_select)
        layout.addLayout(payment_layout)

        # 📥 Generate PDF Button
        generate_btn = QPushButton("📥 Generate PDF & Save Invoice")
        generate_btn.clicked.connect(self.generate_job_work_pdf)
        layout.addWidget(generate_btn)

        self.setLayout(layout)

    def generate_job_work_pdf(self):
        """
        Generate Job Work PDF Invoice and save to DB.
        """
        try:
            profile = get_company_profile()
            company_name = profile[1]
            gst_no = profile[2]
            address = profile[3]
            email = profile[4]
            phone = profile[5]
            logo_path = profile[6]

            # Customer Details
            customer_name = self.customer_name_input.text().strip()
            customer_phone = self.customer_phone_input.text().strip()

            if not customer_name or not self.job_amount_input.text().strip():
                QMessageBox.warning(
                    self, "Missing Data", "⚠️ Customer name and Job Amount are required.")
                return

            # Save customer
            customer_id = save_customer(
                customer_name, customer_phone, "", "")

            # Job Work Data
            job_description = self.job_description.toPlainText().strip()
            job_amount = float(self.job_amount_input.text().strip() or 0.0)

            paid_amount = float(self.paid_amount_input.text().strip() or 0.0)
            balance = job_amount - paid_amount
            status = "Paid" if balance <= 0 else (
                "Partial" if paid_amount > 0 else "Unpaid")
            payment_method = self.payment_method_select.currentText()

            # Save invoice to DB
            invoice_no = get_next_invoice_number()
            save_invoice(
                customer_id=customer_id,
                total_amount=job_amount,
                paid_amount=paid_amount,
                balance=balance,
                payment_method=payment_method,
                status=status,
                items=[]
            )

            # Generate PDF
            filename = f"JobWork_Invoice_{invoice_no}.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4

            # --- Header ---
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, company_name)
            c.setFont("Helvetica", 10)
            c.drawString(50, height - 65, f"GST No: {gst_no}")
            c.drawString(50, height - 80, f"Address: {address}")
            c.drawString(50, height - 95, f"Email: {email} | Phone: {phone}")

            c.setFont("Helvetica-Bold", 12)
            c.drawRightString(width - 50, height - 50,
                              f"Invoice No: {invoice_no}")
            c.drawRightString(width - 50, height - 65,
                              f"Date: {datetime.date.today()}")

            # --- Customer Info ---
            y = height - 130
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Billed To:")
            c.setFont("Helvetica", 10)
            c.drawString(130, y, customer_name)
            y -= 15
            c.drawString(130, y, f"Phone: {customer_phone}")

            y -= 30

            # --- Job Description ---
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Job Work Description:")
            y -= 15
            c.setFont("Helvetica", 10)
            c.drawString(60, y, job_description)

            y -= 50

            # --- Totals ---
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, f"Total Amount (₹):")
            c.drawRightString(width - 50, y, f"{job_amount:.2f}")

            y -= 20
            if paid_amount > 0:
                c.setFont("Helvetica", 10)
                c.drawString(50, y, f"Paid Amount (₹):")
                c.drawRightString(width - 50, y, f"{paid_amount:.2f}")
                y -= 15

            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, f"Balance (₹):")
            c.drawRightString(width - 50, y, f"{balance:.2f}")

            # --- Footer ---
            y -= 50
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(50, y, "Thank you for your business!")
            c.save()

            QMessageBox.information(
                self, "Success", f"✅ Job Work Invoice saved as {filename}")

            # Reset UI
            self.job_description.clear()
            self.job_amount_input.clear()
            self.paid_amount_input.clear()

        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to generate Job Work PDF: {e}")
