# ui/customer_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox, QSplitter, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QColor, QBrush
from openpyxl import Workbook
import datetime
import sqlite3
import os

from models.customer_model import (
    add_customer, get_customer_by_code, add_outlet, get_outlets,
    get_all_customers
)

DB_FILE = "data/database.db"


def update_customer_in_db(customer_code, **kwargs):
    """
    Safe local helper to update allowed customer fields.
    Avoids import/signature mismatch with model helper.
    Allowed: name, trn_no, email, phone, remarks, disabled, address_line1, address_line2
    """
    allowed = {"name", "trn_no", "email", "phone", "remarks",
               "disabled", "address_line1", "address_line2"}
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    # append updated_at and where param
    values.append(datetime.datetime.now().isoformat())
    values.append(customer_code)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    sql = f"UPDATE customer SET {', '.join(fields)}, updated_at = ? WHERE customer_code = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()


def update_outlet_in_db(outlet_id, **kwargs):
    """
    Local helper to update outlet fields (if models.update_outlet not available).
    Allowed fields: outlet_code, outlet_name, address_line1, address_line2, city, state, country, phone, remarks, disabled
    """
    allowed = {"outlet_code", "outlet_name", "address_line1", "address_line2",
               "city", "state", "country", "phone", "remarks", "disabled"}
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    values.append(outlet_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE customer_outlet SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


class CustomerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("👥 Customer & Outlets")
        self.setGeometry(250, 120, 1200, 700)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        self.customers_data = []
        self.current_customer_code = None

        self.setup_ui()
        self.load_customers()

    def setup_ui(self):
        # root layout
        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # -------- header (compact) --------
        header_row = QHBoxLayout()
        header = QLabel("Customers & Outlets")
        header.setObjectName("smallHeader")
        header.setStyleSheet("font-size:13px; font-weight:600;")
        # force compact header (theme won't expand it)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.setMaximumHeight(28)
        header_row.addWidget(header)
        header_row.addStretch()
        root.addLayout(header_row)

        # -------- toolbar (compact) wrapped in a widget) --------
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search customers by name / phone / code / address")
        self.search_input.setFixedWidth(360)
        self.search_input.setMaximumHeight(28)
        self.search_input.textChanged.connect(self.search_customers)

        add_btn = QPushButton("➕ Add Customer")
        edit_btn = QPushButton("✏️ Edit Customer")
        add_outlet_btn = QPushButton("🏬 Add Outlet")
        edit_outlet_btn = QPushButton("✏️ Edit Outlet")
        refresh_btn = QPushButton("🔄 Refresh")
        export_btn = QPushButton("📥 Export")

        # connect actions
        add_btn.clicked.connect(self.add_customer_dialog)
        edit_btn.clicked.connect(self.edit_customer_dialog)
        add_outlet_btn.clicked.connect(self.add_outlet_dialog)
        edit_outlet_btn.clicked.connect(self.edit_outlet_dialog)
        refresh_btn.clicked.connect(self.load_customers)
        export_btn.clicked.connect(self.export_customers_to_excel)

        # compact button sizing so theme won't make them tall
        for w in (add_btn, edit_btn, add_outlet_btn, edit_outlet_btn, refresh_btn, export_btn):
            w.setMaximumHeight(30)
            w.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        toolbar_layout.addWidget(self.search_input)
        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addWidget(edit_btn)
        toolbar_layout.addWidget(add_outlet_btn)
        toolbar_layout.addWidget(edit_outlet_btn)
        toolbar_layout.addWidget(refresh_btn)
        toolbar_layout.addWidget(export_btn)
        toolbar_layout.addStretch()

        toolbar_widget.setLayout(toolbar_layout)
        toolbar_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar_widget.setMaximumHeight(46)
        root.addWidget(toolbar_widget)

        # -------- create left and right panels BEFORE creating splitter --------
        # Left panel: customer list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.customer_table = QTableWidget()
        # Added Address Line 1 and Address Line 2 columns
        self.customer_table.setColumnCount(8)
        self.customer_table.setHorizontalHeaderLabels(
            ["Customer Code", "Name", "TRN", "Address Line 1",
                "Address Line 2", "Phone", "Remarks", "Disabled"]
        )
        self.customer_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.customer_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.customer_table.cellClicked.connect(self.on_customer_selected)

        # ensure table expands to fill available space
        self.customer_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.customer_table.setMinimumHeight(200)

        left_layout.addWidget(self.customer_table)

        # Right panel: outlets
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        subtitle = QLabel("Outlets for selected customer")
        subtitle.setStyleSheet("font-weight:600;")
        subtitle.setMaximumHeight(22)
        right_layout.addWidget(subtitle)

        self.outlet_table = QTableWidget()
        self.outlet_table.setColumnCount(8)
        self.outlet_table.setHorizontalHeaderLabels(
            ["ID", "Outlet Code", "Outlet Name", "Address",
                "City", "Phone", "Remarks", "Disabled"]
        )
        self.outlet_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.outlet_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.outlet_table.hideColumn(0)  # hide ID column

        self.outlet_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.outlet_table.setMinimumHeight(200)

        right_layout.addWidget(self.outlet_table)

        # -------- splitter panels (now add widgets to splitter) --------
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([480, 720])

        # force splitter to expand and take the remaining space
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        root.addWidget(splitter)

        # set final layout
        self.setLayout(root)

    # -------------------------
    # Load / Refresh
    # -------------------------
    def load_customers(self):
        """Load all customers (including disabled) and refresh UI."""
        try:
            self.customers_data = get_all_customers(include_disabled=True)
        except TypeError:
            self.customers_data = get_all_customers()
        self.populate_customer_table(self.customers_data)
        # clear outlets
        self.outlet_table.setRowCount(0)
        self.current_customer_code = None

    def populate_customer_table(self, data):
        self.customer_table.setRowCount(0)
        for row in data:
            # flexible tuple handling to support older and newer schemas
            # possible expected tuples (older): (customer_code, name, trn_no, phone, remarks, disabled)
            # newer: (customer_code, name, trn_no, address_line1, address_line2, phone, remarks, disabled)
            r = self.customer_table.rowCount()
            self.customer_table.insertRow(r)

            # safe getters
            customer_code = row[0] if len(row) > 0 else ""
            name = row[1] if len(row) > 1 else ""
            trn_no = row[2] if len(row) > 2 else ""
            # guess address fields
            addr1 = ""
            addr2 = ""
            phone = ""
            remarks = ""
            disabled_val = 0

            if len(row) >= 8:
                # assume new layout
                addr1 = row[3]
                addr2 = row[4]
                phone = row[5]
                remarks = row[6]
                disabled_val = int(row[7]) if row[7] is not None else 0
            else:
                # fallback to older layout
                # try to find phone and remarks by scanning
                if len(row) > 3:
                    phone = row[3]
                if len(row) > 4:
                    remarks = row[4]
                if len(row) > 5:
                    try:
                        disabled_val = int(row[5])
                    except Exception:
                        disabled_val = 0

            values = [customer_code, name, trn_no,
                      addr1, addr2, phone, remarks]
            for c, value in enumerate(values):
                self.customer_table.setItem(r, c, QTableWidgetItem(str(value)))

            # Disabled column - show Yes/No and style
            text = "Yes" if int(disabled_val) else "No"
            item = QTableWidgetItem(text)
            if int(disabled_val):
                item.setForeground(QBrush(QColor(180, 30, 30)))
            self.customer_table.setItem(r, 7, item)

            # if disabled -> paint row light red
            try:
                if int(disabled_val):
                    for col_i in range(self.customer_table.columnCount()):
                        cell = self.customer_table.item(r, col_i)
                        if cell:
                            cell.setBackground(QBrush(QColor(255, 235, 235)))
            except Exception:
                pass
        self.customer_table.resizeColumnsToContents()

    def search_customers(self):
        q = self.search_input.text().lower()
        if not self.customers_data:
            return
        filtered = []
        for row in self.customers_data:
            # build a combined string using available fields safely
            parts = []
            for i in (0, 1, 2, 3, 4):
                if len(row) > i and row[i] is not None:
                    parts.append(str(row[i]).lower())
            combined = " ".join(parts)
            if q in combined:
                filtered.append(row)
        self.populate_customer_table(filtered)

    # -------------------------
    # Customer actions
    # -------------------------
    def add_customer_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Customer")
        form = QFormLayout(dialog)
        name_input = QLineEdit()
        trn_input = QLineEdit()
        addr1_input = QLineEdit()
        addr2_input = QLineEdit()
        phone_input = QLineEdit()
        remarks_input = QLineEdit()
        form.addRow("Name:", name_input)
        form.addRow("TRN:", trn_input)
        form.addRow("Address Line 1:", addr1_input)
        form.addRow("Address Line 2:", addr2_input)
        form.addRow("Phone:", phone_input)
        form.addRow("Remarks:", remarks_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            try:
                # attempt to call model add_customer with address kwargs (if model supports)
                try:
                    code = add_customer(
                        name_input.text().strip(),
                        trn_input.text().strip(),
                        phone=phone_input.text().strip(),
                        remarks=remarks_input.text().strip(),
                        address_line1=addr1_input.text().strip(),
                        address_line2=addr2_input.text().strip()
                    )
                except TypeError:
                    # fallback to older signature without address
                    code = add_customer(
                        name_input.text().strip(),
                        trn_input.text().strip(),
                        phone=phone_input.text().strip(),
                        remarks=remarks_input.text().strip()
                    )

                QMessageBox.information(
                    self, "Success", f"Customer {code} added.")
                self.load_customers()
                self.select_customer_by_code(code)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to add customer: {e}")

    def edit_customer_dialog(self):
        row = self.customer_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Customer",
                                "Please select a customer to edit.")
            return
        code = self.customer_table.item(row, 0).text()

        # use robust dict helper
        from models.customer_model import get_customer_dict, update_customer
        cust = get_customer_dict(code)
        if not cust:
            QMessageBox.warning(self, "Error", "Customer not found.")
            return

        # safe extraction
        customer_code = cust.get("customer_code") or code
        name = cust.get("name", "")
        trn = cust.get("trn_no", "")
        addr1 = cust.get("address_line1", "")
        addr2 = cust.get("address_line2", "")
        email = cust.get("email", "")
        phone = cust.get("phone", "")
        remarks = cust.get("remarks", "")
        disabled = int(cust.get("disabled", 0) or 0)

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Customer")
        form = QFormLayout(dialog)
        name_input = QLineEdit(name)
        trn_input = QLineEdit(trn)
        addr1_input = QLineEdit(addr1)
        addr2_input = QLineEdit(addr2)
        phone_input = QLineEdit(phone)
        remarks_input = QLineEdit(remarks)
        disabled_cb = QCheckBox("Disabled")
        disabled_cb.setChecked(bool(disabled))
        # company name should be editable earlier? (we keep full edit)
        form.addRow("Name:", name_input)
        form.addRow("TRN:", trn_input)
        form.addRow("Address Line 1:", addr1_input)
        form.addRow("Address Line 2:", addr2_input)
        form.addRow("Phone:", phone_input)
        form.addRow("Remarks:", remarks_input)
        form.addRow(disabled_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            new_disabled = 1 if disabled_cb.isChecked() else 0
            try:
                # update textual fields via model helper (updated earlier)
                update_customer(customer_code,
                                name=name_input.text().strip(),
                                trn_no=trn_input.text().strip(),
                                phone=phone_input.text().strip(),
                                remarks=remarks_input.text().strip(),
                                address_line1=addr1_input.text().strip(),
                                address_line2=addr2_input.text().strip(),
                                disabled=new_disabled)
                # cascade disable if toggled on now and was off before
                if new_disabled == 1 and disabled == 0:
                    ok = QMessageBox.question(
                        self, "Confirm Disable", "Disabling this customer will disable ALL its outlets. Continue?", QMessageBox.Yes | QMessageBox.No)
                    if ok == QMessageBox.Yes:
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM customer WHERE customer_code = ?", (customer_code,))
                        rowid = cursor.fetchone()
                        if rowid:
                            cid_val = rowid[0]
                            cursor.execute(
                                "UPDATE customer_outlet SET disabled = 1 WHERE customer_id = ?", (cid_val,))
                            conn.commit()
                        conn.close()
                QMessageBox.information(self, "Success", "Customer updated.")
                self.load_customers()
                self.select_customer_by_code(customer_code)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update: {e}")

    def toggle_disable_customer_cascade(self, customer_code):
        """
        Not used in toolbar; kept as helper if needed.
        """
        # fetch current
        cust = get_customer_by_code(customer_code)
        if not cust:
            return
        disabled = int(cust[7]) if len(cust) > 7 else 0
        if disabled:
            # enable
            update_customer_in_db(customer_code, disabled=0)
        else:
            # disable + cascade
            update_customer_in_db(customer_code, disabled=1)
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM customer WHERE customer_code = ?", (customer_code,))
            row = cursor.fetchone()
            if row:
                cid = row[0]
                cursor.execute(
                    "UPDATE customer_outlet SET disabled = 1 WHERE customer_id = ?", (cid,))
                conn.commit()
            conn.close()
        self.load_customers()

    def select_customer_by_code(self, code):
        for r in range(self.customer_table.rowCount()):
            if self.customer_table.item(r, 0).text() == code:
                self.customer_table.selectRow(r)
                self.on_customer_selected(r, 0)
                break

    def on_customer_selected(self, row, col):
        code = self.customer_table.item(row, 0).text()
        self.current_customer_code = code
        # load outlets (including disabled)
        try:
            outlets = get_outlets(code, include_disabled=True)
        except TypeError:
            outlets = get_outlets(code)
        self.outlet_table.setRowCount(0)
        for out in outlets:
            # expected out: id, customer_id, outlet_code, outlet_name, address1, address2, city, state, country, phone, remarks, disabled
            out_id = out[0]
            outlet_code = out[2] if len(out) > 2 else ""
            outlet_name = out[3] if len(out) > 3 else ""
            addr1 = out[4] if len(out) > 4 else ""
            addr2 = out[5] if len(out) > 5 else ""
            address = ", ".join(p for p in (addr1, addr2) if p)
            city = out[6] if len(out) > 6 else ""
            phone = out[9] if len(out) > 9 else ""
            remarks = out[10] if len(out) > 10 else ""
            disabled = int(out[11]) if len(out) > 11 else 0

            rpos = self.outlet_table.rowCount()
            self.outlet_table.insertRow(rpos)
            self.outlet_table.setItem(rpos, 0, QTableWidgetItem(str(out_id)))
            self.outlet_table.setItem(rpos, 1, QTableWidgetItem(outlet_code))
            self.outlet_table.setItem(rpos, 2, QTableWidgetItem(outlet_name))
            self.outlet_table.setItem(rpos, 3, QTableWidgetItem(address))
            self.outlet_table.setItem(rpos, 4, QTableWidgetItem(city))
            self.outlet_table.setItem(rpos, 5, QTableWidgetItem(phone))
            self.outlet_table.setItem(rpos, 6, QTableWidgetItem(remarks))
            # Disabled column show Yes/No and style
            dis_text = "Yes" if disabled else "No"
            item = QTableWidgetItem(dis_text)
            if disabled:
                item.setForeground(QBrush(QColor(180, 30, 30)))
                # highlight row
                for col_i in range(self.outlet_table.columnCount()):
                    # ensure cell exists
                    pass
            self.outlet_table.setItem(rpos, 7, item)
            if disabled:
                for col_i in range(self.outlet_table.columnCount()):
                    cell = self.outlet_table.item(rpos, col_i)
                    if cell:
                        cell.setBackground(QBrush(QColor(255, 240, 240)))

        self.outlet_table.resizeColumnsToContents()

    def update_buttons_state(self):
        # not used heavily now; kept if you want fine-grained enable/disable of toolbar buttons
        pass

    # -------------------------
    # Outlets actions
    # -------------------------
    def add_outlet_dialog(self):
        row = self.customer_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Customer",
                                "Please select a customer first.")
            return
        customer_code = self.customer_table.item(row, 0).text()

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Outlet")
        form = QFormLayout(dialog)
        outlet_code_input = QLineEdit()
        outlet_name_input = QLineEdit()
        addr1_input = QLineEdit()
        addr2_input = QLineEdit()
        city_input = QLineEdit()
        phone_input = QLineEdit()
        remarks_input = QLineEdit()
        form.addRow("Outlet Code:", outlet_code_input)
        form.addRow("Outlet Name:", outlet_name_input)
        form.addRow("Address Line 1:", addr1_input)
        form.addRow("Address Line 2:", addr2_input)
        form.addRow("City:", city_input)
        form.addRow("Phone:", phone_input)
        form.addRow("Remarks:", remarks_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            try:
                add_outlet(customer_code,
                           outlet_code_input.text().strip(),
                           outlet_name_input.text().strip(),
                           addr1_input.text().strip(),
                           addr2_input.text().strip(),
                           city_input.text().strip(),
                           "", "",  # state, country
                           phone_input.text().strip(),
                           remarks_input.text().strip())
                QMessageBox.information(self, "Success", "Outlet added.")
                # refresh outlets
                current_row = self.customer_table.currentRow()
                if current_row >= 0:
                    self.on_customer_selected(current_row, 0)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to add outlet: {e}")

    def edit_outlet_dialog(self):
        row = self.outlet_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Outlet",
                                "Please select an outlet to edit.")
            return
        outlet_id = int(self.outlet_table.item(row, 0).text())
        outlet_code = self.outlet_table.item(row, 1).text()
        outlet_name = self.outlet_table.item(row, 2).text()
        address = self.outlet_table.item(row, 3).text()
        city = self.outlet_table.item(row, 4).text()
        phone = self.outlet_table.item(row, 5).text()
        remarks = self.outlet_table.item(row, 6).text()
        disabled = 1 if self.outlet_table.item(
            row, 7).text().lower() == "yes" else 0

        addr_parts = [p.strip()
                      for p in address.split(",")] if address else ["", ""]
        addr1 = addr_parts[0] if len(addr_parts) > 0 else ""
        addr2 = addr_parts[1] if len(addr_parts) > 1 else ""

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Outlet")
        form = QFormLayout(dialog)
        code_input = QLineEdit(outlet_code)
        name_input = QLineEdit(outlet_name)
        addr1_input = QLineEdit(addr1)
        addr2_input = QLineEdit(addr2)
        city_input = QLineEdit(city)
        phone_input = QLineEdit(phone)
        remarks_input = QLineEdit(remarks)
        disabled_cb = QCheckBox("Disabled (Yes / No)")
        disabled_cb.setChecked(bool(disabled))
        form.addRow("Outlet Code:", code_input)
        form.addRow("Outlet Name:", name_input)
        form.addRow("Address Line 1:", addr1_input)
        form.addRow("Address Line 2:", addr2_input)
        form.addRow("City:", city_input)
        form.addRow("Phone:", phone_input)
        form.addRow("Remarks:", remarks_input)
        form.addRow(disabled_cb)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            try:
                payload = {
                    "outlet_code": code_input.text().strip(),
                    "outlet_name": name_input.text().strip(),
                    "address_line1": addr1_input.text().strip(),
                    "address_line2": addr2_input.text().strip(),
                    "city": city_input.text().strip(),
                    "phone": phone_input.text().strip(),
                    "remarks": remarks_input.text().strip(),
                    "disabled": 1 if disabled_cb.isChecked() else 0
                }
                # try to use model's update_outlet if present
                try:
                    from models.customer_model import update_outlet
                except Exception:
                    update_outlet = None

                if update_outlet:
                    update_outlet(outlet_id, **payload)
                else:
                    update_outlet_in_db(outlet_id, **payload)

                QMessageBox.information(self, "Success", "Outlet updated.")
                # refresh outlets
                self.on_customer_selected(self.customer_table.currentRow(), 0)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to update outlet: {e}")

    # -------------------------
    # Export
    # -------------------------
    def export_customers_to_excel(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Customers_Outlets"
            headers = [
                "Customer Code", "Customer Name", "Customer TRN", "Customer Address Line 1", "Customer Address Line 2", "Customer Phone", "Customer Remarks", "Customer Disabled",
                "Outlet ID", "Outlet Code", "Outlet Name", "Outlet Address", "Outlet City", "Outlet Phone", "Outlet Remarks", "Outlet Disabled"
            ]
            ws.append(headers)

            try:
                all_customers = get_all_customers(include_disabled=True)
            except TypeError:
                all_customers = get_all_customers()

            for cust in all_customers:
                # flexible unpacking similar to populate
                cust_code = cust[0] if len(cust) > 0 else ""
                cust_name = cust[1] if len(cust) > 1 else ""
                cust_trn = cust[2] if len(cust) > 2 else ""
                cust_addr1 = cust[3] if len(cust) > 3 else ""
                cust_addr2 = cust[4] if len(cust) > 4 else ""
                cust_phone = cust[5] if len(cust) > 5 else ""
                cust_remarks = cust[6] if len(cust) > 6 else ""
                cust_disabled = cust[7] if len(cust) > 7 else 0

                try:
                    outlets = get_outlets(cust_code, include_disabled=True)
                except TypeError:
                    outlets = get_outlets(cust_code)

                if not outlets:
                    ws.append([cust_code, cust_name, cust_trn, cust_addr1, cust_addr2, cust_phone,
                              cust_remarks, ("Yes" if cust_disabled else "No")] + [""] * 8)
                else:
                    for out in outlets:
                        out_id = out[0]
                        out_code = out[2] if len(out) > 2 else ""
                        out_name = out[3] if len(out) > 3 else ""
                        addr = ", ".join(p for p in (
                            (out[4] if len(out) > 4 else ""), (out[5] if len(out) > 5 else "")) if p)
                        out_city = out[6] if len(out) > 6 else ""
                        out_phone = out[9] if len(out) > 9 else ""
                        out_remarks = out[10] if len(out) > 10 else ""
                        out_disabled = out[11] if len(out) > 11 else 0
                        ws.append([
                            cust_code, cust_name, cust_trn, cust_addr1, cust_addr2, cust_phone, cust_remarks, (
                                "Yes" if cust_disabled else "No"),
                            out_id, out_code, out_name, addr, out_city, out_phone, out_remarks, (
                                "Yes" if out_disabled else "No")
                        ])

            today = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"Customers_Outlets_{today}.xlsx"
            wb.save(filename)
            QMessageBox.information(self, "Success", f"Exported to {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export: {e}")
