from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox
)
from PyQt5.QtWidgets import QDateEdit, QCheckBox
from PyQt5.QtCore import QDate
from PyQt5.QtGui import QIcon
from models.stock_model import (
    get_consolidated_stock, add_item, add_stock, get_item_by_item_code
)


class GeneralStockWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📦 Stock Management (User)")
        self.setGeometry(200, 100, 1000, 600)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setup_ui()
        self.load_stock_data()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("📦 Stock Management")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Search, Add Stock, Refresh
        top_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search Item...")
        self.search_input.textChanged.connect(self.filter_stock_data)

        add_stock_btn = QPushButton("➕ Add Stock")
        add_stock_btn.clicked.connect(self.add_stock_popup)

        refresh_btn = QPushButton("🔄 Refresh Stock")
        refresh_btn.clicked.connect(self.load_stock_data)

        top_layout.addWidget(self.search_input)
        top_layout.addWidget(add_stock_btn)
        top_layout.addWidget(refresh_btn)
        layout.addLayout(top_layout)

        # Stock Table
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(5)
        self.stock_table.setHorizontalHeaderLabels([
            "Item Code", "Item Name", "Unit", "Selling Price (₹)", "Available Qty"
        ])
        layout.addWidget(self.stock_table)

        self.setLayout(layout)

    def load_stock_data(self):
        self.stock_table.setRowCount(0)
        self.full_stock_data = get_consolidated_stock()

        for row in self.full_stock_data:
            # row = (item_code, name, total_qty, uom, selling_price)
            row_pos = self.stock_table.rowCount()
            self.stock_table.insertRow(row_pos)

            self.stock_table.setItem(row_pos, 0, QTableWidgetItem(row[0]))
            self.stock_table.setItem(row_pos, 1, QTableWidgetItem(row[1]))
            self.stock_table.setItem(row_pos, 2, QTableWidgetItem(row[3]))
            self.stock_table.setItem(
                row_pos, 3, QTableWidgetItem(f"₹{row[4]:.2f}"))
            self.stock_table.setItem(row_pos, 4, QTableWidgetItem(str(row[2])))

    def filter_stock_data(self):
        search_text = self.search_input.text().lower()
        self.stock_table.setRowCount(0)

        for row in self.full_stock_data:
            if (search_text in row[0].lower()) or (search_text in row[1].lower()):
                row_pos = self.stock_table.rowCount()
                self.stock_table.insertRow(row_pos)

                self.stock_table.setItem(row_pos, 0, QTableWidgetItem(row[0]))
                self.stock_table.setItem(row_pos, 1, QTableWidgetItem(row[1]))
                self.stock_table.setItem(row_pos, 2, QTableWidgetItem(row[3]))
                self.stock_table.setItem(
                    row_pos, 3, QTableWidgetItem(f"₹{row[4]:.2f}"))
                self.stock_table.setItem(
                    row_pos, 4, QTableWidgetItem(str(row[2])))

    def add_stock_popup(self):
        """
        Popup for adding stock (either new item or new batch).
        Includes optional expiry date (calendar picker).
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Add Stock Entry")
        form_layout = QFormLayout(dialog)

        code_input = QLineEdit()
        name_input = QLineEdit()
        unit_input = QLineEdit("pcs")
        purchase_price_input = QLineEdit()
        selling_price_input = QLineEdit()
        qty_input = QLineEdit()
        vat_input = QLineEdit("5")

        # Expiry controls: checkbox + date picker
        expiry_checkbox = QCheckBox("Has Expiry")
        expiry_input = QDateEdit()
        expiry_input.setCalendarPopup(True)
        expiry_input.setDisplayFormat("yyyy-MM-dd")
        expiry_input.setEnabled(False)  # disabled until checkbox checked
        expiry_input.setDate(QDate.currentDate())

        def on_code_changed():
            code = code_input.text().strip().upper()
            if not code:
                return
            item = get_item_by_item_code(code)
            if item:
                # item = (id, item_code, name, uom, per_box_qty, vat, selling_price, remarks)
                name_input.setText(item[2])
                unit_input.setText(item[3])
                # guard against missing indexes
                try:
                    vat_input.setText(str(item[5]))
                except Exception:
                    vat_input.setText("5")
                try:
                    selling_price_input.setText(str(item[6]))
                except Exception:
                    selling_price_input.setText("0.0")
            else:
                name_input.clear()
                unit_input.setText("pcs")
                vat_input.setText("5")
                selling_price_input.setText("0.0")

        def on_expiry_toggled(state):
            expiry_input.setEnabled(bool(state))

        code_input.textChanged.connect(on_code_changed)
        expiry_checkbox.stateChanged.connect(on_expiry_toggled)

        form_layout.addRow("Item Code:", code_input)
        form_layout.addRow("Item Name:", name_input)
        form_layout.addRow("Unit:", unit_input)
        form_layout.addRow("VAT %:", vat_input)
        form_layout.addRow("Purchase Price:", purchase_price_input)
        form_layout.addRow("Selling Price:", selling_price_input)
        form_layout.addRow("Quantity:", qty_input)

        # Put expiry checkbox and date picker on the same row
        expiry_row = QHBoxLayout()
        expiry_row.addWidget(expiry_checkbox)
        expiry_row.addWidget(expiry_input)
        form_layout.addRow("Expiry (optional):", expiry_row)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                code = code_input.text().strip().upper()
                name = name_input.text().strip()
                uom = unit_input.text().strip()
                vat = float(vat_input.text().strip() or 0)
                purchase_price = float(
                    purchase_price_input.text().strip() or 0)
                selling_price = float(selling_price_input.text().strip() or 0)
                qty = float(qty_input.text().strip() or 0)

                if not code or not name:
                    QMessageBox.warning(
                        self, "Validation Error", "⚠️ Item Code and Name required.")
                    return

                # determine expiry value
                expiry_val = None
                if expiry_checkbox.isChecked() and expiry_input.isEnabled():
                    # Use yyyy-MM-dd format (matches DB expectations)
                    expiry_val = expiry_input.date().toString("yyyy-MM-dd")

                # If item does not exist, add it first
                item = get_item_by_item_code(code)
                if not item:
                    add_item(code, name, uom, vat_percentage=vat,
                             selling_price=selling_price)

                # Add stock batch with expiry_date if provided
                add_stock(code, purchase_price=purchase_price,
                          quantity=qty, expiry_date=expiry_val, stock_type="purchase")

                QMessageBox.information(
                    self, "Success", "✅ Stock entry added successfully.")
                self.load_stock_data()
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to add stock: {e}")
