from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QComboBox, QDateEdit, QMessageBox
)
from PyQt5.QtCore import QDate
from PyQt5.QtGui import QIcon
from models.invoice_model import get_all_invoices, get_invoices_by_month, get_invoices_by_date_range
from openpyxl import Workbook
import datetime


class SalesWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 Sales Data")
        self.setGeometry(300, 150, 1000, 600)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))

        self.setup_ui()
        self.load_all_sales()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("📊 Sales Data")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Filters
        filter_layout = QHBoxLayout()

        # Month Filter
        self.month_filter = QComboBox()
        self.month_filter.addItem("All Months")
        for month in range(1, 13):
            self.month_filter.addItem(QDate.longMonthName(month))
        self.month_filter.currentIndexChanged.connect(self.apply_month_filter)
        filter_layout.addWidget(QLabel("Filter by Month:"))
        filter_layout.addWidget(self.month_filter)

        # Date Range Filter
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())

        date_filter_btn = QPushButton("Apply Date Range")
        date_filter_btn.clicked.connect(self.apply_date_range_filter)

        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.end_date)
        filter_layout.addWidget(date_filter_btn)

        # Export Button
        export_btn = QPushButton("📥 Export to Excel")
        export_btn.clicked.connect(self.export_sales_to_excel)

        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # Sales Table
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(8)
        self.sales_table.setHorizontalHeaderLabels([
            "Invoice No", "Customer Name", "Date", "Total Amount (₹)",
            "Paid Amount (₹)", "Balance (₹)", "Payment Method", "Status"
        ])
        layout.addWidget(self.sales_table)

        self.setLayout(layout)

    def load_all_sales(self):
        """
        Load all invoices into the table.
        """
        self.sales_data = get_all_invoices()
        self.populate_table(self.sales_data)

    def populate_table(self, data):
        """
        Populate the sales table with data.
        """
        self.sales_table.setRowCount(0)
        for row_data in data:
            row_pos = self.sales_table.rowCount()
            self.sales_table.insertRow(row_pos)
            for col, value in enumerate(row_data):
                self.sales_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))

    def apply_month_filter(self):
        """
        Filter invoices by selected month.
        """
        selected_month = self.month_filter.currentIndex()
        if selected_month == 0:
            self.load_all_sales()
        else:
            self.sales_data = get_invoices_by_month(selected_month)
            self.populate_table(self.sales_data)

    def apply_date_range_filter(self):
        """
        Filter invoices by date range.
        """
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        self.sales_data = get_invoices_by_date_range(start, end)
        self.populate_table(self.sales_data)

    def export_sales_to_excel(self):
        """
        Export the current sales data to Excel.
        """
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Sales Report"

            # Headers
            headers = [
                "Invoice No", "Customer Name", "Date", "Total Amount (₹)",
                "Paid Amount (₹)", "Balance (₹)", "Payment Method", "Status"
            ]
            ws.append(headers)

            # Data Rows
            for row in self.sales_data:
                ws.append(row)

            # Save Excel file
            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Sales_Report_{today}.xlsx"
            wb.save(filename)

            QMessageBox.information(
                self, "Success", f"✅ Sales data exported successfully!\nFile: {filename}")
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to export Excel: {e}")
