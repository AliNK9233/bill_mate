from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox
)
from PyQt5.QtGui import QIcon
from models.stock_model import (
    get_consolidated_stock, add_stock_item,
    add_stock_batch, get_latest_item_details_by_code
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

        # Search, Add Stock, and Refresh Buttons
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
        top_layout.addWidget(refresh_btn)  # ✅ Added refresh button
        layout.addLayout(top_layout)

        # Stock Table
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(7)
        self.stock_table.setHorizontalHeaderLabels([
            "Item Name", "Item Code", "Unit", "HSN Code", "GST (%)",
            "Selling Price (₹)", "Available Qty"
        ])
        layout.addWidget(self.stock_table)

        self.setLayout(layout)

    def load_stock_data(self):
        self.stock_table.setRowCount(0)
        stock_data = get_consolidated_stock()
        self.full_stock_data = stock_data

        for row_data in stock_data:
            self.add_row_to_table(row_data)

    def add_row_to_table(self, row_data):
        row_position = self.stock_table.rowCount()
        self.stock_table.insertRow(row_position)

        # Consolidated Stock Data
        item_name = row_data[1]
        item_code = row_data[2]
        unit = row_data[3]
        hsn_code = row_data[4]
        gst_percent = row_data[5]
        selling_price = row_data[6] if row_data[6] else 0.0
        available_qty = row_data[7] if row_data[7] else 0

        self.stock_table.setItem(row_position, 0, QTableWidgetItem(item_name))
        self.stock_table.setItem(row_position, 1, QTableWidgetItem(item_code))
        self.stock_table.setItem(row_position, 2, QTableWidgetItem(unit))
        self.stock_table.setItem(row_position, 3, QTableWidgetItem(hsn_code))
        self.stock_table.setItem(
            row_position, 4, QTableWidgetItem(f"{gst_percent}%"))
        self.stock_table.setItem(
            row_position, 5, QTableWidgetItem(f"₹{selling_price:.2f}"))
        self.stock_table.setItem(
            row_position, 6, QTableWidgetItem(str(available_qty)))

    def filter_stock_data(self):
        search_text = self.search_input.text().lower()
        self.stock_table.setRowCount(0)

        for row_data in self.full_stock_data:
            if search_text in row_data[1].lower() or search_text in row_data[2].lower():
                self.add_row_to_table(row_data)

    def add_stock_popup(self):
        """
        Popup to add new stock.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Add Stock Entry")
        form_layout = QFormLayout(dialog)

        code_input = QLineEdit()
        name_input = QLineEdit()
        unit_input = QLineEdit("Pcs")
        hsn_input = QLineEdit()
        gst_input = QLineEdit("18")  # Default GST
        purchase_price_input = QLineEdit()
        selling_price_input = QLineEdit()
        quantity_input = QLineEdit()

        def on_code_changed():
            code = code_input.text().strip().upper()
            if not code:
                return

            # Fetch item details if code exists
            item = get_latest_item_details_by_code(code)
            if item:
                stock_id, name, code, unit, hsn_code, gst_percent, selling_price = item
                name_input.setText(name)
                unit_input.setText(unit)
                hsn_input.setText(hsn_code)
                gst_input.setText(str(gst_percent))
                selling_price_input.setText(
                    str(selling_price) if selling_price else "0.0")
            else:
                name_input.clear()
                unit_input.setText("Pcs")
                hsn_input.clear()
                gst_input.setText("18")
                selling_price_input.setText("0.0")

        code_input.textChanged.connect(on_code_changed)

        form_layout.addRow("Item Code:", code_input)
        form_layout.addRow("Item Name:", name_input)
        form_layout.addRow("Unit:", unit_input)
        form_layout.addRow("HSN Code:", hsn_input)
        form_layout.addRow("GST %:", gst_input)
        form_layout.addRow("Purchase Price (₹):", purchase_price_input)
        form_layout.addRow("Selling Price (₹):", selling_price_input)
        form_layout.addRow("Quantity:", quantity_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                code = code_input.text().strip().upper()
                name = name_input.text().strip()
                unit = unit_input.text().strip()
                hsn_code = hsn_input.text().strip() or ""
                gst_percent = float(gst_input.text().strip())
                purchase_price = float(purchase_price_input.text().strip())
                selling_price = float(selling_price_input.text().strip())
                quantity = int(quantity_input.text().strip())

                if not code or not name:
                    QMessageBox.warning(
                        self, "Validation Error", "⚠️ Item Code and Name are required.")
                    return

                # Check if item code exists
                existing_item = get_latest_item_details_by_code(code)
                if not existing_item:
                    stock_id = add_stock_item(
                        name, code, unit, hsn_code, gst_percent)
                else:
                    stock_id = existing_item[0]

                add_stock_batch(stock_id, purchase_price,
                                selling_price, quantity)
                QMessageBox.information(
                    self, "Success", f"✅ Stock entry added successfully!")
                self.load_stock_data()  # Refresh table
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to add stock entry: {e}")
