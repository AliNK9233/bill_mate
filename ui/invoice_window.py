# ui/invoice_window.py
import os
import sys
import subprocess
import sqlite3
import uuid
from functools import partial
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QMessageBox, QComboBox, QCompleter, QCheckBox, QDialog,
    QDialogButtonBox, QToolButton
)
from PyQt5.QtGui import QIcon, QFont, QIntValidator
from PyQt5.QtCore import Qt

# Models
from models.customer_model import get_all_customers, get_outlets
from models.salesman_model import get_all_salesmen
from models.stock_model import get_consolidated_stock
from models.invoice_model import create_invoice, fetch_invoice

# PDF generator helper
from utils.pdf_helper import generate_invoice_pdf


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        try:
            s = str(v).replace(",", "").strip()
            return float(s) if s else float(default)
        except Exception:
            return float(default)


def open_file_externally(path):
    if not path or not os.path.exists(path):
        return
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform.startswith("darwin"):
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])


class InvoiceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧾 Invoice Generator")
        self.setGeometry(200, 100, 1100, 650)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        self.invoice_items = []
        self.next_line_id = 1
        self.item_lookup = {}

        self.setup_ui()
        self.load_customer_options()
        self.load_salesman_options()
        self.load_item_options()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)

        title = QLabel("🧾 Invoice Generator")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        # ---------------------------
        # Customer / ship / salesman row
        # ---------------------------
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Bill To:"))

        self.customer_select = QComboBox()
        self.customer_select.setEditable(True)
        self.customer_select.currentIndexChanged.connect(
            self.on_billto_changed)
        row1.addWidget(self.customer_select, 2)

        row1.addWidget(QLabel("Ship To:"))
        self.ship_to_select = QComboBox()
        self.ship_to_select.setEditable(True)
        row1.addWidget(self.ship_to_select, 2)

        row1.addWidget(QLabel("Salesman:"))
        self.salesman_select = QComboBox()
        self.salesman_select.setEditable(True)
        row1.addWidget(self.salesman_select, 1)

        layout.addLayout(row1)

        # ---------------------------
        # Item search row
        # ---------------------------
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Item (code/name/scan):"))

        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText(
            "Type code or name (or scan barcode)")
        # Enter in item_search → focus qty_input
        self.item_search.returnPressed.connect(
            lambda: self.qty_input.setFocus())
        self.item_search.setMinimumWidth(260)
        self.item_search.setMaximumWidth(520)
        row2.addWidget(self.item_search, 2)

        row2.addWidget(QLabel("Qty:"))

        # QLineEdit for qty
        self.qty_input = QLineEdit()
        self.qty_input.setFixedWidth(120)
        self.qty_input.setFont(QFont("Segoe UI", 11))
        self.qty_input.setText("1")
        self.qty_input.setValidator(QIntValidator(1, 99999))
        # Enter in qty_input → Add item
        self.qty_input.returnPressed.connect(self.on_item_entered)
        row2.addWidget(self.qty_input)

        add_btn = QPushButton("➕ Add Item")
        add_btn.clicked.connect(self.on_item_entered)
        row2.addWidget(add_btn)

        refresh_btn = QPushButton("🔄 Refresh Items")
        refresh_btn.clicked.connect(self.load_item_options)
        row2.addWidget(refresh_btn)

        layout.addLayout(row2)

        # ---------------------------
        # Invoice table
        # ---------------------------
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(9)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Item Code", "Item Name", "Qty", "UOM",
             "Rate (₹)", "VAT %", "FOC", "Line Total (₹)", "Action"]
        )
        self.invoice_table.setEditTriggers(self.invoice_table.NoEditTriggers)
        layout.addWidget(self.invoice_table)

        # ---------------------------
        # Totals row
        # ---------------------------
        totals_row = QHBoxLayout()
        self.items_total_label = QLabel("Items Total: ₹0.00")
        self.items_total_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        totals_row.addWidget(self.items_total_label)

        totals_row.addStretch()
        totals_row.addWidget(QLabel("Discount (₹):"))
        self.discount_input = QLineEdit("0.00")
        self.discount_input.setFixedWidth(100)
        self.discount_input.editingFinished.connect(self.refresh_invoice_table)
        totals_row.addWidget(self.discount_input)

        self.vat_total_label = QLabel("VAT Total: ₹0.00")
        totals_row.addWidget(self.vat_total_label)

        self.grand_total_label = QLabel("Grand Total: ₹0.00")
        self.grand_total_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        totals_row.addWidget(self.grand_total_label)

        layout.addLayout(totals_row)

        # ---------------------------
        # Actions row
        # ---------------------------
        actions = QHBoxLayout()
        save_btn = QPushButton("💾 Save Invoice")
        save_btn.clicked.connect(self.save_invoice)
        actions.addWidget(save_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self.setLayout(layout)

    # ---------------------------
    # Loaders
    # ---------------------------
    def load_customer_options(self):
        self.customer_select.clear()
        self.customer_select.addItem("🚫 No Customer", None)
        try:
            for c in get_all_customers() or []:
                code, name = c[0], (c[1] if len(c) > 1 else c[0])
                self.customer_select.addItem(f"{name} ({code})", code)
        except Exception:
            pass
        self.populate_shipto_for_selected()

    def on_billto_changed(self, idx):
        self.populate_shipto_for_selected()

    def populate_shipto_for_selected(self):
        self.ship_to_select.clear()
        self.ship_to_select.addItem("🚫 No Ship To (none)", None)
        cust_code = self.customer_select.currentData()
        if not cust_code:
            return
        try:
            for o in get_outlets(cust_code) or []:
                out_id, outlet_name = o[0], (o[3] if len(o) > 3 else str(o[0]))
                self.ship_to_select.addItem(f"{outlet_name}", out_id)
        except Exception:
            pass

    def load_salesman_options(self):
        self.salesman_select.clear()
        self.salesman_select.addItem("🚫 No Salesman", None)
        try:
            for s in get_all_salesmen() or []:
                code, name = (s[0], s[1] if len(s) > 1 else s[0])
                self.salesman_select.addItem(f"{name} ({code})", code)
        except Exception:
            pass

    def load_item_options(self):
        self.item_lookup = {}
        completions = set()
        try:
            for r in get_consolidated_stock() or []:
                if hasattr(r, "get"):
                    code = r.get("item_code") or r.get("code") or ""
                    name = r.get("name") or ""
                    total_qty = _safe_float(r.get("total_qty") or 0)
                    uom = r.get("uom") or ""
                    price = _safe_float(r.get("selling_price") or 0.0)
                    vat = _safe_float(r.get("vat_percentage") or 5.0)
                else:
                    code = r[0] if len(r) > 0 else ""
                    name = r[1] if len(r) > 1 else ""
                    total_qty = _safe_float(r[2] if len(r) > 2 else 0)
                    uom = r[3] if len(r) > 3 else ""
                    price = _safe_float(r[4] if len(r) > 4 else 0.0)
                    vat = _safe_float(r[5] if len(r) > 5 else 5.0)

                if total_qty <= 0:
                    continue

                info = {"code": code, "name": name, "qty": total_qty,
                        "uom": uom, "rate": price, "vat": vat}
                self.item_lookup[code] = info
                key_combo = f"{code} - {name}"
                self.item_lookup[key_combo] = info
                completions.add(key_combo)
        except Exception:
            pass

        try:
            completer = QCompleter(sorted(list(completions)))
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.item_search.setCompleter(completer)
        except Exception:
            pass

    # ---------------------------
    # Add item
    # ---------------------------
    def on_item_entered(self):
        text = self.item_search.text().strip()
        if not text:
            return
        info = self.item_lookup.get(text)
        if not info:
            for k, v in self.item_lookup.items():
                if text.lower() in k.lower():
                    info = v
                    break
        if not info:
            QMessageBox.warning(self, "Invalid Item",
                                "Item not found or out of stock.")
            return

        try:
            qty = int(self.qty_input.text().strip() or "1")
        except Exception:
            qty = 1
        if qty <= 0:
            qty = 1

        line_id = str(uuid.uuid4())
        line = {"line_id": line_id, "code": info["code"], "name": info["name"],
                "qty": qty, "uom": info.get("uom", ""), "rate": float(info.get("rate", 0.0)),
                "vat": float(info.get("vat", 5.0)), "foc": False}
        self.invoice_items.append(line)

        self.qty_input.setText("1")
        self.item_search.setFocus()
        self.item_search.selectAll()
        self.refresh_invoice_table()

    # ---------------------------
    # Table / Totals
    # ---------------------------
    def refresh_invoice_table(self):
        self.invoice_table.setRowCount(0)
        items_total = vat_total = 0.0

        for it in self.invoice_items:
            r = self.invoice_table.rowCount()
            self.invoice_table.insertRow(r)
            self.invoice_table.setItem(r, 0, QTableWidgetItem(it["code"]))
            self.invoice_table.setItem(r, 1, QTableWidgetItem(it["name"]))

            qty_edit = QLineEdit(str(it["qty"]))
            qty_edit.setValidator(QIntValidator(0, 999999))
            qty_edit.setProperty("line_id", it["line_id"])
            qty_edit.editingFinished.connect(self._on_qty_changed)
            self.invoice_table.setCellWidget(r, 2, qty_edit)

            self.invoice_table.setItem(
                r, 3, QTableWidgetItem(it.get("uom", "")))
            self.invoice_table.setItem(
                r, 4, QTableWidgetItem(f"{it['rate']:.2f}"))
            self.invoice_table.setItem(
                r, 5, QTableWidgetItem(f"{it['vat']:.2f}%"))

            cb = QCheckBox()
            cb.setChecked(it.get("foc", False))
            cb.setProperty("line_id", it["line_id"])
            cb.stateChanged.connect(self._on_foc_toggled)
            self.invoice_table.setCellWidget(r, 6, cb)

            if it.get("foc", False):
                line_sub = line_vat = 0.0
            else:
                line_sub = it["qty"] * it["rate"]
                line_vat = line_sub * (it["vat"] / 100.0)
            line_total = line_sub + line_vat
            items_total += line_sub
            vat_total += line_vat
            self.invoice_table.setItem(
                r, 7, QTableWidgetItem(f"{line_total:.2f}"))

            btn = QToolButton()
            btn.setText("🗑️")
            btn.clicked.connect(partial(self._on_delete_line, it["line_id"]))
            self.invoice_table.setCellWidget(r, 8, btn)

        try:
            discount = float(self.discount_input.text().strip() or 0.0)
        except Exception:
            discount = 0.0
            self.discount_input.setText("0.00")

        taxable = max(0.0, items_total - discount)
        grand_total = taxable + vat_total
        self.items_total_label.setText(
            f"Items Total: ₹{items_total:.2f} (-₹{discount:.2f})")
        self.vat_total_label.setText(f"VAT Total: ₹{vat_total:.2f}")
        self.grand_total_label.setText(f"Grand Total: ₹{grand_total:.2f}")

    def _on_qty_changed(self):
        editor = self.sender()
        if editor:
            line_id = editor.property("line_id")
            try:
                new_qty = int(editor.text().strip() or "0")
            except Exception:
                new_qty = 0
            for it in self.invoice_items:
                if it["line_id"] == line_id:
                    it["qty"] = new_qty
                    break
            self.refresh_invoice_table()

    def _on_foc_toggled(self, state):
        cb = self.sender()
        if cb:
            line_id = cb.property("line_id")
            for it in self.invoice_items:
                if it["line_id"] == line_id:
                    it["foc"] = bool(state)
                    break
            self.refresh_invoice_table()

    def _on_delete_line(self, line_id):
        self.invoice_items = [
            it for it in self.invoice_items if it["line_id"] != line_id]
        self.refresh_invoice_table()

    # ---------------------------
    # Save invoice
    # ---------------------------
    def save_invoice(self):
        if not self.invoice_items:
            QMessageBox.warning(
                self, "No items", "Please add at least one item.")
            return

        bill_to = self.customer_select.currentData()
        selected_outlet_id = self.ship_to_select.currentData()
        salesman = self.salesman_select.currentData()

        payload = []
        for it in self.invoice_items:
            payload.append({
                "item_code": it["code"],
                "item_name": it["name"],
                "uom": it.get("uom"),
                "quantity": float(it["qty"]),
                "rate": float(it["rate"]),
                "vat_percentage": float(it["vat"]),
                "free": bool(it.get("foc", False))
            })

        try:
            discount_val = float(self.discount_input.text().strip() or 0.0)
        except Exception:
            discount_val = 0.0
            self.discount_input.setText("0.00")

        ship_to_param = str(selected_outlet_id) if selected_outlet_id else ""
        try:
            inv_no = create_invoice(
                bill_to, ship_to_param, payload,
                lpo_no="", discount=discount_val,
                customer_id=bill_to, salesman_id=salesman,
                outlet_id=selected_outlet_id
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Failed", f"Failed to create invoice: {e}")
            return

        QMessageBox.information(
            self, "Saved", f"Invoice {inv_no} created successfully.")
        self.invoice_items.clear()
        self.refresh_invoice_table()
        self.load_item_options()

        try:
            pdf_path = generate_invoice_pdf(inv_no, open_after=False)
            if pdf_path and os.path.exists(pdf_path):
                open_file_externally(pdf_path)
                QMessageBox.information(
                    self, "PDF", f"Invoice PDF generated:\n{pdf_path}")
        except Exception as e:
            QMessageBox.warning(self, "PDF Error",
                                f"PDF generation failed: {e}")
