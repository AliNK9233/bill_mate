from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from models.invoice_model import (
    get_all_invoices, update_invoice_entry
)
from utils.inv_pdf_helper import generate_invoice_pdf # New Import
from openpyxl import Workbook
import datetime
import os


class SalesWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 Sales Data")
        self.setGeometry(300, 150, 1200, 600) # Increased width
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        self.edited_rows = {}
        self.setup_ui()
        self.load_all_sales()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("📊 Sales Data")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Filters & Buttons
        filter_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search Invoice No or Customer Name")
        self.search_input.textChanged.connect(self.search_invoice)
        filter_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_all_sales)
        filter_layout.addWidget(refresh_btn)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self.save_changes)
        filter_layout.addWidget(save_btn)
        
        # New "View PDF" button
        view_pdf_btn = QPushButton("📄 View PDF")
        view_pdf_btn.clicked.connect(self.view_selected_pdf)
        filter_layout.addWidget(view_pdf_btn)

        export_btn = QPushButton("📥 Export to Excel")
        export_btn.clicked.connect(self.export_sales_to_excel)
        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # Sales Table - Now with 10 columns
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(10)
        self.sales_table.setHorizontalHeaderLabels([
            "Invoice No", "Customer Name", "Date", "Total Amount (₹)", "Discount (₹)",
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

                # Make "Paid Amount" and "Remarks" editable for non-paid/cancelled rows
                status_col_index = 8 
                current_status = row_data[status_col_index]
                if current_status not in ["Paid", "Cancelled"] and col in [5, 9]: # Paid Amount and Remarks
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                self.sales_table.setItem(row_pos, col, item)
        self.sales_table.blockSignals(False)
        self.sales_table.resizeColumnsToContents()

    def track_changes(self, item):
        row = item.row()
        status_item = self.sales_table.item(row, 8)
        if not status_item or status_item.text() in ["Paid", "Cancelled"]:
            return

        try:
            total_amount = float(self.sales_table.item(row, 3).text() or 0)
            paid_amount_item = self.sales_table.item(row, 5)
            
            # Check if the changed item is the paid amount
            if item.column() == 5:
                paid_amount = float(paid_amount_item.text() or 0)

                if paid_amount > total_amount:
                    QMessageBox.warning(self, "Invalid Entry", "⚠️ Paid amount cannot exceed total amount.")
                    # Revert to old value by reloading
                    self.load_all_sales()
                    return

                balance = total_amount - paid_amount
                status = "Paid" if balance <= 0.01 else ("Partial" if paid_amount > 0 else "Unpaid")

                # Update balance and status in the table
                self.sales_table.blockSignals(True)
                self.sales_table.setItem(row, 6, QTableWidgetItem(f"{balance:.2f}"))
                self.sales_table.setItem(row, 8, QTableWidgetItem(status))
                self.sales_table.blockSignals(False)

            # Record changes for saving
            invoice_no = self.sales_table.item(row, 0).text()
            self.edited_rows[invoice_no] = {
                "paid_amount": float(self.sales_table.item(row, 5).text()),
                "balance": float(self.sales_table.item(row, 6).text()),
                "status": self.sales_table.item(row, 8).text(),
                "remarks": self.sales_table.item(row, 9).text()
            }
        except (ValueError, AttributeError):
            pass

    def save_changes(self):
        try:
            if not self.edited_rows:
                QMessageBox.information(self, "No Changes", "ℹ️ No edits to save.")
                return

            for invoice_no, changes in self.edited_rows.items():
                update_invoice_entry(
                    invoice_no,
                    changes["paid_amount"], changes["balance"],
                    changes["status"], changes["remarks"]
                )
            QMessageBox.information(self, "Success", "✅ Changes saved successfully.")
            self.load_all_sales()
            self.edited_rows.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"❌ Failed to save changes: {e}")
            
    def view_selected_pdf(self):
        selected_rows = self.sales_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select an invoice to view its PDF.")
            return
            
        row_index = selected_rows[0].row()
        invoice_no = self.sales_table.item(row_index, 0).text()
        
        try:
            pdf_path = generate_invoice_pdf(invoice_no)
            os.startfile(pdf_path) # Open the PDF file
        except FileNotFoundError:
             QMessageBox.critical(self, "Error", f"Could not find the generated PDF for invoice {invoice_no}.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate or open PDF: {e}")


    def search_invoice(self):
        query = self.search_input.text().lower()
        if not query:
            self.populate_table(self.sales_data)
            return
            
        filtered_data = [row for row in self.sales_data if query in row[0].lower() or query in row[1].lower()]
        self.populate_table(filtered_data)

    def export_sales_to_excel(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Sales Report"
            headers = [self.sales_table.horizontalHeaderItem(i).text() for i in range(self.sales_table.columnCount())]
            ws.append(headers)
            
            for row_num in range(self.sales_table.rowCount()):
                row_data = [self.sales_table.item(row_num, col_num).text() for col_num in range(self.sales_table.columnCount())]
                ws.append(row_data)

            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Sales_Report_{today}.xlsx"
            wb.save(filename)
            QMessageBox.information(self, "Success", f"✅ Sales data exported successfully!\nFile: {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"❌ Failed to export Excel: {e}")
