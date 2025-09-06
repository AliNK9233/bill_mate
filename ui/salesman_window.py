from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox
)
from PyQt5.QtGui import QIcon
from models.salesman_model import add_salesman, get_all_salesmen, update_salesman, delete_salesman
from openpyxl import Workbook
import datetime
import sqlite3


DB_FILE = "data/database.db"


def get_all_salesmen():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT emp_id, name, phone, email, remarks FROM salesman")
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_salesman(emp_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values())
    values.append(emp_id)
    cursor.execute(f"UPDATE salesman SET {fields} WHERE emp_id = ?", values)
    conn.commit()
    conn.close()


def delete_salesman(emp_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM salesman WHERE emp_id = ?", (emp_id,))
    conn.commit()
    conn.close()


class SalesmanWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧑‍💼 Salesman Management")
        self.setGeometry(350, 180, 900, 600)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        self.setup_ui()
        self.load_salesmen()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("🧑‍💼 Salesman Management")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title_label)

        # Search + Buttons
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "🔍 Search Salesman Name / Phone / ID")
        self.search_input.textChanged.connect(self.search_salesmen)

        add_btn = QPushButton("➕ Add Salesman")
        add_btn.clicked.connect(self.add_salesman_dialog)

        edit_btn = QPushButton("✏️ Edit Salesman")
        edit_btn.clicked.connect(self.edit_salesman_dialog)

        delete_btn = QPushButton("🗑️ Delete Salesman")
        delete_btn.clicked.connect(self.delete_salesman_action)

        export_btn = QPushButton("📥 Export to Excel")
        export_btn.clicked.connect(self.export_salesmen_to_excel)

        top_layout.addWidget(self.search_input)
        top_layout.addWidget(add_btn)
        top_layout.addWidget(edit_btn)
        top_layout.addWidget(delete_btn)
        top_layout.addWidget(export_btn)
        layout.addLayout(top_layout)

        # Salesman Table
        self.salesman_table = QTableWidget()
        self.salesman_table.setColumnCount(5)
        self.salesman_table.setHorizontalHeaderLabels(
            ["Emp ID", "Name", "Phone", "Email", "Remarks"]
        )
        layout.addWidget(self.salesman_table)

        self.setLayout(layout)

    # -----------------------------
    # Data Management
    # -----------------------------

    def load_salesmen(self):
        self.salesmen_data = get_all_salesmen()
        self.populate_salesman_table(self.salesmen_data)

    def populate_salesman_table(self, data):
        self.salesman_table.setRowCount(0)
        for row in data:
            row_pos = self.salesman_table.rowCount()
            self.salesman_table.insertRow(row_pos)
            for col, value in enumerate(row):
                self.salesman_table.setItem(
                    row_pos, col, QTableWidgetItem(str(value)))

    def search_salesmen(self):
        search_text = self.search_input.text().lower()
        filtered = [
            row for row in self.salesmen_data
            if search_text in row[0].lower()
            or search_text in row[1].lower()
            or search_text in str(row[2])
        ]
        self.populate_salesman_table(filtered)

    # -----------------------------
    # CRUD Functions
    # -----------------------------

    def add_salesman_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Add New Salesman")
        form_layout = QFormLayout(dialog)

        emp_id_input = QLineEdit()
        name_input = QLineEdit()
        phone_input = QLineEdit()
        email_input = QLineEdit()
        remarks_input = QLineEdit()

        form_layout.addRow("Employee ID:", emp_id_input)
        form_layout.addRow("Name:", name_input)
        form_layout.addRow("Phone:", phone_input)
        form_layout.addRow("Email:", email_input)
        form_layout.addRow("Remarks:", remarks_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                add_salesman(emp_id_input.text().strip(),
                             name_input.text().strip(),
                             phone_input.text().strip(),
                             email_input.text().strip(),
                             remarks_input.text().strip())
                QMessageBox.information(
                    self, "Success", "✅ Salesman added successfully.")
                self.load_salesmen()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"❌ {e}")

    def edit_salesman_dialog(self):
        row = self.salesman_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Salesman",
                                "⚠️ Please select a salesman.")
            return

        emp_id = self.salesman_table.item(row, 0).text()
        name = self.salesman_table.item(row, 1).text()
        phone = self.salesman_table.item(row, 2).text()
        email = self.salesman_table.item(row, 3).text()
        remarks = self.salesman_table.item(row, 4).text()

        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Salesman")
        form_layout = QFormLayout(dialog)

        name_input = QLineEdit(name)
        phone_input = QLineEdit(phone)
        email_input = QLineEdit(email)
        remarks_input = QLineEdit(remarks)

        form_layout.addRow("Name:", name_input)
        form_layout.addRow("Phone:", phone_input)
        form_layout.addRow("Email:", email_input)
        form_layout.addRow("Remarks:", remarks_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form_layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_salesman(emp_id,
                                name=name_input.text().strip(),
                                phone=phone_input.text().strip(),
                                email=email_input.text().strip(),
                                remarks=remarks_input.text().strip())
                QMessageBox.information(
                    self, "Success", "✅ Salesman updated successfully.")
                self.load_salesmen()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"❌ {e}")

    def delete_salesman_action(self):
        row = self.salesman_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Salesman",
                                "⚠️ Please select a salesman.")
            return

        emp_id = self.salesman_table.item(row, 0).text()

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete salesman {emp_id}?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            try:
                delete_salesman(emp_id)
                QMessageBox.information(
                    self, "Success", "✅ Salesman deleted successfully.")
                self.load_salesmen()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"❌ {e}")

    # -----------------------------
    # Export
    # -----------------------------

    def export_salesmen_to_excel(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Salesmen Report"

            headers = ["Emp ID", "Name", "Phone", "Email", "Remarks"]
            ws.append(headers)

            for row in self.salesmen_data:
                ws.append(row)

            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Salesmen_Report_{today}.xlsx"
            wb.save(filename)

            QMessageBox.information(
                self, "Success", f"✅ Salesmen exported successfully!\nFile: {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"❌ Failed to export: {e}")
