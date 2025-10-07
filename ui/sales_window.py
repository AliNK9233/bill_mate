from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from models.invoice_model import (
    get_all_invoices, update_invoice_entry
)
from openpyxl import Workbook
import datetime


class SalesWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 Sales Data")
        self.setGeometry(300, 150, 1100, 600)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        self.edited_rows = {}  # Track edited rows
        self.setup_ui()
        self.load_all_sales()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("📊 Sales Data")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Filters & Buttons
        filter_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "🔍 Search Invoice No or Customer Name")
        self.search_input.textChanged.connect(self.search_invoice)
        filter_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_all_sales)
        filter_layout.addWidget(refresh_btn)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self.save_changes)
        filter_layout.addWidget(save_btn)

        export_btn = QPushButton("📥 Export to Excel")
        export_btn.clicked.connect(self.export_sales_to_excel)
        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # Sales Table
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(9)
        self.sales_table.setHorizontalHeaderLabels([
            "Invoice No", "Customer Name", "Date", "Total Amount (₹)",
            "Paid Amount (₹)", "Balance (₹)", "Payment Method", "Status", "Remarks"
        ])
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sales_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sales_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.sales_table.itemChanged.connect(self.track_changes)
        layout.addWidget(self.sales_table)

        self.setLayout(layout)

    def load_all_sales(self):
        self.sales_data = get_all_invoices()
        self.populate_table(self.sales_data)

    def populate_table(self, data):
        self.sales_table.blockSignals(True)
        self.sales_table.setRowCount(0)
        for row_data in data:
            row_pos = self.sales_table.rowCount()
            self.sales_table.insertRow(row_pos)
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))

                # Only make "Paid Amount" and "Remarks" editable for non-paid rows
                if row_data[7] != "Paid" and col in [4, 8]:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                self.sales_table.setItem(row_pos, col, item)

            # Remarks column
            # Remarks from DB
            remarks_value = row_data[8] if len(row_data) > 8 else ""
            remarks_item = QTableWidgetItem(remarks_value)
            if row_data[7] == "Paid":
                remarks_item.setFlags(
                    remarks_item.flags() & ~Qt.ItemIsEditable)
            self.sales_table.setItem(row_pos, 8, remarks_item)
        self.sales_table.blockSignals(False)

    def track_changes(self, item):
        row = item.row()
        col = item.column()
        if self.sales_table.item(row, 7).text() == "Paid":
            return  # Ignore changes for paid rows

        try:
            total_amount = float(self.sales_table.item(row, 3).text() or 0)
            paid_amount = float(self.sales_table.item(row, 4).text() or 0)

            # Prevent overpayment
            if paid_amount > total_amount:
                QMessageBox.warning(self, "Invalid Entry",
                                    "⚠️ Paid amount cannot exceed total amount.")
                self.load_all_sales()
                return

            balance = total_amount - paid_amount
            status = "Paid" if balance == 0 else (
                "Partial" if paid_amount > 0 else "Unpaid")

            # Update balance and status
            self.sales_table.blockSignals(True)
            self.sales_table.setItem(
                row, 5, QTableWidgetItem(f"{balance:.2f}"))
            self.sales_table.setItem(row, 7, QTableWidgetItem(status))
            self.sales_table.blockSignals(False)

            remarks = self.sales_table.item(row, 8).text() if col == 8 else ""
            invoice_no = self.sales_table.item(row, 0).text()
            self.edited_rows[invoice_no] = {
                "paid_amount": paid_amount,
                "balance": balance,
                "status": status,
                "remarks": remarks
            }
        except Exception:
            pass

    def save_changes(self):
        try:
            if not self.edited_rows:
                QMessageBox.information(
                    self, "No Changes", "ℹ️ No edits to save.")
                return

            for invoice_no, changes in self.edited_rows.items():
                update_invoice_entry(
                    invoice_no,
                    changes["paid_amount"],
                    changes["balance"],
                    changes["status"],
                    changes["remarks"]
                )
            QMessageBox.information(
                self, "Success", "✅ Changes saved successfully.")
            self.load_all_sales()
            self.edited_rows.clear()
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to save changes: {e}")

    def search_invoice(self):
        query = self.search_input.text().lower()
        filtered_data = [row for row in self.sales_data if query in row[0].lower(
        ) or query in row[1].lower()]
        self.populate_table(filtered_data)

    def export_sales_to_excel(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Sales Report"
            headers = [
                "Invoice No", "Customer Name", "Date", "Total Amount (₹)",
                "Paid Amount (₹)", "Balance (₹)", "Payment Method", "Status", "Remarks"
            ]
            ws.append(headers)
            for row in self.sales_data:
                ws.append(row)
            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Sales_Report_{today}.xlsx"
            wb.save(filename)
            QMessageBox.information(
                self, "Success", f"✅ Sales data exported successfully!\nFile: {filename}")
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to export Excel: {e}")
