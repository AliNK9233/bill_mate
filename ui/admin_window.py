from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QApplication
)
from PyQt5.QtGui import QIcon
from models.stock_model import get_all_batches, update_item_master, update_batch_details
from openpyxl import Workbook
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget
)
from PyQt5.QtGui import QIcon
from ui.dashboard_window import DashboardWindow
from ui.sales_window import SalesWindow
from ui.customer_window import CustomerWindow
from models.stock_model import initialize_db
from ui.admin_stock_window import AdminStockWindow


class AdminWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔒 Admin Panel")
        self.setGeometry(200, 100, 1100, 700)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))

        # Initialize DB if needed
        initialize_db()

        self.setup_ui()

    def setup_ui(self):

        layout = QVBoxLayout()

        # Tabs
        self.tabs = QTabWidget()

        # Dashboard Tab
        self.dashboard_tab = DashboardWindow()
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")

        # Stock Management Tab
        self.stock_tab = AdminStockWindow()  # ✅ Use the admin stock window
        self.tabs.addTab(self.stock_tab, "📦 Stock Management")
        # Sales Data Tab
        self.sales_tab = SalesWindow()
        self.tabs.addTab(self.sales_tab, "💸 Sales Data")

        # Customer Management Tab
        self.customer_tab = CustomerWindow()
        self.tabs.addTab(self.customer_tab, "👥 Customer Management")

        layout.addWidget(self.tabs)
        self.setLayout(layout)
