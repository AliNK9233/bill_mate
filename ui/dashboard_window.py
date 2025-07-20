from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QGroupBox,
    QGridLayout, QPushButton, QHBoxLayout
)
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from models.dashboard_model import (
    get_total_sales, get_total_customers, get_total_pending_balance,
    get_total_jobwork, get_monthly_sales_jobwork, get_top_customers, get_low_stock_items
)


class DashboardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 Admin Dashboard")
        self.setGeometry(300, 150, 1400, 750)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))

        self.setup_ui()
        self.load_all_dashboard_data()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title and Refresh Button
        header_layout = QHBoxLayout()
        title_label = QLabel("📊 Admin Dashboard")
        title_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; margin: 10px 0;")
        refresh_btn = QPushButton("🔄 Refresh Dashboard")
        refresh_btn.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 5px;")
        refresh_btn.clicked.connect(self.load_all_dashboard_data)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        # Summary Cards
        summary_box = QGroupBox("Overview")
        summary_box.setStyleSheet(
            "QGroupBox { font-size: 16px; font-weight: bold; padding-top: 20px; margin-top: 10px; }")
        summary_layout = QGridLayout()

        self.sales_label = QLabel()
        self.sales_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: green;")
        self.jobwork_label = QLabel()
        self.jobwork_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: purple;")
        self.customers_label = QLabel()
        self.customers_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: blue;")
        self.pending_label = QLabel()
        self.pending_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: red;")

        summary_layout.addWidget(self.sales_label, 0, 0)
        summary_layout.addWidget(self.jobwork_label, 0, 1)
        summary_layout.addWidget(self.customers_label, 1, 0)
        summary_layout.addWidget(self.pending_label, 1, 1)

        summary_box.setLayout(summary_layout)
        layout.addWidget(summary_box)

        # All Charts in Single Row
        all_charts_layout = QHBoxLayout()

        # 📊 Total Sales Split Chart
        self.sales_split_chart = Figure(figsize=(4, 3), dpi=100)
        self.sales_split_canvas = FigureCanvas(self.sales_split_chart)
        all_charts_layout.addWidget(self.sales_split_canvas)

        # 📊 Paid vs Pending Chart
        self.paid_pending_chart = Figure(figsize=(4, 3), dpi=100)
        self.paid_pending_canvas = FigureCanvas(self.paid_pending_chart)
        all_charts_layout.addWidget(self.paid_pending_canvas)

        # 📊 Month-wise Bar Chart
        self.monthly_chart = Figure(figsize=(5, 3), dpi=100)
        self.monthly_canvas = FigureCanvas(self.monthly_chart)
        all_charts_layout.addWidget(self.monthly_canvas)

        layout.addLayout(all_charts_layout)

        # Tables Layout (Side by Side)
        tables_layout = QHBoxLayout()

        # Top Customers Table
        top_customers_box = QGroupBox("🏆 Top 5 Customers (by Sales)")
        top_customers_box.setStyleSheet(
            "QGroupBox { font-size: 16px; font-weight: bold; padding-top: 20px; margin-top: 10px; }")
        top_customers_layout = QVBoxLayout()
        self.top_customers_table = QTableWidget()
        self.top_customers_table.setColumnCount(3)
        self.top_customers_table.setHorizontalHeaderLabels(
            ["Customer Name", "Phone", "Total Sales (₹)"])
        top_customers_layout.addWidget(self.top_customers_table)
        top_customers_box.setLayout(top_customers_layout)
        tables_layout.addWidget(top_customers_box)

        # Low Stock Items Table
        low_stock_box = QGroupBox("⚠️ Low Stock Items")
        low_stock_box.setStyleSheet(
            "QGroupBox { font-size: 16px; font-weight: bold; padding-top: 20px; margin-top: 10px; }")
        low_stock_layout = QVBoxLayout()
        self.low_stock_table = QTableWidget()
        self.low_stock_table.setColumnCount(3)
        self.low_stock_table.setHorizontalHeaderLabels(
            ["Item Name", "Item Code", "Available Qty"])
        low_stock_layout.addWidget(self.low_stock_table)
        low_stock_box.setLayout(low_stock_layout)
        tables_layout.addWidget(low_stock_box)

        layout.addLayout(tables_layout)
        self.setLayout(layout)

    def load_all_dashboard_data(self):
        self.load_summary()
        self.plot_sales_split_chart()
        self.plot_paid_pending_chart()
        self.plot_monthly_bar_chart()
        self.load_top_customers()
        self.load_low_stock_items()

    def load_summary(self):
        total_sales = get_total_sales()
        total_jobwork = get_total_jobwork()
        total_customers = get_total_customers()
        total_pending = get_total_pending_balance()

        self.sales_label.setText(f"🛒 Total Sales: ₹{total_sales:.2f}")
        self.jobwork_label.setText(f"🛠️ Total Job Work: ₹{total_jobwork:.2f}")
        self.customers_label.setText(f"👥 Total Customers: {total_customers}")
        self.pending_label.setText(f"🧾 Pending Balance: ₹{total_pending:.2f}")

    def plot_sales_split_chart(self):
        self.sales_split_chart.clear()
        ax = self.sales_split_chart.add_subplot(111)
        labels = ["Sales", "Job Work"]
        sizes = [get_total_sales(), get_total_jobwork()]
        colors = ["#2ecc71", "#9b59b6"]
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.85
        )
        centre_circle = Circle((0, 0), 0.70, fc="white")
        ax.add_artist(centre_circle)
        ax.set_title("💰 Total Sales Split", fontsize=14, fontweight="bold")
        self.sales_split_canvas.draw()

    def plot_paid_pending_chart(self):
        self.paid_pending_chart.clear()
        ax = self.paid_pending_chart.add_subplot(111)
        total_sales = get_total_sales()
        total_pending = get_total_pending_balance()
        total_paid = total_sales - total_pending
        labels = ["Paid", "Pending"]
        sizes = [total_paid, total_pending]
        colors = ["#3498db", "#e74c3c"]
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.85
        )
        centre_circle = Circle((0, 0), 0.70, fc="white")
        ax.add_artist(centre_circle)
        ax.set_title("💵 Paid vs Pending", fontsize=14, fontweight="bold")
        self.paid_pending_canvas.draw()

    def plot_monthly_bar_chart(self):
        self.monthly_chart.clear()
        ax = self.monthly_chart.add_subplot(111)

        data = get_monthly_sales_jobwork()
        months = [row[0] for row in data]
        sales = [row[1] for row in data]
        jobwork = [row[2] for row in data]

        bar_width = 0.35
        x = range(len(months))

        ax.bar(x, sales, width=bar_width, label="Sales", color="#3498db")
        ax.bar([i + bar_width for i in x], jobwork,
               width=bar_width, label="Job Work", color="#9b59b6")

        ax.set_xticks([i + bar_width / 2 for i in x])
        ax.set_xticklabels(months, rotation=45)
        ax.set_ylabel("Amount (₹)")
        ax.set_title("📅 Month-wise Sales & Job Work")
        ax.legend()

        self.monthly_canvas.draw()

    def load_top_customers(self):
        customers = get_top_customers()
        self.top_customers_table.setRowCount(0)
        for row in customers:
            row_pos = self.top_customers_table.rowCount()
            self.top_customers_table.insertRow(row_pos)
            for col, value in enumerate(row):
                self.top_customers_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))

    def load_low_stock_items(self):
        items = get_low_stock_items()
        self.low_stock_table.setRowCount(0)
        for row in items:
            row_pos = self.low_stock_table.rowCount()
            self.low_stock_table.insertRow(row_pos)
            for col, value in enumerate(row):
                self.low_stock_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))
