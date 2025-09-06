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
    QDialogButtonBox
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt

# Models
from models.customer_model import get_all_customers, get_outlets
from models.salesman_model import get_all_salesmen
from models.stock_model import get_consolidated_stock
from models.invoice_model import create_invoice, fetch_invoice

# small helper to open file cross-platform


def open_file_externally(path):
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

        self.invoice_items = {}  # keyed by item_code
        self.item_lookup = {}  # mapping for search by code or name
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

        # Customer row
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

        # Invoice table: now includes VAT column
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(8)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Item Code", "Item Name", "Qty", "UOM",
                "Rate (₹)", "VAT %", "FOC", "Line Total (₹)"]
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

        # Actions
        actions = QHBoxLayout()
        save_btn = QPushButton("💾 Save Invoice")
        save_btn.clicked.connect(self.save_invoice)
        actions.addWidget(save_btn)

        preview_btn = QPushButton("📄 Preview PDF")
        preview_btn.clicked.connect(self.generate_preview_pdf)
        actions.addWidget(preview_btn)

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
                # c expected (customer_code, name, ...)
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
        # always include empty option
        self.ship_to_select.addItem("🚫 No Ship To", None)
        cust_code = self.customer_select.currentData()
        if not cust_code:
            return
        # Add the customer itself as an option (same address)
        self.ship_to_select.addItem(
            f"{self.customer_select.currentText()} (Same)", cust_code)
        try:
            outlets = get_outlets(cust_code) or []
            for o in outlets:
                # o expected (id, customer_id, outlet_code, outlet_name, address_line1, ...)
                oid = o[0]
                outlet_code = o[2] if len(o) > 2 else str(oid)
                outlet_name = o[3] if len(o) > 3 else outlet_code
                addr = ""
                if len(o) > 4 and o[4]:
                    addr = o[4]
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
        Build item_lookup mapping by code & name to support completer searching.
        """
        self.item_lookup = {}
        try:
            rows = get_consolidated_stock() or []
            # supported shapes: (item_code, name, total_qty, uom, selling_price, ...)
            for r in rows:
                if len(r) >= 5:
                    code, name, total_qty, uom, price = r[:5]
                elif len(r) >= 3:
                    code, name, total_qty = r[:3]
                    uom = ""
                    price = 0.0
                else:
                    continue
                try:
                    total_qty = float(total_qty or 0)
                except Exception:
                    total_qty = 0.0
                # only include if available
                if total_qty <= 0:
                    continue
                info = {"code": code, "name": name, "qty": total_qty, "uom": uom or "", "rate": float(
                    price or 0.0), "vat": r[5] if len(r) > 5 else 5.0}
                # map both lowercased name and code
                self.item_lookup[str(code).lower()] = info
                self.item_lookup[str(name).lower()] = info
                # raw code key
                self.item_lookup[str(code)] = info
            # build completer list (unique display values)
            completions = set()
            for v in self.item_lookup.values():
                completions.add(v["code"])
                completions.add(v["name"])
            completer = QCompleter(sorted(list(completions)))
            completer.setCaseSensitivity(False)
            self.item_search.setCompleter(completer)
        except Exception:
            self.item_lookup = {}

    # ---------------------------
    # Item add handling
    # ---------------------------
    def on_item_entered(self):
        text = self.item_search.text().strip()
        if not text:
            QMessageBox.warning(
                self, "No item", "Please enter item code or name.")
            return

        key = text if text in self.item_lookup else text.lower()
        info = self.item_lookup.get(key)
        # try partial name match too
        if not info:
            for k, v in self.item_lookup.items():
                if isinstance(k, str) and key.lower() in k:
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
                "rate": info.get("rate", 0.0),
                "vat": float(info.get("vat", 5.0)),
                "foc": False
            }

        self.item_search.clear()
        self.qty_input.setValue(1)
        self.refresh_invoice_table()

    def refresh_invoice_table(self):
        self.invoice_table.setRowCount(0)
        items_total = 0.0
        vat_total = 0.0

        for code, it in self.invoice_items.items():
            r = self.invoice_table.rowCount()
            self.invoice_table.insertRow(r)

            self.invoice_table.setItem(r, 0, QTableWidgetItem(str(code)))
            self.invoice_table.setItem(r, 1, QTableWidgetItem(str(it["name"])))
            self.invoice_table.setItem(r, 2, QTableWidgetItem(str(it["qty"])))
            self.invoice_table.setItem(
                r, 3, QTableWidgetItem(str(it.get("uom", ""))))
            self.invoice_table.setItem(
                r, 4, QTableWidgetItem(f"{it.get('rate', 0):.2f}"))
            self.invoice_table.setItem(
                r, 5, QTableWidgetItem(f"{it.get('vat', 5.0):.2f}%"))

            cb = QCheckBox()
            cb.setChecked(bool(it.get("foc", False)))
            cb.stateChanged.connect(
                partial(self.on_line_foc_changed, code, cb))
            self.invoice_table.setCellWidget(r, 6, cb)

            if it.get("foc", False):
                line_sub = 0.0
                line_vat = 0.0
            else:
                line_sub = it["qty"] * it["rate"]
                line_vat = line_sub * (it.get("vat", 5.0) / 100.0)

            line_total = line_sub + line_vat
            items_total += line_sub
            vat_total += line_vat

            self.invoice_table.setItem(
                r, 7, QTableWidgetItem(f"{line_total:.2f}"))

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

    def on_line_foc_changed(self, code, checkbox):
        self.invoice_items[code]["foc"] = bool(checkbox.isChecked())
        self.refresh_invoice_table()

    # ---------------------------
    # Save invoice (with DB-locked handling)
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

        # call create_invoice; it was patched to be safer, but still protect for DB busy
        try:
            inv_no = create_invoice(bill_to, ship_to, payload, lpo_no="",
                                    discount=discount_val, customer_id=bill_to, salesman_id=salesman)
        except sqlite3.OperationalError as e:
            # common sqlite "database is locked" shows as OperationalError
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

        # generate PDF and show preview (best-effort)
        try:
            header, items = fetch_invoice(inv_no)
            # open generated PDF using the same helper from your previous code; here we call a small helper
            # we'll generate a simple PDF file named Invoice_<inv_no>.pdf using a minimal function
            pdf_path = self._generate_minimal_pdf(inv_no, header, items)
            if pdf_path and os.path.exists(pdf_path):
                open_file_externally(pdf_path)
        except Exception:
            pass

    # minimal PDF generator (keeps code small). If you have a fancier generator keep using that.
    def _generate_minimal_pdf(self, invoice_no, header, items):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            fname = f"Invoice_{invoice_no}.pdf"
            c = canvas.Canvas(fname, pagesize=A4)
            w, h = A4
            y = h - 50
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, y, f"Invoice: {invoice_no}")
            y -= 24
            c.setFont("Helvetica", 10)
            if header:
                c.drawString(40, y, f"Billed To: {header[4] or ''}")
                y -= 14
                c.drawString(40, y, f"Ship To: {header[5] or ''}")
                y -= 20
            # header for items
            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, y, "S.No")
            c.drawString(80, y, "Item")
            c.drawString(380, y, "Qty")
            c.drawString(420, y, "Rate")
            c.drawString(480, y, "VAT%")
            c.drawString(530, y, "Amount")
            y -= 14
            c.setFont("Helvetica", 10)
            total = 0.0
            for idx, it in enumerate(items or [], start=1):
                # if DB rows from fetch_invoice: we expected (id, serial_no, item_code, item_name, uom, per_box, quantity, rate, sub_total, vat_pct, vat_amt, net_amount)
                if len(it) >= 12:
                    _, serial_no, item_code, item_name, uom, per_box, qty, rate, sub_total, vat_pct, vat_amt, net_amount = it[
                        :12]
                else:
                    # fallback: if items is list of simple tuples
                    try:
                        item_name, qty, uom, rate, vat_pct = it
                        sub_total = float(qty) * float(rate)
                        vat_amt = sub_total * (float(vat_pct) / 100.0)
                        net_amount = sub_total + vat_amt
                    except Exception:
                        continue
                c.drawString(40, y, str(idx))
                c.drawString(80, y, str(item_name)[:40])
                c.drawRightString(400, y, str(qty))
                c.drawRightString(440, y, f"{float(rate):.2f}")
                c.drawRightString(500, y, f"{float(vat_pct):.2f}%")
                c.drawRightString(560, y, f"{float(net_amount):.2f}")
                total += float(net_amount)
                y -= 14
                if y < 80:
                    c.showPage()
                    y = h - 40
            y -= 10
            c.setFont("Helvetica-Bold", 11)
            c.drawString(400, y, "Grand Total:")
            c.drawRightString(560, y, f"₹{total:.2f}")
            c.save()
            return os.path.abspath(fname)
        except Exception as e:
            print("PDF gen error:", e)
            return None

    def generate_preview_pdf(self):
        # quick preview using _generate_minimal_pdf with current items but no DB header
        items_preview = []
        for code, it in self.invoice_items.items():
            items_preview.append((it["name"], it["qty"], it.get(
                "uom", ""), it.get("rate", 0.0), it.get("vat", 5.0)))
        fname = f"Preview_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        # use same minimal generator but build fake header/items
        try:
            # create minimal canvas
            path = self._generate_minimal_pdf(
                f"PREVIEW-{datetime.now().strftime('%Y%m%d%H%M%S')}", None, items_preview)
            if path:
                open_file_externally(path)
        except Exception as e:
            QMessageBox.warning(self, "Preview Failed",
                                f"Preview generation failed: {e}")
