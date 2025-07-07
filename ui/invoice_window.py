from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QComboBox, QCompleter
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

        # 🧑 Customer Details
        customer_layout = QHBoxLayout()

        self.customer_select = QComboBox()
        self.customer_select.setEditable(True)
        self.load_customer_options()
        self.customer_select.currentIndexChanged.connect(self.customer_changed)

        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("📞 Phone")
        customer_layout.addWidget(self.customer_select)
        customer_layout.addWidget(self.customer_phone_input)
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
        self.qty_input.returnPressed.connect(
            self.add_item_to_invoice)  # ⏎ Press Enter to add
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

        # 💵 Payment & Billing Type
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

        # 💰 Total Label (Big Bold Font)
        self.total_label = QLabel("💰 Total: ₹0.00")
        self.total_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.total_label)

        # 💸 GST Total Label (Hidden by default)
        self.gst_total_label = QLabel("GST Total: ₹0.00")
        self.gst_total_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.gst_total_label.setVisible(False)  # Hide initially
        layout.addWidget(self.gst_total_label)

        # 💳 Grand Total Label (Always visible)
        self.grand_total_label = QLabel("💳 Grand Total: ₹0.00")
        self.grand_total_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.grand_total_label)

        # 📥 Generate PDF Button
        generate_btn = QPushButton("📥 Generate PDF & Save Invoice")
        generate_btn.clicked.connect(self.generate_pdf)
        layout.addWidget(generate_btn)

        self.setLayout(layout)

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
        Load stock items into dropdown.
        """
        items = get_consolidated_stock()
        self.item_lookup = {}
        self.item_search.clear()
        for row in items:
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

    def generate_pdf(self):
        """
        Generate Professional PDF Invoice with:
        - Page numbers fixed (no overlap)
        - Font size consistent
        - Item S.No. column added
        """

        try:
            # ✅ Customer details
            selected_customer = self.customer_select.currentText().split(" (")[
                0]

            if selected_customer != "➕ Add New Guest Customer" and selected_customer in self.customer_lookup:
                # ✅ Existing customer in DB
                customer_phone, customer_address, customer_gst_no = self.customer_lookup[
                    selected_customer]
                customer_name = selected_customer

                # If no GST in DB, leave blank
                customer_gst_no = customer_gst_no if customer_gst_no else ""
                customer_address = customer_address if customer_address else ""
            else:
                # 🆕 New Guest customer
                customer_name = self.customer_select.currentText()
                customer_phone = self.customer_phone_input.text().strip()
                customer_address = self.customer_address_input.text().strip() if hasattr(self,
                                                                                         "customer_address_input") else ""
                customer_gst_no = self.customer_gst_input.text().strip() if hasattr(self,
                                                                                    "customer_gst_input") else ""

            # Save customer
            customer_id = save_customer(
                customer_name, customer_phone, customer_address)

            # Totals
            billing_type = self.billing_type.currentText()
            total_amount = sum(item['total'] for item in self.invoice_items)
            gst_total = 0.0

            if billing_type == "GST Bill":
                gst_total = sum(item['total'] * (item['gst'] / 100)
                                for item in self.invoice_items)
                total_amount += gst_total

            paid_amount = float(self.paid_amount_input.text().strip() or 0.0)
            balance = total_amount - paid_amount
            status = "Paid" if balance <= 0 else (
                "Partial" if paid_amount > 0 else "Unpaid")
            payment_method = "Cash"

            # Save invoice to DB
            invoice_no = get_next_invoice_number()
            save_invoice(
                customer_id=customer_id,
                total_amount=total_amount,
                paid_amount=paid_amount,
                balance=balance,
                payment_method=payment_method,
                status=status,
                items=self.invoice_items
            )

            for item in self.invoice_items:
                reduce_stock_quantity(item['code'], item['qty'])

            # Generate PDF
            filename = f"Invoice_{invoice_no}.pdf"
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4

            # --- PAGE FRAME FUNCTION ---
            def draw_page_frame(page_num, total_pages):
                # Border
                c.setStrokeColor(colors.black)
                c.rect(20, 20, width - 40, height - 40, stroke=True, fill=0)

                # Header
                logo_path = "data/logos/rayani_logo.png"
                c.drawImage(logo_path, 35, height - 90,
                            width=70, height=50, mask='auto')

                c.setFont("Helvetica-Bold", 16)
                c.drawString(120, height - 50, "RAYANI ENGINEERING")
                c.setFont("Helvetica", 10)
                c.drawString(120, height - 65, "123 Example Street, Your City")
                c.drawString(120, height - 80,
                             "Phone: +91-9876543210 | GSTIN: 27ABCDE1234F1Z5")

                # Invoice Details
                c.setFont("Helvetica-Bold", 11)
                c.drawRightString(width - 40, height - 50,
                                  f"Invoice No: {invoice_no}")
                c.setFont("Helvetica", 10)
                c.drawRightString(width - 40, height - 65,
                                  f"Date: {datetime.date.today()}")

                # Page number bottom-left (fixed position)
                c.setFont("Helvetica", 8)
                c.drawString(30, 30, f"Page {page_num} of {total_pages}")

            # Precalculate total pages
            items_per_page = 20
            total_pages = ((len(self.invoice_items) - 1) // items_per_page) + 1
            page_num = 1

            draw_page_frame(page_num, total_pages)

            # --- CUSTOMER INFO ---
            y = height - 120
            c.setFont("Helvetica-Bold", 10)
            c.drawString(35, y, "Billed To:")
            c.setFont("Helvetica", 10)
            c.drawString(110, y, customer_name)
            if customer_address:
                c.drawString(110, y - 15, f"Address: {customer_address}")
            if customer_gst_no:
                c.drawString(110, y - 30, f"GST No: {customer_gst_no}")
            if customer_phone:
                c.drawString(110, y - 45, f"Phone: {customer_phone}")
            y -= 70

            # --- TABLE HEADER FUNCTION ---
            def draw_table_header(y_pos):
                c.setFillColor(colors.lightgrey)
                c.rect(30, y_pos, width - 60, 20, fill=True, stroke=False)
                c.setFillColor(colors.black)
                c.setFont("Helvetica-Bold", 10)

                if billing_type == "GST Bill":
                    c.drawString(35, y_pos + 5, "S.No.")
                    c.drawString(65, y_pos + 5, "Item Name")
                    c.drawString(200, y_pos + 5, "Unit")
                    c.drawString(250, y_pos + 5, "HSN Code")
                    c.drawString(320, y_pos + 5, "Qty")
                    c.drawString(370, y_pos + 5, "Rate (₹)")
                    c.drawString(440, y_pos + 5, "GST (₹ + %)")
                    c.drawString(530, y_pos + 5, "Total (₹)")
                else:
                    c.drawString(35, y_pos + 5, "S.No.")
                    c.drawString(65, y_pos + 5, "Item Name")
                    c.drawString(300, y_pos + 5, "Unit")
                    c.drawString(350, y_pos + 5, "Qty")
                    c.drawString(400, y_pos + 5, "Rate (₹)")
                    c.drawString(480, y_pos + 5, "Total (₹)")

            draw_table_header(y)

            # --- TABLE CONTENT ---
            y -= 20
            c.setFont("Helvetica", 10)
            for idx, item in enumerate(self.invoice_items, 1):
                c.drawString(35, y, str(idx))  # S.No.
                c.drawString(65, y, item['name'])
                if billing_type == "GST Bill":
                    c.drawString(200, y, item.get('unit', 'Pcs'))
                    c.drawString(250, y, item['hsn'])
                    c.drawString(320, y, str(item['qty']))
                    c.drawString(370, y, f"{item['price']:.2f}")
                    gst_value = item['total'] * (item['gst'] / 100)
                    gst_text = f"₹{gst_value:.2f} ({item['gst']}%)"
                    c.drawString(440, y, gst_text)
                    c.drawString(530, y, f"{item['total']:.2f}")
                else:
                    c.drawString(300, y, item.get('unit', 'Pcs'))
                    c.drawString(350, y, str(item['qty']))
                    c.drawString(400, y, f"{item['price']:.2f}")
                    c.drawString(480, y, f"{item['total']:.2f}")

                y -= 15
                if y < 100 and idx < len(self.invoice_items):
                    c.showPage()
                    page_num += 1
                    draw_page_frame(page_num, total_pages)
                    y = height - 140
                    draw_table_header(y)
                    y -= 20

            # --- TOTALS ---
            y -= 10
            c.line(30, y, width - 30, y)
            y -= 15

            if billing_type == "GST Bill":
                c.drawString(400, y, "GST Total:")
                c.drawRightString(width - 40, y, f"{gst_total:.2f}")
                y -= 15

            c.setFont("Helvetica-Bold", 12)
            c.drawString(350, y, "Grand Total (₹):")
            c.drawRightString(width - 40, y, f"{total_amount:.2f}")
            y -= 20

            # ✅ Amount in words
            amount_in_words = num2words(
                total_amount, lang='en_IN').title() + " Only"
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(30, y, f"Amount in Words: {amount_in_words}")

            # --- TERMS & SIGNATURE ---
            y -= 40
            c.setFont("Helvetica-Bold", 10)
            c.drawString(30, y, "Terms & Conditions:")
            c.setFont("Helvetica", 9)
            y -= 15
            c.drawString(
                40, y, "1. Goods once Sold cannot be taken back or exchanged.")
            y -= 12
            c.drawString(
                40, y, "2. Interest @ 24% p.a. will be charged for uncleared bills beyond 7 days.")
            y -= 12
            c.drawString(40, y, "3. Subject to local jurisdiction.")

            c.setFont("Helvetica", 10)
            c.drawString(width - 180, 60, "For RAYANI ENGINEERING")
            c.line(width - 180, 50, width - 40, 50)
            c.drawString(width - 130, 35, "Authorized Signatory")

            # --- FOOTER ---
            # c.setFont("Helvetica-Oblique", 8)
            # c.drawString(30, 30, "Thank you for your business!")

            c.save()

            QMessageBox.information(
                self, "Success", f"✅ Professional PDF Invoice saved as {filename}")

            # Reset for new invoice
            self.invoice_table.setRowCount(0)
            self.invoice_items.clear()
            self.update_invoice_total()
            self.paid_amount_input.clear()

        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to generate PDF: {e}")
