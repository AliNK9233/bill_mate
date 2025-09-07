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

        # invoice_items becomes a list of line dicts (allows duplicate codes as separate lines)
        # list of { line_id, code, name, qty, uom, rate, vat, foc }
        self.invoice_items = []
        self.next_line_id = 1      # incremental id generator for invoice lines

        # mapping of keys -> info (unchanged semantics)
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
        # Create refresh buttons first
        # ---------------------------
        cust_refresh_btn = QPushButton("🔄")
        cust_refresh_btn.setFixedWidth(26)
        cust_refresh_btn.setToolTip("Refresh customers")
        cust_refresh_btn.clicked.connect(self.load_customer_options)

        ship_refresh_btn = QPushButton("🔄")
        ship_refresh_btn.setFixedWidth(26)
        ship_refresh_btn.setToolTip("Refresh outlets")
        # populate_shipto_for_selected will refresh outlets for currently selected customer
        ship_refresh_btn.clicked.connect(self.populate_shipto_for_selected)

        sales_refresh_btn = QPushButton("🔄")
        sales_refresh_btn.setFixedWidth(26)
        sales_refresh_btn.setToolTip("Refresh salesmen")
        sales_refresh_btn.clicked.connect(self.load_salesman_options)

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
        row1.addWidget(cust_refresh_btn)

        row1.addWidget(QLabel("Ship To:"))
        self.ship_to_select = QComboBox()
        self.ship_to_select.setEditable(True)
        row1.addWidget(self.ship_to_select, 2)
        row1.addWidget(ship_refresh_btn)

        row1.addWidget(QLabel("Salesman:"))
        self.salesman_select = QComboBox()
        self.salesman_select.setEditable(True)
        row1.addWidget(self.salesman_select, 1)
        row1.addWidget(sales_refresh_btn)

        layout.addLayout(row1)

        # ---------------------------
        # Item search row
        # ---------------------------
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
        # Totals row (invoice-level discount)
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
        # Actions row: Save only
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
        # add an empty option
        self.ship_to_select.addItem("🚫 No Ship To (none)", None)

        cust_code = self.customer_select.currentData()
        if not cust_code:
            return

        try:
            outlets = get_outlets(cust_code) or []
            for o in outlets:
                # o: (id, customer_id, outlet_code, outlet_name, address_line1, address_line2, city, ...)
                out_id = o[0]
                outlet_code = o[2] if len(o) > 2 else str(out_id)
                outlet_name = o[3] if len(o) > 3 else outlet_code
                # show only outlet name (you requested)
                self.ship_to_select.addItem(f"{outlet_name}", out_id)
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
                # store lookups:
                # allow direct code lookup
                self.item_lookup[code] = info
                key_combo = f"{code} - {name}"
                # allow "CODE - Name" lookup
                self.item_lookup[key_combo] = info
                # do NOT add bare code or bare name to completions -> prevents duplicates
                completions.add(key_combo)
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

        # Try exact lookups: code, "CODE - Name", or case-insensitive
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

        # create a new invoice line always (do not merge with existing lines)
        line_id = f"L{self.next_line_id}"
        self.next_line_id += 1
        line = {
            "line_id": line_id,
            "code": info["code"],
            "name": info["name"],
            "qty": qty,
            "uom": info.get("uom", ""),
            "rate": float(info.get("rate", 0.0)),
            "vat": float(info.get("vat", 5.0)),
            "foc": False
        }
        self.invoice_items.append(line)

        # reset input
        self.item_search.clear()
        self.qty_input.setValue(1)
        self.refresh_invoice_table()

    def refresh_invoice_table(self):
        """
        Populate invoice_table with current self.invoice_items (list).
        Qty is a QSpinBox cell widget (editable), FOC is a QCheckBox, Action column has delete button.
        """
        self.invoice_table.setRowCount(0)
        items_total = 0.0
        vat_total = 0.0

        for it in list(self.invoice_items):
            code = it["code"]
            r = self.invoice_table.rowCount()
            self.invoice_table.insertRow(r)

            self.invoice_table.setItem(r, 0, QTableWidgetItem(str(code)))
            self.invoice_table.setItem(r, 1, QTableWidgetItem(str(it["name"])))

            qty_spin = QSpinBox()
            qty_spin.setMinimum(0)
            qty_spin.setMaximum(999999)
            qty_spin.setValue(int(it["qty"]))
            qty_spin.setProperty("line_id", it["line_id"])
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
            cb.setProperty("line_id", it["line_id"])
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
            # connect with the line_id so deletion removes the correct entry
            btn.clicked.connect(partial(self._on_delete_line, it["line_id"]))
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
        line_id = widget.property("line_id")
        try:
            value = int(value)
        except Exception:
            return
        # find line by id and update qty
        for it in self.invoice_items:
            if it.get("line_id") == line_id:
                it["qty"] = value
                break
            self.refresh_invoice_table()

    def _on_foc_toggled(self, state):
        widget = self.sender()
        if widget is None:
            return
        line_id = widget.property("line_id")
        for it in self.invoice_items:
            if it.get("line_id") == line_id:
                it["foc"] = bool(state)
                break
        self.refresh_invoice_table()

    def _on_delete_line(self, line_id):
        # remove item with matching line_id
        self.invoice_items = [
            it for it in self.invoice_items if it.get("line_id") != line_id]
        self.refresh_invoice_table()
    # ---------------------------
    # Save invoice
    # ---------------------------

    def save_invoice(self):
        if not self.invoice_items:
            QMessageBox.warning(
                self, "No items", "Please add at least one item.")
            return

        # customer (may be id or code), selected outlet id (or None), salesman id
        bill_to = self.customer_select.currentData()
        selected_outlet_id = self.ship_to_select.currentData()  # may be None
        salesman = self.salesman_select.currentData()

        # build payload from either dict (code -> item) or list of item dicts
        payload = []
        if isinstance(self.invoice_items, dict):
            items_source = list(self.invoice_items.values())
        elif isinstance(self.invoice_items, list):
            items_source = self.invoice_items
        else:
            try:
                items_source = list(self.invoice_items)
            except Exception:
                items_source = []

        for it in items_source:
            try:
                code = it.get("code") or it.get("item_code") or ""
                name = it.get("name") or it.get("item_name") or ""
                qty = float(it.get("qty") or it.get("quantity") or 0)
                payload.append({
                    "item_code": code,
                    "item_name": name,
                    "uom": it.get("uom"),
                    "quantity": qty,
                    "rate": float(it.get("rate", 0.0)),
                    "vat_percentage": float(it.get("vat", it.get("vat_percentage", 5.0))),
                    "free": bool(it.get("foc", it.get("free", False)))
                })
            except Exception:
                # skip malformed item
                continue

        # invoice-level discount (compute here so we can use it in create_invoice call)
        try:
            discount_val = float(self.discount_input.text().strip() or 0.0)
        except Exception:
            discount_val = 0.0
            self.discount_input.setText("0.00")

        # ship_to param: we still pass a string for compatibility, but pass numeric outlet_id explicitly as outlet_id
        ship_to_param = str(selected_outlet_id) if selected_outlet_id else ""

        # call create_invoice; handle DB busy/errors
        try:
            inv_no = create_invoice(
                # legacy identifier for customer (code or id)
                bill_to,
                # legacy ship_to (we also pass outlet_id)
                ship_to_param,
                payload,
                lpo_no="",
                discount=discount_val,
                customer_id=bill_to,
                salesman_id=salesman,
                outlet_id=selected_outlet_id
            )
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

        # clear invoice items (handle both dict and list)
        if isinstance(self.invoice_items, dict):
            self.invoice_items.clear()
        else:
            # replace with empty list to avoid keeping stale references
            try:
                self.invoice_items[:] = []
            except Exception:
                self.invoice_items = []

        self.refresh_invoice_table()
        self.load_item_options()

        # generate PDF and open it (best-effort)
        try:
            from utils.pdf_helper import generate_invoice_pdf
            pdf_path = generate_invoice_pdf(inv_no, open_after=False)
            if pdf_path and os.path.exists(pdf_path):
                self._last_pdf_path = pdf_path
                open_file_externally(pdf_path)
                QMessageBox.information(
                    self, "PDF Generated", f"Invoice PDF generated and opened:\n{pdf_path}")
            else:
                QMessageBox.information(
                    self, "PDF", "Invoice saved but PDF was not created.")
        except Exception as e:
            QMessageBox.warning(
                self, "PDF Error", f"Invoice saved but PDF generation/open failed: {e}")
