from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox
)
from PyQt5.QtGui import QIcon
from models.stock_model import get_all_batches, update_item_master, update_batch_details
from openpyxl import Workbook
import datetime


class AdminStockWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📦 Admin Stock Management")
        self.setGeometry(200, 100, 1100, 700)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setup_ui()
        self.load_full_stock()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("📦 Admin Stock Management")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search Item...")
        self.search_input.textChanged.connect(self.filter_stock_data)

        edit_master_btn = QPushButton("✏️ Edit Master Data")
        edit_master_btn.clicked.connect(self.edit_master_data)

        edit_batch_btn = QPushButton("✏️ Edit Batch Details")
        edit_batch_btn.clicked.connect(self.edit_batch_data)

        export_btn = QPushButton("📥 Export to Excel")
        export_btn.clicked.connect(self.export_to_excel)

        button_layout.addWidget(self.search_input)
        button_layout.addWidget(edit_master_btn)
        button_layout.addWidget(edit_batch_btn)
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)

        # Full Stock Table
        self.full_stock_table = QTableWidget()
        self.full_stock_table.setColumnCount(9)
        self.full_stock_table.setHorizontalHeaderLabels([
            "Item Code", "Item Name", "Unit", "HSN Code", "GST (%)",
            "Purchase Price (₹)", "Sell Price (₹)", "Available Qty", "Batch Date"
        ])
        layout.addWidget(self.full_stock_table)

        self.setLayout(layout)

    def load_full_stock(self):
        self.full_stock_table.setRowCount(0)
        self.full_stock_data = get_all_batches()

        for row in self.full_stock_data:
            row_pos = self.full_stock_table.rowCount()
            self.full_stock_table.insertRow(row_pos)

            for col, value in enumerate(row):
                self.full_stock_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))

    def filter_stock_data(self):
        search_text = self.search_input.text().lower()
        self.full_stock_table.setRowCount(0)

        for row in self.full_stock_data:
            if (search_text in row[0].lower()) or (search_text in row[1].lower()) or (search_text in row[3].lower()):
                row_pos = self.full_stock_table.rowCount()
                self.full_stock_table.insertRow(row_pos)

                for col, value in enumerate(row):
                    self.full_stock_table.setItem(
                        row_pos, col, QTableWidgetItem(str(value)))

    def edit_master_data(self):
        selected_row = self.full_stock_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Select Item",
                                "⚠️ Please select an item to edit.")
            return

        item_code = self.full_stock_table.item(selected_row, 0).text()
        item_name = self.full_stock_table.item(selected_row, 1).text()
        unit = self.full_stock_table.item(selected_row, 2).text()
        hsn = self.full_stock_table.item(selected_row, 3).text()
        gst = self.full_stock_table.item(
            selected_row, 4).text().replace("%", "")

        # Edit popup
        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Master Data")
        form_layout = QFormLayout(dialog)

        name_input = QLineEdit(item_name)
        unit_input = QLineEdit(unit)
        hsn_input = QLineEdit(hsn)
        gst_input = QLineEdit(gst)

        form_layout.addRow("Item Name:", name_input)
        form_layout.addRow("Unit:", unit_input)
        form_layout.addRow("HSN Code:", hsn_input)
        form_layout.addRow("GST %:", gst_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_item_master(
                    item_code,
                    name_input.text().strip(),
                    unit_input.text().strip(),
                    hsn_input.text().strip(),
                    float(gst_input.text().strip())
                )
                QMessageBox.information(
                    self, "Success", "✅ Master data updated successfully.")
                self.load_full_stock()
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to update master data: {e}")

    def edit_batch_data(self):
        selected_row = self.full_stock_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Select Batch",
                                "⚠️ Please select a batch to edit.")
            return

        item_code = self.full_stock_table.item(selected_row, 0).text()
        purchase_price = self.full_stock_table.item(
            selected_row, 5).text().replace("₹", "")
        sell_price = self.full_stock_table.item(
            selected_row, 6).text().replace("₹", "")
        qty = self.full_stock_table.item(selected_row, 7).text()

        # Edit popup
        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Batch Details")
        form_layout = QFormLayout(dialog)

        purchase_input = QLineEdit(purchase_price)
        sell_input = QLineEdit(sell_price)
        qty_input = QLineEdit(qty)

        form_layout.addRow("Purchase Price (₹):", purchase_input)
        form_layout.addRow("Sell Price (₹):", sell_input)
        form_layout.addRow("Available Qty:", qty_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_batch_details(
                    item_code,
                    float(purchase_input.text().strip()),
                    float(sell_input.text().strip()),
                    int(qty_input.text().strip())
                )
                QMessageBox.information(
                    self, "Success", "✅ Batch details updated successfully.")
                self.load_full_stock()
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to update batch: {e}")

    def export_to_excel(self):
        try:
            # Create Excel workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Full Stock Report"

            # Headers
            headers = [
                "Item Code", "Item Name", "Unit", "HSN Code", "GST (%)",
                "Purchase Price (₹)", "Sell Price (₹)", "Available Qty", "Batch Date"
            ]
            ws.append(headers)

            # Add data rows
            for row in self.full_stock_data:
                ws.append(row)

            # Save Excel file
            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Full_Stock_Report_{today}.xlsx"
            wb.save(filename)

            QMessageBox.information(
                self, "Success", f"✅ Excel exported successfully!\nFile: {filename}")
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to export Excel: {e}")
