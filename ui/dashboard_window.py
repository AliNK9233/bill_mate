from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QGroupBox, QGridLayout
)
from PyQt5.QtGui import QIcon
from models.dashboard_model import (
    get_total_sales, get_total_customers,
    get_total_pending_balance, get_top_customers, get_low_stock_items
)


class DashboardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 Admin Dashboard")
        self.setGeometry(300, 150, 1000, 600)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("📊 Admin Dashboard")
        title_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Summary Cards
        summary_box = QGroupBox("Overview")
        summary_layout = QGridLayout()

        total_sales = get_total_sales()
        total_customers = get_total_customers()
        total_pending = get_total_pending_balance()

        sales_label = QLabel(f"🛒 Total Sales: ₹{total_sales:.2f}")
        sales_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: green;")

        customers_label = QLabel(f"👥 Total Customers: {total_customers}")
        customers_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: blue;")

        pending_label = QLabel(f"🧾 Pending Balance: ₹{total_pending:.2f}")
        pending_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: red;")

        summary_layout.addWidget(sales_label, 0, 0)
        summary_layout.addWidget(customers_label, 0, 1)
        summary_layout.addWidget(pending_label, 0, 2)

        summary_box.setLayout(summary_layout)
        layout.addWidget(summary_box)

        # Top Customers
        top_customers_box = QGroupBox("🏆 Top 5 Customers (by Sales)")
        top_customers_layout = QVBoxLayout()

        self.top_customers_table = QTableWidget()
        self.top_customers_table.setColumnCount(3)
        self.top_customers_table.setHorizontalHeaderLabels([
            "Customer Name", "Phone", "Total Sales (₹)"
        ])
        self.load_top_customers()

        top_customers_layout.addWidget(self.top_customers_table)
        top_customers_box.setLayout(top_customers_layout)
        layout.addWidget(top_customers_box)

        # Low Stock Items
        low_stock_box = QGroupBox("⚠️ Low Stock Items")
        low_stock_layout = QVBoxLayout()

        self.low_stock_table = QTableWidget()
        self.low_stock_table.setColumnCount(3)
        self.low_stock_table.setHorizontalHeaderLabels([
            "Item Name", "Item Code", "Available Qty"
        ])
        self.load_low_stock_items()

        low_stock_layout.addWidget(self.low_stock_table)
        low_stock_box.setLayout(low_stock_layout)
        layout.addWidget(low_stock_box)

        self.setLayout(layout)

    def load_top_customers(self):
        """
        Load top 5 customers into table.
        """
        customers = get_top_customers()
        self.top_customers_table.setRowCount(0)
        for row in customers:
            row_pos = self.top_customers_table.rowCount()
            self.top_customers_table.insertRow(row_pos)
            for col, value in enumerate(row):
                self.top_customers_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))

    def load_low_stock_items(self):
        """
        Load low stock items into table.
        """
        items = get_low_stock_items()
        self.low_stock_table.setRowCount(0)
        for row in items:
            row_pos = self.low_stock_table.rowCount()
            self.low_stock_table.insertRow(row_pos)
            for col, value in enumerate(row):
                self.low_stock_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))
