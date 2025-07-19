from ui.main_window import MainWindow
from PyQt5.QtWidgets import QApplication
import sys
import os

from models.stock_model import initialize_db
from models.invoice_model import initialize_invoice_db
from models.company_model import initialize_company_profile_table
initialize_company_profile_table()


# Initialize DB if needed
if not os.path.exists("data/database.db"):
    print("⚡ Creating new database...")

    initialize_db()
    initialize_invoice_db()
else:
    # Ensure tables exist even if DB file exists
    initialize_invoice_db()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load SAP Theme
    with open("data/themes/theme.qss", "r") as f:
        app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
