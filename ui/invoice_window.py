# ui/invoice_window.py
import os
import sys
import subprocess
import sqlite3
from functools import partial
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QMessageBox, QComboBox, QCompleter, QCheckBox, QSpinBox, QDialog,
    QDialogButtonBox, QToolButton
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt

# Models
from models.customer_model import get_all_customers, get_outlets
from models.salesman_model import get_all_salesmen
from models.stock_model import get_consolidated_stock
from models.invoice_model import create_invoice, fetch_invoice

# PDF generator helper (keeps generation, but no UI preview)
from utils.pdf_helper import generate_invoice_pdf


def on_view_invoice(self):
    row = self.invoice_table.currentRow()
    if row < 0:
        QMessageBox.warning(self, "Select Invoice",
                            "Please select an invoice to view.")
        return
    invoice_no = self.invoice_table.item(row, 0).text().strip()
    try:
        from utils.pdf_helper import generate_invoice_pdf
        pdf_path = generate_invoice_pdf(invoice_no, open_after=True)
        QMessageBox.information(
            self, "PDF Opened", f"Invoice PDF generated and opened:\n{pdf_path}")
    except Exception as e:
        QMessageBox.warning(self, "Failed to open PDF",
                            f"Could not generate/open PDF:\n{e}")


def open_file_externally(path):
    """Open file with the system default viewer."""
    if not path or not os.path.exists(path):
        return
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform.startswith("darwin"):
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])


