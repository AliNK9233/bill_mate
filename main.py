import sys
import os

from models.stock_model import initialize_db
from models.invoice_model import initialize_invoice_db

# Initialize DB if needed
if not os.path.exists("data/database.db"):
    print("⚡ Creating new database...")
    initialize_db()
    initialize_invoice_db()
else:
    # Ensure tables exist even if DB file exists
    initialize_invoice_db()

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
