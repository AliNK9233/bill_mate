from datetime import datetime
from ui.main_window import MainWindow
from PyQt5.QtWidgets import QApplication, QMessageBox
import sys
import os
import base64

from models.stock_model import initialize_db
from models.jobwork_model import initialize_jobwork_db
from models.invoice_model import initialize_invoice_db
from models.company_model import initialize_company_profile_table
from models.delivery_model import initialize_delivery_tables
initialize_company_profile_table()
initialize_delivery_tables()

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

# Initialize DB if needed
if not os.path.exists("data/database.db"):
    print("⚡ Creating new database...")
    initialize_db()
    initialize_invoice_db()
    initialize_jobwork_db()

else:
    # Ensure tables exist even if DB file exists
    initialize_invoice_db()
    initialize_jobwork_db()

if __name__ == "__main__":
    # Load SAP Theme
    with open("data/themes/theme.qss", "r") as f:
        app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
