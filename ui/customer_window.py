from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox
)
from PyQt5.QtGui import QIcon
from models.invoice_model import get_all_customers, get_customer_sales_summary, update_customer_details
from openpyxl import Workbook
import datetime


class CustomerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("👥 Customer Management")
        self.setGeometry(300, 150, 900, 600)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))

        self.setup_ui()
        self.load_customers()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("👥 Customers")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search Customer Name / Phone")
        self.search_input.textChanged.connect(self.search_customers)

        # Buttons
        edit_btn = QPushButton("✏️ Edit Customer")
        edit_btn.clicked.connect(self.edit_customer)

        view_sales_btn = QPushButton("📄 View Customer Sales")
        view_sales_btn.clicked.connect(self.view_customer_sales)

        export_btn = QPushButton("📥 Export Customers to Excel")
        export_btn.clicked.connect(self.export_customers_to_excel)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(edit_btn)
        search_layout.addWidget(view_sales_btn)
        search_layout.addWidget(export_btn)

        layout.addLayout(search_layout)

        # Customer Table
        self.customer_table = QTableWidget()
        self.customer_table.setColumnCount(5)
        self.customer_table.setHorizontalHeaderLabels([
            "Name", "Phone", "Address", "Total Sales (₹)", "Outstanding Balance (₹)"
        ])
        layout.addWidget(self.customer_table)

        self.setLayout(layout)

    def load_customers(self):
        """
        Load all customers into the table.
        """
        self.customers_data = get_all_customers()
        self.populate_table(self.customers_data)

    def populate_table(self, data):
        """
        Populate the customer table with data.
        """
        self.customer_table.setRowCount(0)
        for row_data in data:
            row_pos = self.customer_table.rowCount()
            self.customer_table.insertRow(row_pos)
            for col, value in enumerate(row_data):
                self.customer_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))

    def search_customers(self):
        """
        Filter customers based on search input.
        """
        search_text = self.search_input.text().lower()
        filtered_data = [
            row for row in self.customers_data
            if search_text in row[0].lower() or search_text in row[1]
        ]
        self.populate_table(filtered_data)

    def edit_customer(self):
        """
        Edit selected customer details.
        """
        selected_row = self.customer_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Select Customer",
                                "⚠️ Please select a customer to edit.")
            return

        name = self.customer_table.item(selected_row, 0).text()
        phone = self.customer_table.item(selected_row, 1).text()
        address = self.customer_table.item(selected_row, 2).text()

        # Edit Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Customer")
        form_layout = QFormLayout(dialog)

        name_input = QLineEdit(name)
        phone_input = QLineEdit(phone)
        address_input = QLineEdit(address)

        form_layout.addRow("Name:", name_input)
        form_layout.addRow("Phone:", phone_input)
        form_layout.addRow("Address:", address_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_customer_details(
                    phone, name_input.text().strip(), phone_input.text(
                    ).strip(), address_input.text().strip()
                )
                QMessageBox.information(
                    self, "Success", "✅ Customer details updated successfully.")
                self.load_customers()
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to update customer: {e}")

    def view_customer_sales(self):
        """
        View selected customer's sales summary.
        """
        selected_row = self.customer_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Select Customer",
                                "⚠️ Please select a customer.")
            return

        phone = self.customer_table.item(selected_row, 1).text()
        summary = get_customer_sales_summary(phone)

        if summary:
            total_sales, pending_invoices = summary
            QMessageBox.information(
                self,
                "Customer Sales Summary",
                f"📊 Total Sales: ₹{total_sales:.2f}\n"
                f"🧾 Pending Invoices: {pending_invoices}"
            )
        else:
            QMessageBox.information(
                self, "No Data", "ℹ️ No sales data found for this customer.")

    def export_customers_to_excel(self):
        """
        Export customer data to Excel.
        """
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Customers Report"

            # Headers
            headers = [
                "Name", "Phone", "Address", "Total Sales (₹)", "Outstanding Balance (₹)"
            ]
            ws.append(headers)

            # Data Rows
            for row in self.customers_data:
                ws.append(row)

            # Save Excel file
            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Customers_Report_{today}.xlsx"
            wb.save(filename)

            QMessageBox.information(
                self, "Success", f"✅ Customers exported successfully!\nFile: {filename}")
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to export Excel: {e}")
