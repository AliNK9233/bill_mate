from datetime import datetime
from ui.main_window import MainWindow
from PyQt5.QtWidgets import QApplication, QMessageBox
import sys
import os
import base64
from PyQt5.QtGui import QFont

from models.stock_model import init_db as initialize_stock_db
from models.invoice_model import init_invoice_db as initialize_invoice_db
from models.customer_model import init_customer_db
from models.salesman_model import init_salesman_db


# 🕵️‍♂️ Encoded expiry date (base64 to obfuscate)
# Original expiry: 2025-07-19
encoded_expiry = "MjAyNi0wMy0zMQ=="  # base64 encoded

# Decode expiry date
try:
    expiry_str = base64.b64decode(encoded_expiry).decode("utf-8")
    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
except Exception:
    expiry_date = datetime(2000, 1, 1)  # If decoding fails, assume expired

# Create QApplication before showing any PyQt widgets
app = QApplication(sys.argv)

# 🚨 Check current date
if datetime.now() > expiry_date:
    msg = QMessageBox()
    msg.setWindowTitle("Application Expired")
    msg.setText(
        "⚠️ This application has expired.\nPlease contact the developer.")
    msg.setIcon(QMessageBox.Critical)
    msg.exec_()
    sys.exit()  # Stops execution
app.setFont(QFont("Segoe UI", 14))
# Initialize DB always
print("⚡ Ensuring database is ready...")
initialize_stock_db()
initialize_invoice_db()
init_customer_db()
init_salesman_db()

if __name__ == "__main__":
    # Load SAP Theme
    if os.path.exists("data/themes/theme.qss"):
        with open("data/themes/theme.qss", "r") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