class InvoiceWindow(QWidget):
    """
    Invoice UI:
     - Item search shows "CODE - Name" suggestions.
     - Qty editable per-line via SpinBox.
     - Delete button per line.
     - FOC checkbox per line.
     - Live totals and invoice-level discount.
     - Save generates invoice and PDF silently (no preview buttons).
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧾 Invoice Generator")
        self.setGeometry(200, 100, 1100, 650)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        self.invoice_items = {}    # keyed by item_code -> dict
        self.item_lookup = {}      # mapping of keys -> info

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

        # Customer / ship / salesman row
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

        # Item search row
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Item (code/name/scan):"))
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText(
            "Type code or name (or scan barcode) and press Add")
        self.item_search.returnPressed.connect(self.on_item_entered)
        row2.addWidget(self.item_search, 3)

        row2.addWidget(QLabel("Qty:"))
        self.qty_input = QSpinBox()
        self.qty_input.setMinimum(1)
        self.qty_input.setMaximum(99999)
        row2.addWidget(self.qty_input, 0)

        add_btn = QPushButton("➕ Add Item")
        add_btn.clicked.connect(self.on_item_entered)
        row2.addWidget(add_btn)

        refresh_btn = QPushButton("🔄 Refresh Items")
        refresh_btn.clicked.connect(self.load_item_options)
        row2.addWidget(refresh_btn)

        layout.addLayout(row2)

        # Invoice table: columns: code, name, qty(spin), uom, rate, vat, foc, line_total, delete
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(9)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Item Code", "Item Name", "Qty", "UOM",
                "Rate (₹)", "VAT %", "FOC", "Line Total (₹)", "Action"]
        )
        self.invoice_table.setEditTriggers(self.invoice_table.NoEditTriggers)
        layout.addWidget(self.invoice_table)

        # Totals row (invoice-level discount)
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

        # Actions row: Save only (preview and view removed)
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
            customers = get_all_customers() or []
            for c in customers:
                code = c[0]
                name = c[1] if len(c) > 1 else c[0]
                self.customer_select.addItem(f"{name} ({code})", code)
        except Exception:
            pass
        self.populate_shipto_for_selected()

    def on_billto_changed(self, idx):
        self.populate_shipto_for_selected()

    def populate_shipto_for_selected(self):
        self.ship_to_select.clear()
        self.ship_to_select.addItem("🚫 No Ship To", None)
        cust_code = self.customer_select.currentData()
        if not cust_code:
            return
        self.ship_to_select.addItem(
            f"{self.customer_select.currentText()} (Same)", cust_code)
        try:
            outlets = get_outlets(cust_code) or []
            for o in outlets:
                outlet_code = o[2] if len(o) > 2 else str(o[0])
                outlet_name = o[3] if len(o) > 3 else outlet_code
                addr = (o[4] if len(o) > 4 else "") or ""
                display = outlet_name + f" ({outlet_code})"
                if addr:
                    display += f" - {addr}"
                self.ship_to_select.addItem(display, outlet_code)
        except Exception:
            pass

    def load_salesman_options(self):
        self.salesman_select.clear()
        self.salesman_select.addItem("🚫 No Salesman", None)
        try:
            salesmen = get_all_salesmen() or []
            for s in salesmen:
                code = s[0] if len(s) > 0 else s
                name = s[1] if len(s) > 1 else code
                self.salesman_select.addItem(f"{name} ({code})", code)
        except Exception:
            pass

    def load_item_options(self):
        """
        Build item_lookup mapping and completer options.
        Completions include "CODE - Name", "CODE", "Name".
        """
        self.item_lookup = {}
        completions = set()
        try:
            rows = get_consolidated_stock() or []
            for r in rows:
                code = r[0] if len(r) > 0 else ""
                name = r[1] if len(r) > 1 else ""
                total_qty = float(r[2] or 0)
                uom = r[3] if len(r) > 3 else ""
                price = float(r[4] or 0.0)
                vat = float(r[5]) if len(r) > 5 and isinstance(
                    r[5], (int, float)) else 5.0
                if total_qty <= 0:
                    continue
                info = {"code": code, "name": name, "qty": total_qty,
                        "uom": uom, "rate": price, "vat": vat}
                self.item_lookup[code] = info
                self.item_lookup[name.lower()] = info
                key_combo = f"{code} - {name}"
                self.item_lookup[key_combo] = info
                completions.add(key_combo)
                completions.add(code)
                completions.add(name)
        except Exception:
            pass

        try:
            completer = QCompleter(sorted(list(completions)))
            completer.setCaseSensitivity(False)
            self.item_search.setCompleter(completer)
        except Exception:
            pass

    # ---------------------------
    # Item add handling
    # ---------------------------
    def on_item_entered(self):
        text = self.item_search.text().strip()
        if not text:
            QMessageBox.warning(
                self, "No item", "Please enter item code or name.")
            return

        info = self.item_lookup.get(text) or self.item_lookup.get(
            text.lower()) or self.item_lookup.get(text.upper())
        if not info:
            for k, v in self.item_lookup.items():
                if isinstance(k, str) and text.lower() in k.lower():
                    info = v
                    break

        if not info:
            QMessageBox.warning(self, "Invalid Item",
                                "Item not found or out of stock.")
            return

        qty = int(self.qty_input.value())
        if qty <= 0:
            QMessageBox.warning(self, "Invalid Qty", "Quantity must be > 0.")
            return
        if qty > info["qty"]:
            QMessageBox.warning(self, "Stock Error",
                                f"Only {info['qty']} units available.")
            return

        code = info["code"]
        if code in self.invoice_items:
            self.invoice_items[code]["qty"] += qty
        else:
            self.invoice_items[code] = {
                "code": code,
                "name": info["name"],
                "qty": qty,
                "uom": info.get("uom", ""),
                "rate": float(info.get("rate", 0.0)),
                "vat": float(info.get("vat", 5.0)),
                "foc": False
            }

        self.item_search.clear()
        self.qty_input.setValue(1)
        self.refresh_invoice_table()

    def refresh_invoice_table(self):
        """
        Populate invoice_table with current self.invoice_items.
        Qty is a QSpinBox cell widget (editable), FOC is a QCheckBox, Action column has delete button.
        """
        self.invoice_table.setRowCount(0)
        items_total = 0.0
        vat_total = 0.0

        for code, it in list(self.invoice_items.items()):
            r = self.invoice_table.rowCount()
            self.invoice_table.insertRow(r)

            self.invoice_table.setItem(r, 0, QTableWidgetItem(str(code)))
            self.invoice_table.setItem(r, 1, QTableWidgetItem(str(it["name"])))

            qty_spin = QSpinBox()
            qty_spin.setMinimum(0)
            qty_spin.setMaximum(999999)
            qty_spin.setValue(int(it["qty"]))
            qty_spin.setProperty("item_code", code)
            qty_spin.valueChanged.connect(self._on_qty_changed)
            self.invoice_table.setCellWidget(r, 2, qty_spin)

            self.invoice_table.setItem(
                r, 3, QTableWidgetItem(str(it.get("uom", ""))))
            self.invoice_table.setItem(
                r, 4, QTableWidgetItem(f"{it.get('rate', 0):.2f}"))
            self.invoice_table.setItem(
                r, 5, QTableWidgetItem(f"{it.get('vat', 5.0):.2f}%"))

            cb = QCheckBox()
            cb.setChecked(bool(it.get("foc", False)))
            cb.setProperty("item_code", code)
            cb.stateChanged.connect(self._on_foc_toggled)
            self.invoice_table.setCellWidget(r, 6, cb)

            if it.get("foc", False):
                line_sub = 0.0
                line_vat = 0.0
            else:
                line_sub = float(it["qty"]) * float(it["rate"])
                line_vat = line_sub * (float(it.get("vat", 5.0)) / 100.0)
            line_total = line_sub + line_vat
            items_total += line_sub
            vat_total += line_vat
            self.invoice_table.setItem(
                r, 7, QTableWidgetItem(f"{line_total:.2f}"))

            btn = QToolButton()
            btn.setText("🗑️")
            btn.setToolTip("Remove this line")
            btn.clicked.connect(partial(self._on_delete_line, code))
            btn.setAutoRaise(True)
            self.invoice_table.setCellWidget(r, 8, btn)

        # Totals & discount
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

    # ---------- callbacks for widgets inside table ----------
    def _on_qty_changed(self, value):
        widget = self.sender()
        if widget is None:
            return
        code = widget.property("item_code")
        try:
            value = int(value)
        except Exception:
            return
        if code in self.invoice_items:
            self.invoice_items[code]["qty"] = value
            self.refresh_invoice_table()

    def _on_foc_toggled(self, state):
        widget = self.sender()
        if widget is None:
            return
        code = widget.property("item_code")
        if code in self.invoice_items:
            self.invoice_items[code]["foc"] = bool(state)
            self.refresh_invoice_table()

    def _on_delete_line(self, code):
        if code in self.invoice_items:
            del self.invoice_items[code]
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
        ship_to = self.ship_to_select.currentData() or self.ship_to_select.currentText()
        salesman = self.salesman_select.currentData()

        payload = []
        for code, it in self.invoice_items.items():
            payload.append({
                "item_code": code,
                "item_name": it["name"],
                "uom": it.get("uom"),
                "per_box_qty": 1,
                "quantity": it["qty"],
                "rate": it["rate"],
                "vat_percentage": it.get("vat", 5.0),
                "free": bool(it.get("foc", False))
            })

        try:
            discount_val = float(self.discount_input.text().strip() or 0.0)
        except Exception:
            discount_val = 0.0

        # call create_invoice; handle DB busy/errors
        try:
            inv_no = create_invoice(bill_to, ship_to, payload, lpo_no="",
                                    discount=discount_val, customer_id=bill_to, salesman_id=salesman)
        except sqlite3.OperationalError as e:
            QMessageBox.warning(self, "Failed to create invoice",
                                f"Failed to create invoice: {e}")
            return
        except Exception as e:
            QMessageBox.warning(self, "Failed to create invoice",
                                f"Failed to create invoice: {e}")
            return

        QMessageBox.information(
            self, "Saved", f"Invoice {inv_no} created successfully.")
        # clear and refresh
        self.invoice_items.clear()
        self.refresh_invoice_table()
        self.load_item_options()

        # generate PDF and open it (best-effort)
        try:
            # local import to avoid breaking if utils missing at module import time
            from utils.pdf_helper import generate_invoice_pdf
            pdf_path = generate_invoice_pdf(inv_no, open_after=False)
            if pdf_path and os.path.exists(pdf_path):
                # save last path and open with system viewer
                self._last_pdf_path = pdf_path
                open_file_externally(pdf_path)
                QMessageBox.information(self, "PDF Generated",
                                        f"Invoice PDF generated and opened:\n{pdf_path}")
            else:
                QMessageBox.information(self, "PDF",
                                        "Invoice saved but PDF was not created.")
        except Exception as e:
            # do not fail the save for PDF problems — notify user
            QMessageBox.warning(
                self, "PDF Error", f"Invoice saved but PDF generation/open failed: {e}")
