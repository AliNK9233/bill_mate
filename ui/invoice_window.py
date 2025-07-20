import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QComboBox, QCompleter, QTextEdit
)

from PyQt5.QtGui import QIcon, QFont
from models.invoice_model import save_invoice, get_next_invoice_number, get_all_customers, save_customer
from models.stock_model import get_consolidated_stock, reduce_stock_quantity
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import datetime
from models.invoice_model import save_customer
from num2words import num2words
from reportlab.lib import colors
from models.company_model import get_company_profile


class InvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧾 Invoice Generator")
        self.setGeometry(200, 100, 1000, 600)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))
        self.invoice_items = []
        self.total_amount = 0.0
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # 🌟 Title
        title_label = QLabel("🧾 Invoice Generator")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #0A3D62;")
        layout.addWidget(title_label)

        # 🧑 Customer Section
        customer_layout = QHBoxLayout()

        # 🆕 New Dropdown: Existing / Guest
        self.customer_type_select = QComboBox()
        self.customer_type_select.addItems(
            ["📋 Existing Customer", "🆕 Guest Customer"])
        self.customer_type_select.currentIndexChanged.connect(
            self.toggle_customer_mode)

        # Customer Name Dropdown (for Existing)
        self.customer_select = QComboBox()
        self.customer_select.setEditable(False)
        self.load_customer_options()
        self.customer_select.currentIndexChanged.connect(self.customer_changed)

        # Guest Customer Inputs
        self.guest_name_input = QLineEdit()
        self.guest_name_input.setPlaceholderText("👤 Enter Customer Name")
        self.guest_name_input.hide()  # hidden initially

        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("📞 Phone")
        self.customer_phone_input.setMaxLength(
            10)  # optional: phone length limit

        customer_layout.addWidget(self.customer_type_select, 1)
        customer_layout.addWidget(self.customer_select, 3)
        customer_layout.addWidget(self.guest_name_input, 3)
        customer_layout.addWidget(self.customer_phone_input, 2)

        layout.addLayout(customer_layout)

        # 📦 Item Search + Quantity
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

        # 📝 Invoice Table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(5)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Item Name", "Qty", "Rate (₹)", "GST %", "Total (₹)"]
        )
        layout.addWidget(self.invoice_table)

        # 💵 Payment Section
        payment_layout = QHBoxLayout()
        self.paid_amount_input = QLineEdit()
        self.paid_amount_input.setPlaceholderText("💰 Amount Paid")

        self.payment_method_select = QComboBox()
        self.payment_method_select.addItems(["Cash", "Card", "UPI", "Cheque"])

        self.billing_type = QComboBox()
        self.billing_type.addItems(["Normal Bill", "GST Bill"])
        self.billing_type.currentIndexChanged.connect(
            self.update_invoice_total)

        self.payment_status_select = QComboBox()
        self.payment_status_select.addItems(["Paid", "Partial", "Unpaid"])

        payment_layout.addWidget(self.paid_amount_input)
        payment_layout.addWidget(self.payment_method_select)
        payment_layout.addWidget(self.billing_type)
        payment_layout.addWidget(self.payment_status_select)
        layout.addLayout(payment_layout)

        # 💰 Total Labels
        self.total_label = QLabel("💰 Total: ₹0.00")
        self.total_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.total_label)

        self.gst_total_label = QLabel("GST Total: ₹0.00")
        self.gst_total_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.gst_total_label.setVisible(False)
        layout.addWidget(self.gst_total_label)

        self.grand_total_label = QLabel("💳 Grand Total: ₹0.00")
        self.grand_total_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.grand_total_label)

        # 📥 Generate PDF Button
        generate_btn = QPushButton("📥 Generate PDF & Save Invoice")
        generate_btn.clicked.connect(self.handle_generate_pdf)
        layout.addWidget(generate_btn)

        self.setLayout(layout)

    def toggle_customer_mode(self):
        """
        Switch between existing customer dropdown and guest customer input.
        """
        if self.customer_type_select.currentText() == "🆕 Guest Customer":
            self.customer_select.hide()
            self.guest_name_input.show()
        else:
            self.guest_name_input.hide()
            self.customer_select.show()

    def get_customer_details(self):
        """
        Return selected/entered customer name and phone (trimmed).
        """
        if self.customer_type_select.currentText() == "🆕 Guest Customer":
            name = self.guest_name_input.text().strip()
            phone = self.customer_phone_input.text().strip()
        else:
            selected_text = self.customer_select.currentText()
            name = selected_text.split(
                " (")[0].strip()  # remove trailing phone
            phone, _ = self.customer_lookup.get(selected_text, ("", ""))
        return name, phone

    def handle_generate_pdf(self):
        """
        Decide whether to generate normal or GST invoice PDF
        based on billing type selection.
        """
        selected_type = self.billing_type.currentText()
        if selected_type == "GST Bill":
            self.generate_pdf_tax()
        else:
            self.generate_pdf_normal()

    def load_customer_options(self):
        """
        Load customer names into dropdown.
        """
        self.customer_lookup = {}  # name -> (phone, address)
        self.customer_select.clear()
        customers = get_all_customers()
        for cust in customers:
            name, phone, address, *_ = cust
            display_text = f"{name} ({phone})"
            self.customer_select.addItem(display_text)
            self.customer_lookup[display_text] = (phone, address)
        self.customer_select.addItem("➕ Add New Guest Customer")

    def customer_changed(self):
        """
        Auto-fill phone for selected customer or allow adding guest.
        """
        selected_text = self.customer_select.currentText()
        if selected_text == "➕ Add New Guest Customer":
            self.customer_phone_input.setText("")
        elif selected_text in self.customer_lookup:
            phone, _ = self.customer_lookup[selected_text]
            self.customer_phone_input.setText(phone)

    def load_item_options(self):
        """
        Load stock items into dropdown, excluding items with zero stock.
        """
        items = get_consolidated_stock()
        self.item_lookup = {}
        self.item_search.clear()
        for row in items:
            # Adjust index if stock quantity is in a different column
            stock_qty = row[7]
            if stock_qty > 0:  # ✅ Only include items with stock > 0
                display_text = f"{row[2]} - {row[1]}"  # Code - Name
                self.item_search.addItem(display_text)
                self.item_lookup[display_text] = row

    def add_item_to_invoice(self):
        """
        Add selected item after checking stock availability.
        """
        selected_text = self.item_search.currentText()
        if selected_text not in self.item_lookup:
            QMessageBox.warning(self, "Invalid Item",
                                "⚠️ Please select a valid item.")
            return

        try:
            qty = int(self.qty_input.text().strip())
            if qty <= 0:
                raise ValueError("Quantity must be positive.")
        except Exception:
            QMessageBox.warning(self, "Invalid Quantity",
                                "⚠️ Enter a valid quantity.")
            return

        item = self.item_lookup[selected_text]
        available_qty = item[7]  # Total available qty

        if qty > available_qty:
            QMessageBox.warning(
                self,
                "Stock Error",
                f"⚠️ Only {available_qty} units of '{item[1]}' are available. Please reduce quantity."
            )
            return

        name, rate, gst = item[1], item[6], item[5]
        total = rate * qty

        row_pos = self.invoice_table.rowCount()
        self.invoice_table.insertRow(row_pos)
        self.invoice_table.setItem(row_pos, 0, QTableWidgetItem(name))
        self.invoice_table.setItem(row_pos, 1, QTableWidgetItem(str(qty)))
        self.invoice_table.setItem(row_pos, 2, QTableWidgetItem(f"{rate:.2f}"))
        self.invoice_table.setItem(row_pos, 3, QTableWidgetItem(f"{gst}%"))
        self.invoice_table.setItem(
            row_pos, 4, QTableWidgetItem(f"{total:.2f}"))

        self.invoice_items.append({
            "code": item[2], "name": name, "hsn": item[4], "gst": gst,
            "price": rate, "qty": qty, "total": total
        })
        self.update_invoice_total()
        self.qty_input.clear()

    def update_invoice_total(self):
        """
        Update total, GST total, and Grand Total display.
        """
        item_total = sum(item['total'] for item in self.invoice_items)
        grand_total = item_total
        gst_total = 0.0

        if self.billing_type.currentText() == "GST Bill":
            # Calculate GST Total
            gst_total = sum(item['total'] * (item['gst'] / 100)
                            for item in self.invoice_items)
            grand_total += gst_total

            # Show both Item Total and GST Total
            self.total_label.setText(f"💰 Item Total: ₹{item_total:.2f}")
            self.gst_total_label.setText(f"🧾 GST Total: ₹{gst_total:.2f}")
            self.gst_total_label.setVisible(True)
        else:
            # Hide GST Total for Normal Bill
            self.total_label.setText(f"💰 Total: ₹{item_total:.2f}")
            self.gst_total_label.setVisible(False)

        # Always show Grand Total in bold
        self.grand_total_label.setText(f"💳 Grand Total: ₹{grand_total:.2f}")
        self.grand_total_label.setVisible(True)

    def generate_pdf_tax(self):
        """
        Generate a professional GST-compliant Tax Invoice:
        - Includes Invoice No and Date in header
        - Proper logo with fallback
        - Clean professional layout
        """
        from reportlab.lib.units import mm
        import os
        import datetime

        try:
            # 🏢 Load company profile
            profile = get_company_profile()
            company_name = profile.get('name', "Dummy Company Pvt Ltd")
            gst_no = profile.get('gst_no', "27ABCDE1234F1Z5")
            address = profile.get('address', "123 Example Street, Test City")
            email = profile.get('email', "info@dummy.com")
            phone1 = profile.get('phone1', "+91-9876543210")
            phone2 = profile.get('phone2', "+91-9123456789")
            logo_path = profile.get('logo_path')

            # ✅ Fallback logo if not set or missing
            fallback_logo = os.path.abspath("data/logos/rayani_logo.png")
            if not logo_path or not os.path.exists(logo_path):
                print(
                    f"⚠️ Company logo missing, using fallback: {fallback_logo}")
                logo_path = fallback_logo
            else:
                logo_path = os.path.abspath(logo_path)
                print(f"✅ Using company logo: {logo_path}")

            # 🧑 Customer details
            customer_name, customer_phone = self.get_customer_details()

            if not customer_name or not self.invoice_items:
                QMessageBox.warning(
                    self, "Missing Data",
                    "⚠️ Please select a customer and add at least one invoice item."
                )
                return

            # Save customer
            customer_id = save_customer(customer_name, customer_phone, "")
            invoice_no = get_next_invoice_number()
            invoice_date = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")

            # 🧮 Calculate Totals
            item_total = sum(item['total'] for item in self.invoice_items)
            tax_total = sum(
                (item['total'] * item['gst'] / 100) for item in self.invoice_items
            )
            grand_total = item_total + tax_total

            paid_amount = float(self.paid_amount_input.text().strip() or 0.0)
            balance = grand_total - paid_amount
            status = "Paid" if balance <= 0 else (
                "Partial" if paid_amount > 0 else "Unpaid")

            # Save invoice to DB
            save_invoice(
                customer_id=customer_id,
                total_amount=grand_total,
                paid_amount=paid_amount,
                balance=balance,
                payment_method="Cash",
                status=status,
                items=self.invoice_items
            )

            # 📄 Generate PDF
            filename = f"Invoice_{invoice_no}.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4

            # --- Header with Logo and Company Info ---
            if os.path.exists(logo_path):
                try:
                    c.drawImage(
                        logo_path, 30, height - 90,
                        width=40 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask='auto'
                    )
                except Exception as logo_err:
                    print(f"⚠️ Failed to load logo: {logo_err}")

            c.setFont("Helvetica-Bold", 16)
            c.drawString(120, height - 50, company_name)

            c.setFont("Helvetica", 9)
            c.drawString(120, height - 65, address)
            c.drawString(120, height - 78, f"GSTIN: {gst_no}")
            c.drawString(120, height - 91, f"Phone: {phone1}, {phone2}")
            c.drawString(120, height - 104, f"Email: {email}")

            # --- Invoice Header Info (Invoice No and Date) ---
            c.setFont("Helvetica-Bold", 11)
            c.drawRightString(width - 40, height - 50,
                              f"Invoice No: {invoice_no}")
            c.drawRightString(width - 40, height - 65, f"Date: {invoice_date}")

            # --- Customer Info ---
            y = height - 130
            c.setFont("Helvetica-Bold", 11)
            c.drawString(30, y, "Billed To:")
            c.setFont("Helvetica", 10)
            c.drawString(100, y, customer_name)
            c.drawString(100, y - 15, f"Phone: {customer_phone}")

            # --- Table Header ---
            y -= 40
            c.setFillColor(colors.lightgrey)
            c.rect(30, y, width - 60, 20, fill=True, stroke=False)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)

            columns = ["S.No", "Item Name", "Qty", "Unit", "HSN Code",
                       "Price", "Tax %", "Tax Amt", "Amount"]
            col_positions = [35, 70, 200, 240, 290, 350, 400, 450, 510]
            for idx, col in enumerate(columns):
                c.drawString(col_positions[idx], y + 5, col)

            # --- Table Content ---
            y -= 20
            c.setFont("Helvetica", 10)
            for idx, item in enumerate(self.invoice_items, start=1):
                tax_amount_line = item['total'] * (item['gst'] / 100)
                line_total = item['total'] + tax_amount_line

                c.drawString(col_positions[0], y, str(idx))
                c.drawString(col_positions[1], y, item['name'])
                c.drawString(col_positions[2], y, str(item['qty']))
                c.drawString(col_positions[3], y, item.get('unit', 'Nos'))
                c.drawString(col_positions[4], y, item.get('hsn', ''))
                c.drawString(col_positions[5], y, f"{item['price']:.2f}")
                c.drawString(col_positions[6], y, f"{item['gst']}%")
                c.drawString(col_positions[7], y, f"{tax_amount_line:.2f}")
                c.drawString(col_positions[8], y, f"{line_total:.2f}")
                y -= 15

                if y < 100:
                    c.showPage()
                    y = height - 140

            # --- Totals Section ---
            y -= 20
            c.setFont("Helvetica-Bold", 11)
            c.drawString(400, y, "Item Total:")
            c.drawRightString(width - 40, y, f"₹{item_total:.2f}")

            y -= 15
            c.drawString(400, y, "Total Tax:")
            c.drawRightString(width - 40, y, f"₹{tax_total:.2f}")

            y -= 15
            c.setFont("Helvetica-Bold", 12)
            c.drawString(400, y, "Grand Total:")
            c.drawRightString(width - 40, y, f"₹{grand_total:.2f}")

            # --- Amount in Words ---
            amount_in_words = num2words(
                grand_total, lang='en_IN').title() + " Only"
            y -= 20
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(30, y, f"Amount in Words: {amount_in_words}")

            # Footer
            y -= 40
            c.setFont("Helvetica", 9)
            c.drawString(30, y, "Thank you for your business!")
            c.save()

            QMessageBox.information(
                self, "✅ Success", f"Invoice saved as {filename}"
            )

            # Reset UI
            self.invoice_table.setRowCount(0)
            self.invoice_items.clear()
            self.update_invoice_total()
            self.paid_amount_input.clear()

        except Exception as e:
            print(f"❌ Exception during PDF generation: {e}")
            QMessageBox.warning(
                self, "❌ Error", f"Failed to generate PDF: {e}"
            )

    def generate_pdf_normal(self):
        """
        Generate a professional retail invoice:
        - Includes Invoice No and Date in header
        - Clean layout with fallback logo
        """
        from reportlab.lib.units import mm
        import os
        import datetime

        try:
            # 🏢 Load company profile
            profile = get_company_profile()
            company_name = profile.get('name', "Dummy Company Pvt Ltd")
            gst_no = profile.get('gst_no', "27ABCDE1234F1Z5")
            address = profile.get('address', "123 Example Street, Test City")
            email = profile.get('email', "info@dummy.com")
            phone1 = profile.get('phone1', "+91-9876543210")
            phone2 = profile.get('phone2', "+91-9123456789")
            logo_path = profile.get('logo_path')

            # ✅ Fallback logo if not set or missing
            fallback_logo = os.path.abspath("data/logos/rayani_logo.png")
            if not logo_path or not os.path.exists(logo_path):
                print(
                    f"⚠️ Company logo missing, using fallback: {fallback_logo}")
                logo_path = fallback_logo
            else:
                logo_path = os.path.abspath(logo_path)
                print(f"✅ Using company logo: {logo_path}")

            # 🧑 Customer details
            customer_name, customer_phone = self.get_customer_details()

            if not customer_name or not self.invoice_items:
                QMessageBox.warning(
                    self, "Missing Data",
                    "⚠️ Please select a customer and add at least one invoice item."
                )
                return

            # Save customer
            customer_id = save_customer(customer_name, customer_phone, "")
            invoice_no = get_next_invoice_number()
            invoice_date = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")

            # 🧮 Totals
            grand_total = sum(item['total'] for item in self.invoice_items)
            paid_amount = float(self.paid_amount_input.text().strip() or 0.0)
            balance = grand_total - paid_amount
            status = "Paid" if balance <= 0 else (
                "Partial" if paid_amount > 0 else "Unpaid")

            # Save invoice to DB
            save_invoice(
                customer_id=customer_id,
                total_amount=grand_total,
                paid_amount=paid_amount,
                balance=balance,
                payment_method="Cash",
                status=status,
                items=self.invoice_items
            )

            # 📄 Generate PDF
            filename = f"Invoice_{invoice_no}.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4

            # --- Header with Logo and Company Info ---
            if os.path.exists(logo_path):
                try:
                    c.drawImage(
                        logo_path, 30, height - 90,
                        width=40 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask='auto'
                    )
                except Exception as logo_err:
                    print(f"⚠️ Failed to load logo: {logo_err}")

            c.setFont("Helvetica-Bold", 16)
            c.drawString(120, height - 50, company_name)

            c.setFont("Helvetica", 9)
            c.drawString(120, height - 65, address)
            c.drawString(120, height - 78, f"GSTIN: {gst_no}")
            c.drawString(120, height - 91, f"Phone: {phone1}, {phone2}")
            c.drawString(120, height - 104, f"Email: {email}")

            # --- Invoice Header Info (Invoice No and Date) ---
            c.setFont("Helvetica-Bold", 11)
            c.drawRightString(width - 40, height - 50,
                              f"Invoice No: {invoice_no}")
            c.drawRightString(width - 40, height - 65, f"Date: {invoice_date}")

            # --- Customer Info ---
            y = height - 130
            c.setFont("Helvetica-Bold", 11)
            c.drawString(30, y, "Billed To:")
            c.setFont("Helvetica", 10)
            c.drawString(100, y, customer_name)
            c.drawString(100, y - 15, f"Phone: {customer_phone}")

            # --- Table Header ---
            y -= 40
            c.setFillColor(colors.lightgrey)
            c.rect(30, y, width - 60, 20, fill=True, stroke=False)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)

            columns = ["S.No", "Item Name", "Qty", "Unit", "Price", "Amount"]
            col_positions = [35, 70, 200, 260, 340, 420]
            for idx, col in enumerate(columns):
                c.drawString(col_positions[idx], y + 5, col)

            # --- Table Content ---
            y -= 20
            c.setFont("Helvetica", 10)
            for idx, item in enumerate(self.invoice_items, start=1):
                c.drawString(col_positions[0], y, str(idx))
                c.drawString(col_positions[1], y, item['name'])
                c.drawString(col_positions[2], y, str(item['qty']))
                c.drawString(col_positions[3], y, item.get('unit', 'Nos'))
                c.drawString(col_positions[4], y, f"{item['price']:.2f}")
                c.drawString(col_positions[5], y, f"{item['total']:.2f}")
                y -= 15

                if y < 100:
                    c.showPage()
                    y = height - 140

            # --- Totals Section ---
            y -= 20
            c.setFont("Helvetica-Bold", 12)
            c.drawString(400, y, "Grand Total:")
            c.drawRightString(width - 40, y, f"₹{grand_total:.2f}")

            # --- Amount in Words ---
            amount_in_words = num2words(
                grand_total, lang='en_IN').title() + " Only"
            y -= 20
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(30, y, f"Amount in Words: {amount_in_words}")

            # Footer
            y -= 40
            c.setFont("Helvetica", 9)
            c.drawString(30, y, "Thank you for your business!")
            c.save()

            QMessageBox.information(
                self, "✅ Success", f"Invoice saved as {filename}"
            )

            # Reset UI
            self.invoice_table.setRowCount(0)
            self.invoice_items.clear()
            self.update_invoice_total()
            self.paid_amount_input.clear()

        except Exception as e:
            print(f"❌ Exception during PDF generation: {e}")
            QMessageBox.warning(
                self, "❌ Error", f"Failed to generate PDF: {e}"
            )
