import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QMessageBox, QComboBox, QCompleter, QFormLayout, QHeaderView
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt # <-- FIXED: Added missing import
from models.invoice_model import get_invoice_details_by_no, get_invoice_items_by_no, update_full_invoice, cancel_invoice
from models.stock_model import get_consolidated_stock, reduce_stock_quantity, increase_stock_quantity

class FullEditInvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edit Full Invoice")
        self.setGeometry(200, 100, 1000, 700)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.original_items = {}
        self.current_invoice_data = {}
        self.item_lookup = {}
        self.is_tax_invoice = False
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)

        # Search Section
        search_layout = QHBoxLayout()
        self.invoice_no_input = QLineEdit()
        self.invoice_no_input.setPlaceholderText("Enter Invoice No. to Edit (e.g., INV-...)")
        self.fetch_btn = QPushButton("🔍 Fetch Invoice")
        self.fetch_btn.clicked.connect(self.fetch_invoice_data)
        search_layout.addWidget(self.invoice_no_input)
        search_layout.addWidget(self.fetch_btn)
        self.main_layout.addLayout(search_layout)

        # Read-only Details
        self.info_form = QFormLayout()
        self.customer_name_label = QLabel("N/A")
        self.invoice_date_label = QLabel("N/A")
        self.info_form.addRow("<b>Customer:</b>", self.customer_name_label)
        self.info_form.addRow("<b>Invoice Date:</b>", self.invoice_date_label)
        self.main_layout.addLayout(self.info_form)

        # Items Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(["Code", "Item Name", "Qty", "Rate (Rs.)", "GST %", "Total (Rs.)"])
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.itemChanged.connect(self.update_totals)
        self.main_layout.addWidget(self.items_table)
        
        # Add/Remove Item Buttons
        item_actions_layout = QHBoxLayout()
        self.delete_item_btn = QPushButton("➖ Remove Selected Item")
        self.delete_item_btn.clicked.connect(self.delete_selected_item)
        item_actions_layout.addStretch()
        item_actions_layout.addWidget(self.delete_item_btn)
        self.main_layout.addLayout(item_actions_layout)

        # Add New Item Section
        add_item_layout = QHBoxLayout()
        self.item_search = QComboBox()
        self.load_item_options()
        self.item_search.setEditable(True)
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("Qty")
        self.add_item_btn = QPushButton("➕ Add Item")
        self.add_item_btn.clicked.connect(self.add_item_to_invoice)
        add_item_layout.addWidget(QLabel("Add New Item:"))
        add_item_layout.addWidget(self.item_search, 2)
        add_item_layout.addWidget(self.qty_input, 1)
        add_item_layout.addWidget(self.add_item_btn)
        self.main_layout.addLayout(add_item_layout)

        # Editable Footer Form
        self.footer_form = QFormLayout()
        self.discount_edit = QLineEdit("0")
        self.paid_amount_edit = QLineEdit("0")
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Paid", "Partial", "Unpaid", "Cancelled"])
        self.remarks_edit = QLineEdit()
        self.footer_form.addRow("Discount (Rs.):", self.discount_edit)
        self.footer_form.addRow("Paid Amount (Rs.):", self.paid_amount_edit)
        self.footer_form.addRow("Payment Status:", self.status_combo)
        self.footer_form.addRow("Remarks:", self.remarks_edit)
        self.main_layout.addLayout(self.footer_form)
        
        self.discount_edit.textChanged.connect(self.update_totals)
        self.paid_amount_edit.textChanged.connect(self.update_totals)

        # Total Labels
        self.total_label = QLabel("Subtotal: Rs. 0.00")
        self.gst_total_label = QLabel("GST Total: Rs. 0.00")
        self.grand_total_label = QLabel("<b>Grand Total: Rs. 0.00</b>")
        self.balance_label = QLabel("<b>Balance Due: Rs. 0.00</b>")
        self.main_layout.addWidget(self.total_label)
        self.main_layout.addWidget(self.gst_total_label)
        self.main_layout.addWidget(self.grand_total_label)
        self.main_layout.addWidget(self.balance_label)

        # --- Action Buttons ---
        action_layout = QHBoxLayout()
        self.update_btn = QPushButton("💾 Save All Changes")
        self.update_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.update_btn.clicked.connect(self.save_all_changes)
        
        self.cancel_btn = QPushButton("❌ Cancel Invoice")
        self.cancel_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.cancel_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self.cancel_btn.clicked.connect(self.handle_cancel_invoice)

        action_layout.addWidget(self.update_btn)
        action_layout.addWidget(self.cancel_btn)
        self.main_layout.addLayout(action_layout)

        self.set_fields_enabled(False)
        self.reset_form()

    def set_fields_enabled(self, enabled, is_cancelled=False):
        if is_cancelled:
            enabled = False
        
        for widget in [self.items_table, self.delete_item_btn, self.item_search, 
                       self.qty_input, self.add_item_btn, self.discount_edit, 
                       self.paid_amount_edit, self.remarks_edit, 
                       self.update_btn, self.cancel_btn]:
            widget.setEnabled(enabled)
        self.status_combo.setEnabled(enabled)

    def load_item_options(self):
        self.item_lookup.clear()
        self.item_search.clear()
        items = get_consolidated_stock()
        for row in items:
            display_text = f"{row[2]} - {row[1]}"
            self.item_search.addItem(display_text)
            self.item_lookup[display_text] = row
        completer = QCompleter([self.item_search.itemText(i) for i in range(self.item_search.count())])
        self.item_search.setCompleter(completer)

    def fetch_invoice_data(self):
        invoice_no = self.invoice_no_input.text().strip()
        if not invoice_no: return
        header_data = get_invoice_details_by_no(invoice_no)
        if not header_data:
            QMessageBox.critical(self, "Not Found", f"No invoice found with number '{invoice_no}'.")
            self.reset_form()
            return
        self.current_invoice_data = header_data
        
        is_cancelled = header_data.get('status') == 'Cancelled'
        
        try:
            invoice_date = datetime.datetime.strptime(header_data['date'], "%Y-%m-%d %H:%M:%S")
            is_too_old = (datetime.datetime.now() - invoice_date) > datetime.timedelta(days=3)

            if is_too_old and not is_cancelled:
                QMessageBox.warning(self, "Editing Locked", "This invoice is older than 3 days and cannot be fully edited. Only status can be changed.")
                self.populate_form(is_editable=False)
                self.status_combo.setEnabled(True)
                self.update_btn.setEnabled(True)
                self.cancel_btn.setEnabled(True)
                return
            elif is_cancelled:
                 QMessageBox.information(self, "Cancelled", "This invoice has been cancelled. No edits are allowed.")
                 self.populate_form(is_editable=False, is_cancelled=True)
                 return

        except (ValueError, TypeError):
            QMessageBox.critical(self, "Date Error", "Could not parse the invoice date.")
            self.reset_form()
            return
        self.populate_form(is_editable=True)

    def populate_form(self, is_editable, is_cancelled=False):
        data = self.current_invoice_data
        self.customer_name_label.setText(data.get('customer_name', 'N/A'))
        self.invoice_date_label.setText(data.get('date', 'N/A'))
        self.paid_amount_edit.setText(str(data.get('paid_amount', '0.0')))
        self.remarks_edit.setText(data.get('remarks', ''))
        self.discount_edit.setText(str(data.get('discount', '0.0')))
        
        status_index = self.status_combo.findText(data.get('status', 'Unpaid'))
        if status_index != -1: self.status_combo.setCurrentIndex(status_index)
        
        self.items_table.setRowCount(0)
        self.original_items = {}
        items = get_invoice_items_by_no(data['invoice_no'])
        self.is_tax_invoice = any((item.get('gst_percent') or 0) > 0 for item in items)
        
        for item in items:
            self.add_item_to_table(item)
            code = item['item_code']
            self.original_items[code] = self.original_items.get(code, 0) + item['qty']
        
        self.items_table.setColumnHidden(4, not self.is_tax_invoice)
        self.gst_total_label.setVisible(self.is_tax_invoice)
        self.set_fields_enabled(is_editable, is_cancelled)
        self.update_totals()

    def add_item_to_table(self, item_data):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        item_data['total'] = item_data.get('price', 0) * item_data.get('qty', 0)
        for col, key in enumerate(['item_code', 'item_name', 'qty', 'price', 'gst_percent', 'total']):
            val = item_data.get(key, 0)
            if key in ['price', 'total']: val = f"{val:.2f}"
            item = QTableWidgetItem(str(val))
            if key in ['item_code', 'item_name', 'total']:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable) # FIXED: NameError
            self.items_table.setItem(row, col, item)

    def add_item_to_invoice(self):
        selected = self.item_search.currentText()
        if selected not in self.item_lookup: return
        try:
            qty = int(self.qty_input.text().strip())
            if qty <= 0: raise ValueError
        except:
            QMessageBox.warning(self, "Invalid Quantity", "Enter a valid quantity.")
            return
        item = self.item_lookup[selected]
        self.add_item_to_table({
            'item_code': item[2], 'item_name': item[1], 'qty': qty, 'price': item[6],
            'gst_percent': item[5] if self.is_tax_invoice else 0, 'hsn_code': item[4]
        })
        self.qty_input.clear()

    def delete_selected_item(self):
        if self.items_table.currentRow() >= 0:
            self.items_table.removeRow(self.items_table.currentRow())
            self.update_totals()
        else:
            QMessageBox.warning(self, "No Selection", "Please select an item to remove.")

    def update_totals(self):
        self.items_table.blockSignals(True)
        subtotal, gst_total = 0.0, 0.0
        for row in range(self.items_table.rowCount()):
            try:
                qty = int(self.items_table.item(row, 2).text())
                rate = float(self.items_table.item(row, 3).text())
                total = qty * rate
                self.items_table.item(row, 5).setText(f"{total:.2f}")
                subtotal += total
                if self.is_tax_invoice:
                    gst = float(self.items_table.item(row, 4).text())
                    gst_total += total * (gst / 100.0)
            except (ValueError, AttributeError): continue
        try: discount = float(self.discount_edit.text() or 0.0)
        except ValueError: discount = 0.0
        grand_total = (subtotal + gst_total) - discount
        try: paid = float(self.paid_amount_edit.text() or 0.0)
        except ValueError: paid = 0.0
        balance = grand_total - paid

        self.total_label.setText(f"Subtotal: Rs. {subtotal:.2f}")
        self.gst_total_label.setText(f"GST Total: Rs. {gst_total:.2f}")
        self.grand_total_label.setText(f"<b>Grand Total: Rs. {grand_total:.2f}</b>")
        self.balance_label.setText(f"<b>Balance Due: Rs. {balance:.2f}</b>")
        self.items_table.blockSignals(False)

    def save_all_changes(self):
        invoice_no = self.current_invoice_data.get('invoice_no')
        if not invoice_no: return

        new_items_qty = {}
        for row in range(self.items_table.rowCount()):
            code = self.items_table.item(row, 0).text()
            qty = int(self.items_table.item(row, 2).text())
            new_items_qty[code] = new_items_qty.get(code, 0) + qty

        stock_adjustments = {c: new_items_qty.get(c, 0) - self.original_items.get(c, 0) 
                             for c in set(self.original_items) | set(new_items_qty)}
        
        try:
            for code, delta in stock_adjustments.items():
                if delta > 0: reduce_stock_quantity(code, delta)
                elif delta < 0: increase_stock_quantity(code, -delta)
        except Exception as e:
            QMessageBox.critical(self, "Stock Error", f"Failed to adjust stock: {e}. Changes not saved.")
            # Revert stock changes on failure
            for code, delta in stock_adjustments.items():
                if delta > 0: increase_stock_quantity(code, delta)
                elif delta < 0: reduce_stock_quantity(code, -delta)
            return

        final_items, subtotal, gst_total = self._get_final_items_and_totals()
        discount = float(self.discount_edit.text() or 0.0)
        paid = float(self.paid_amount_edit.text() or 0.0)
        grand_total = (subtotal + gst_total) - discount
        header_data = {'total_amount': grand_total, 'paid_amount': paid, 'balance': grand_total - paid, 
                       'status': self.status_combo.currentText(), 'remarks': self.remarks_edit.text(), 'discount': discount}

        try:
            update_full_invoice(invoice_no, header_data, final_items)
            QMessageBox.information(self, "Success", f"Invoice '{invoice_no}' has been updated.")
            self.reset_form()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to save changes: {e}")
            
    def _get_final_items_and_totals(self):
        final_items, subtotal, gst_total = [], 0.0, 0.0
        for row in range(self.items_table.rowCount()):
            item = {'item_code': self.items_table.item(row, 0).text(), 'item_name': self.items_table.item(row, 1).text(),
                    'qty': int(self.items_table.item(row, 2).text()), 'price': float(self.items_table.item(row, 3).text()),
                    'gst_percent': float(self.items_table.item(row, 4).text()), 'total': float(self.items_table.item(row, 5).text()), 'hsn_code': ''}
            final_items.append(item)
            subtotal += item['total']
            if self.is_tax_invoice:
                gst_total += item['total'] * (item['gst_percent']/100)
        return final_items, subtotal, gst_total

    def handle_cancel_invoice(self):
        invoice_no = self.current_invoice_data.get('invoice_no')
        if not invoice_no: return
        
        reply = QMessageBox.question(self, 'Confirm Cancellation', 
                                     f"Are you sure you want to cancel invoice '{invoice_no}'?\nThis will return all items to stock.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                cancel_invoice(invoice_no)
                QMessageBox.information(self, "Success", f"Invoice '{invoice_no}' has been cancelled.")
                self.reset_form()
            except Exception as e:
                QMessageBox.critical(self, "Cancellation Failed", f"An error occurred: {e}")

    def reset_form(self):
        for field in [self.invoice_no_input, self.discount_edit, self.paid_amount_edit, self.remarks_edit]: field.clear()
        for label in [self.customer_name_label, self.invoice_date_label]: label.setText("N/A")
        self.items_table.setRowCount(0)
        self.status_combo.setCurrentIndex(0)
        self.current_invoice_data, self.original_items = {}, {}
        self.is_tax_invoice = False
        self.items_table.setColumnHidden(4, True)
        self.gst_total_label.setVisible(False)
        self.update_totals()
        self.set_fields_enabled(False)

