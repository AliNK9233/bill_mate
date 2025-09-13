# ui/delivery_challan_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QWidget, QLabel, QLineEdit, QTextEdit, QPushButton, QHBoxLayout, QVBoxLayout,
    QGridLayout, QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QHeaderView,
    QDoubleSpinBox, QCompleter
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

import sqlite3
import datetime

from models import delivery_model
try:
    from models import stock_model
    STOCK_DB = stock_model.DB_FILE
except Exception:
    STOCK_DB = "data/database.db"


def fetch_company_profile():
    conn = sqlite3.connect(delivery_model.DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM company_profile LIMIT 1")
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[0] for d in c.description]
    conn.close()
    return dict(zip(cols, row))


def fetch_stock_list():
    try:
        conn = sqlite3.connect(stock_model.DB_FILE)
    except Exception:
        conn = sqlite3.connect(STOCK_DB)
    c = conn.cursor()
    c.execute("SELECT id, code, name, hsn_code, unit FROM stock ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "code": r[1], "name": r[2], "hsn_code": r[3] or "", "unit": r[4] or ""} for r in rows]


class DeliveryChallanDialog(QDialog):
    """
    Delivery Challan editor dialog.
    Use as:
       dlg = DeliveryChallanDialog(parent=..., edit_mode=False)
       if dlg.exec_() == QDialog.Accepted:
           # created/updated; caller can refresh lists
    For edit:
       dlg = DeliveryChallanDialog(parent=..., edit_mode=True, challan_id=123)
       if dlg.exec_() == QDialog.Accepted:
           # saved edits
    """

    def __init__(self, parent=None, edit_mode=False, challan_id=None):
        super().__init__(parent)
        self.setWindowTitle("Delivery Challan")
        self.resize(900, 700)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png")
                           if hasattr(QIcon, "__call__") else QIcon())

        self.edit_mode = bool(edit_mode)
        self.challan_id = challan_id

        self.company = fetch_company_profile()
        self.stock_list = fetch_stock_list()
        self.stock_code_map = {s["code"]: s for s in self.stock_list}

        self._build_ui()
        if self.edit_mode and self.challan_id:
            self.load_challan(self.challan_id)
        else:
            self.new_challan_setup()

    # ---------------- UI ----------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header Grid
        header_grid = QGridLayout()
        header_grid.setColumnStretch(1, 2)
        header_grid.setColumnStretch(2, 3)

        company_label = QLabel("From (Company):")
        self.company_text = QTextEdit()
        self.company_text.setReadOnly(True)
        if self.company:
            comp_text = f"{self.company.get('name', '')}\n{self.company.get('address', '')}\nGST: {self.company.get('gst_no') or self.company.get('gstin', '')}"
            self.company_text.setPlainText(comp_text)
        else:
            self.company_text.setPlainText("Company profile not set")
        header_grid.addWidget(company_label, 0, 0)
        header_grid.addWidget(self.company_text, 0, 1, 2, 1)

        challan_no_label = QLabel("Challan No:")
        self.challan_no_field = QLineEdit()
        self.challan_no_field.setReadOnly(True)
        datetime_label = QLabel("Date / Time:")
        self.datetime_field = QLineEdit()
        self.datetime_field.setReadOnly(True)

        header_grid.addWidget(challan_no_label, 0, 2)
        header_grid.addWidget(self.challan_no_field, 0, 3)
        header_grid.addWidget(datetime_label, 1, 2)
        header_grid.addWidget(self.datetime_field, 1, 3)

        layout.addLayout(header_grid)

        # To / Transport fields
        to_grid = QGridLayout()
        to_grid.addWidget(QLabel("To (Address):"), 0, 0)
        self.to_address = QTextEdit()
        to_grid.addWidget(self.to_address, 0, 1, 1, 3)

        to_grid.addWidget(QLabel("To GST No:"), 1, 0)
        self.to_gst = QLineEdit()
        to_grid.addWidget(self.to_gst, 1, 1)

        to_grid.addWidget(QLabel("Transporter Name:"), 1, 2)
        self.transporter = QLineEdit()
        to_grid.addWidget(self.transporter, 1, 3)

        to_grid.addWidget(QLabel("Vehicle No:"), 2, 0)
        self.vehicle_no = QLineEdit()
        to_grid.addWidget(self.vehicle_no, 2, 1)

        to_grid.addWidget(QLabel("Delivery Location:"), 2, 2)
        self.delivery_location = QLineEdit()
        to_grid.addWidget(self.delivery_location, 2, 3)

        layout.addLayout(to_grid)

        # Items table
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(
            ["Item Code", "Item Name", "HSN", "Qty", "Unit"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # Row buttons + total
        row_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self.add_row)
        remove_row_btn = QPushButton("Remove Selected Row")
        remove_row_btn.clicked.connect(self.remove_selected_row)
        row_btn_layout.addWidget(add_row_btn)
        row_btn_layout.addWidget(remove_row_btn)
        row_btn_layout.addStretch()

        self.total_qty_label = QLabel("Total Qty: 0")
        row_btn_layout.addWidget(self.total_qty_label)
        layout.addLayout(row_btn_layout)

        # Description with suggestions
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Description / Reason:"))
        self.description_input = QLineEdit()
        desc_layout.addWidget(self.description_input)
        layout.addLayout(desc_layout)

        # Completer for suggestions
        suggestions = delivery_model.get_description_suggestions("", limit=50)
        self.desc_completer = QCompleter(suggestions)
        self.desc_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.description_input.setCompleter(self.desc_completer)

        # Bottom buttons (Save / Cancel)
        bottom_layout = QHBoxLayout()
        self.save_btn = QPushButton(
            "Save Challan" if not self.edit_mode else "Save Edits")
        self.save_btn.clicked.connect(self._on_save_clicked)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(cancel_btn)
        layout.addLayout(bottom_layout)

        # initial row
        self.add_row()

    # ---------------- Helpers ----------------
    def new_challan_setup(self):
        self.challan_no_field.setText(delivery_model.get_next_challan_no())
        self.datetime_field.setText(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.update_total_qty()

    def load_challan(self, challan_id):
        """
        Load data from DB into dialog for editing.
        """
        data = delivery_model.get_challan(challan_id)
        if not data:
            QMessageBox.warning(self, "Not found", "Challan not found.")
            return
        hdr = data["header"]
        self.challan_id = challan_id
        # show challan meta
        self.challan_no_field.setText(hdr.get("challan_no") or "")
        self.datetime_field.setText(hdr.get("created_at") or "")
        self.to_address.setPlainText(hdr.get("to_address") or "")
        self.to_gst.setText(hdr.get("to_gst_no") or "")
        self.transporter.setText(hdr.get("transporter_name") or "")
        self.vehicle_no.setText(hdr.get("vehicle_no") or "")
        self.delivery_location.setText(hdr.get("delivery_location") or "")
        self.description_input.setText(hdr.get("description") or "")

        # populate table rows
        self.table.setRowCount(0)
        for it in data["items"]:
            self.add_row(prefill={
                "item_code": it.get("item_code") or "",
                "item_name": it.get("item_name") or "",
                "hsn_code": it.get("hsn_code") or "",
                "qty": it.get("qty") or 0,
                "unit": it.get("unit") or ""
            })

        self.update_total_qty()

    def add_row(self, prefill=None):
        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        # Item Code: editable combo
        code_combo = QComboBox()
        code_combo.setEditable(True)
        code_combo.addItem("")  # empty option
        for s in self.stock_list:
            code_combo.addItem(s["code"])
        if prefill and prefill.get("item_code"):
            code_combo.setCurrentText(prefill["item_code"])
        code_combo.currentTextChanged.connect(
            lambda txt, r=row_pos: self.on_code_changed(r, txt))
        self.table.setCellWidget(row_pos, 0, code_combo)

        # Item Name
        name_item = QTableWidgetItem(
            prefill.get("item_name") if prefill else "")
        self.table.setItem(row_pos, 1, name_item)

        # HSN
        hsn_item = QTableWidgetItem(prefill.get("hsn_code") if prefill else "")
        self.table.setItem(row_pos, 2, hsn_item)

        # Qty (double spin)
        qty_widget = QDoubleSpinBox()
        qty_widget.setMaximum(1_000_000)
        qty_widget.setDecimals(3)
        qty_widget.valueChanged.connect(
            lambda val, r=row_pos: self.on_qty_changed(r, val))
        if prefill and prefill.get("qty"):
            try:
                qty_widget.setValue(float(prefill["qty"]))
            except Exception:
                pass
        self.table.setCellWidget(row_pos, 3, qty_widget)

        # Unit
        unit_item = QTableWidgetItem(prefill.get("unit") if prefill else "")
        self.table.setItem(row_pos, 4, unit_item)

        self.update_total_qty()

    def remove_selected_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.update_total_qty()

    def on_code_changed(self, row, code_text):
        code = code_text.strip()
        if code and code in self.stock_code_map:
            s = self.stock_code_map[code]
            self.table.setItem(row, 1, QTableWidgetItem(s["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(s.get("hsn_code", "")))
            self.table.setItem(row, 4, QTableWidgetItem(s.get("unit", "")))

    def on_qty_changed(self, row, val):
        self.update_total_qty()

    def update_total_qty(self):
        total = 0.0
        for r in range(self.table.rowCount()):
            qty_widget = self.table.cellWidget(r, 3)
            if qty_widget:
                try:
                    total += float(qty_widget.value())
                except Exception:
                    pass
        self.total_qty_label.setText(f"Total Qty: {total:.3f}")

    def table_to_items(self):
        items = []
        for r in range(self.table.rowCount()):
            code_widget = self.table.cellWidget(r, 0)
            code = code_widget.currentText().strip() if code_widget else ""
            name_item = self.table.item(r, 1)
            name = name_item.text().strip() if name_item else ""
            hsn_item = self.table.item(r, 2)
            hsn = hsn_item.text().strip() if hsn_item else ""
            qty_widget = self.table.cellWidget(r, 3)
            qty = float(qty_widget.value()) if qty_widget else 0.0
            unit_item = self.table.item(r, 4)
            unit = unit_item.text().strip() if unit_item else ""
            if not name:
                continue
            items.append({
                "item_code": code or None,
                "item_name": name,
                "hsn_code": hsn,
                "qty": qty,
                "unit": unit
            })
        return items

    def validate_header(self):
        if not self.to_address.toPlainText().strip():
            QMessageBox.warning(self, "Validation",
                                "Please enter recipient (To address).")
            return False
        items = self.table_to_items()
        if not items:
            QMessageBox.warning(self, "Validation",
                                "Please add at least one item.")
            return False
        return True

    # ---------------- Save handler ----------------
    def _on_save_clicked(self):
        if not self.validate_header():
            return

        header = {
            "company_profile_id": self.company.get("id") if self.company else None,
            "to_address": self.to_address.toPlainText().strip(),
            "to_gst_no": self.to_gst.text().strip(),
            "transporter_name": self.transporter.text().strip(),
            "vehicle_no": self.vehicle_no.text().strip(),
            "delivery_location": self.delivery_location.text().strip(),
            "description": self.description_input.text().strip(),
            "related_invoice_no": None,
            "created_by": None
        }
        items = self.table_to_items()

        try:
            if self.edit_mode and self.challan_id:
                # update existing
                delivery_model.update_challan(self.challan_id, header, items)
                challan_no = self.challan_no_field.text()
                QMessageBox.information(
                    self, "Saved", f"Challan updated: {challan_no}")
            else:
                # create new challan
                cid, challan_no = delivery_model.create_challan(header, items)
                QMessageBox.information(
                    self, "Saved", f"Challan created: {challan_no}")
                # set challan_id for this dialog (if caller wants it)
                self.challan_id = cid
                self.challan_no_field.setText(challan_no)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save challan:\n{str(e)}")
            return

        # refresh suggestions completer
        suggestions = delivery_model.get_description_suggestions("", limit=50)
        self.desc_completer.model().setStringList(suggestions)

        # optionally generate pdf here (placeholder) or call external pdf helper
        # generate_challan_pdf(challan_id or cid)

        # Close dialog and return Accepted
        self.accept()
