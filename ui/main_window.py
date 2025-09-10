from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QMessageBox, QLineEdit,
    QPushButton, QDialog, QFormLayout, QDialogButtonBox, QHBoxLayout
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt  # ✅ Needed for full-screen flags

from ui.general_stock_window import GeneralStockWindow
from ui.admin_stock_window import AdminStockWindow
# from ui.dashboard_window import DashboardWindow
from ui.sales_window import SalesReportWindow
from ui.customer_window import CustomerWindow
from ui.invoice_window import InvoiceWindow
from ui.profile_window import CompanyProfileWindow
from ui.salesman_window import SalesmanWindow
from ui.welcome_window import WelcomeWindow
from ui.edit_invoice_window import EditInvoiceWindow


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(" Bill Mate")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.admin_tabs = []  # Track admin-only tabs

        self.setup_ui()

        # ✅ Start in maximized mode
        self.showMaximized()

    def setup_ui(self):
        self.layout = QVBoxLayout()

        # Tabs
        self.tabs = QTabWidget()

        # Welcome Tab
        self.welcome_tab = WelcomeWindow()
        self.tabs.addTab(self.welcome_tab, "🏠 Welcome")

        # 🧾 Invoice Tab (Default Tab)
        self.invoice_tab = InvoiceWindow()
        self.tabs.addTab(self.invoice_tab, "🧾 Invoice")

        # edit invoice tab
        self.edit_invoice_tab = EditInvoiceWindow()
        self.tabs.addTab(self.edit_invoice_tab, "📝 Edit Invoice")

        # salesman tab
        self.salesman_tab = SalesmanWindow()
        self.tabs.addTab(self.salesman_tab, "🧑‍💼 Salesman Management")

        # sales tab
        self.sales_tab = SalesReportWindow()
        self.tabs.addTab(self.sales_tab, "💸 Sales Data")

        # 📦 General Stock Tab (For Users)
        self.general_stock_tab = GeneralStockWindow()
        self.tabs.addTab(self.general_stock_tab, "📦 Stock Management")

        # # 📊 Dashboard Tab
        # self.dashboard_tab = DashboardWindow()
        # self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")

        # 🔑 Admin Login & 🚪 Logout Buttons
        button_layout = QHBoxLayout()
        self.admin_btn = QPushButton("🔑 Admin Login")
        self.admin_btn.clicked.connect(self.admin_login)

        self.logout_btn = QPushButton("🚪 Logout Admin")
        self.logout_btn.setDisabled(True)  # Initially disabled
        self.logout_btn.clicked.connect(self.logout_admin)

        # 🖥️ Full-Screen Toggle Button
        self.fullscreen_btn = QPushButton("🖥️ Full Screen")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        button_layout.addWidget(self.admin_btn)
        button_layout.addWidget(self.logout_btn)
        button_layout.addWidget(self.fullscreen_btn)

        self.layout.addLayout(button_layout)
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

        # Set Invoice Tab as default
        self.tabs.setCurrentIndex(0)

    def toggle_fullscreen(self):
        """
        Toggle between Full Screen and Normal Window
        """
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("🖥️ Full Screen")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("❌ Exit Full Screen")

    def admin_login(self):
        """
        Prompt for Admin Password to unlock admin features.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("🔒 Admin Login")
        form_layout = QFormLayout(dialog)

        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Enter Admin Password:", password_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            if password_input.text() == "0000":
                QMessageBox.information(
                    self, "Access Granted", "✅ Admin Access Granted!"
                )
                self.load_admin_tabs()
                self.admin_btn.setDisabled(True)
                self.logout_btn.setDisabled(False)
            else:
                QMessageBox.warning(self, "Access Denied",
                                    "❌ Incorrect Password!")

    def load_admin_tabs(self):
        """
        Add Admin tabs dynamically after successful login.
        """
        try:
            # # 📊 Dashboard Tab
            # self.dashboard_tab = DashboardWindow()
            # self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
            # self.admin_tabs.append(self.dashboard_tab)

            # 📦 Admin Stock Tab
            self.admin_stock_tab = AdminStockWindow()
            self.tabs.addTab(self.admin_stock_tab, "📦 Admin Stock Management")
            self.admin_tabs.append(self.admin_stock_tab)

            # # 💸 Sales Data Tab
            # self.sales_tab = SalesWindow()
            # self.tabs.addTab(self.sales_tab, "💸 Sales Data")
            # self.admin_tabs.append(self.sales_tab)

            # 👥 Customer Management Tab
            self.customer_tab = CustomerWindow()
            self.tabs.addTab(self.customer_tab, "👥 Customer Management")
            self.admin_tabs.append(self.customer_tab)

            # 🏢 Company Profile Tab
            self.profile_tab = CompanyProfileWindow()
            self.tabs.addTab(self.profile_tab, "🏢 Company Profile")
            self.admin_tabs.append(self.profile_tab)

        except Exception as e:
            QMessageBox.critical(
                self, "Error Loading Admin Tabs", f"❌ An error occurred:\n{e}")

    def logout_admin(self):
        """
        Remove admin tabs and return to user mode.
        """
        for tab in self.admin_tabs:
            index = self.tabs.indexOf(tab)
            if index != -1:
                self.tabs.removeTab(index)
        self.admin_tabs.clear()

        self.admin_btn.setDisabled(False)
        self.logout_btn.setDisabled(True)

        QMessageBox.information(
            self, "Logged Out", "✅ Admin access removed. You are now in User Mode."
        )
