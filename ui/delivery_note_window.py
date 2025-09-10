# ui/delivery_note_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QFormLayout,
    QSpinBox, QComboBox, QFrame, QFileDialog, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

import datetime
import os
from typing import List, Dict, Any, Optional

# invoice fetch
try:
    from models.invoice_model import fetch_invoice
except Exception:
    fetch_invoice = None

# stock_model provides item helpers in your project
try:
    from models.stock_model import get_consolidated_stock, get_latest_item_details_by_code
except Exception:
    get_consolidated_stock = None
    get_latest_item_details_by_code = None

# pdf helper (optional)
try:
    from utils.delivery_pdf import generate_delivery_note_pdf
except Exception:
    generate_delivery_note_pdf = None


def fmt_qty(q):
    try:
        qf = float(q)
        if int(qf) == qf:
            return str(int(qf))
        return f"{qf}"
    except Exception:
        return str(q)


class DeliveryNoteWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prepare Delivery Note")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setGeometry(220, 120, 900, 640)

        self.current_invoice_no: Optional[str] = None
        self.linked_header = None  # header row/dict
        self.items: List[Dict[str, Any]] = []  # item_code, item_name, uom, qty

        self._inline_item_map: Dict[str, Dict[str, Any]] = {}

        self._setup_ui()
        self._populate_inline_items()

    def _setup_ui(self):
        root = QVBoxLayout()
        self.setLayout(root)

        title = QLabel("Delivery Note / Pick List")
        title.setFont(QFont("SansSerif", 14, QFont.Bold))
        root.addWidget(title)

        # mode selection
        mode_row = QHBoxLayout()
        self.rb_link = QRadioButton("Link to invoice")
        self.rb_new = QRadioButton("New delivery note (no invoice)")
        self.rb_link.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_link)
        self.mode_group.addButton(self.rb_new)
        self.rb_link.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self.rb_link)
        mode_row.addWidget(self.rb_new)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # invoice controls
        inv_row = QHBoxLayout()
        inv_row.addWidget(QLabel("Invoice No:"))
        self.input_invoice_no = QLineEdit()
        inv_row.addWidget(self.input_invoice_no)
        self.btn_load_invoice = QPushButton("Load Invoice")
        # connect properly
        self.btn_load_invoice.clicked.connect(self.load_invoice)
        inv_row.addWidget(self.btn_load_invoice)
        inv_row.addStretch()
        root.addLayout(inv_row)

        # header display
        form = QFormLayout()
        self.lbl_invoice_display = QLabel("-")
        self.lbl_salesperson_display = QLabel("-")
        self.lbl_bill_to_display = QLabel("-")
        self.input_created_by = QLineEdit()
        self.input_created_by.setPlaceholderText(
            "Enter your name / prepared by")
        form.addRow("Invoice No:", self.lbl_invoice_display)
        form.addRow("Sales Person:", self.lbl_salesperson_display)
        form.addRow("Bill To:", self.lbl_bill_to_display)
        form.addRow("Created By:", self.input_created_by)
        root.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        root.addWidget(line)

        # inline item add controls
        inline = QHBoxLayout()
        inline.addWidget(QLabel("Item:"))
        self.inline_combo = QComboBox()
        self.inline_combo.setEditable(True)
        inline.addWidget(self.inline_combo, 1)
        inline.addWidget(QLabel("Unit:"))
        self.inline_uom = QLineEdit()
        self.inline_uom.setFixedWidth(100)
        inline.addWidget(self.inline_uom)
        inline.addWidget(QLabel("Qty:"))
        self.inline_qty = QSpinBox()
        self.inline_qty.setMinimum(1)
        self.inline_qty.setMaximum(10_000_000)
        inline.addWidget(self.inline_qty)
        self.btn_add_item = QPushButton("Add Item")
        self.btn_add_item.clicked.connect(self.on_add_item)
        inline.addWidget(self.btn_add_item)
        self.btn_delete_selected = QPushButton("Delete Selected")
        self.btn_delete_selected.clicked.connect(self.on_delete_selected)
        inline.addWidget(self.btn_delete_selected)
        inline.addStretch()
        root.addLayout(inline)

        # items table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["S.No", "Item Code", "Item Name", "Unit", "Qty"])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

        # bottom actions
        br = QHBoxLayout()
        self.btn_print = QPushButton("Print (PDF)")
        self.btn_print.clicked.connect(self.on_print)
        br.addStretch()
        br.addWidget(self.btn_print)
        root.addLayout(br)

        self._on_mode_change()

    def _on_mode_change(self):
        link_mode = self.rb_link.isChecked()
        self.input_invoice_no.setEnabled(link_mode)
        self.btn_load_invoice.setEnabled(link_mode)
        if not link_mode:
            self.current_invoice_no = None
            self.linked_header = None
            self.lbl_invoice_display.setText("-")
            self.lbl_salesperson_display.setText("-")
            self.lbl_bill_to_display.setText("-")
            self.items = []
            self._refresh_table()

    def _populate_inline_items(self):
        self._inline_item_map.clear()
        self.inline_combo.clear()
        entries = []
        if get_consolidated_stock:
            try:
                rows = get_consolidated_stock() or []
                for r in rows:
                    # r: (item_code, name, total_qty, uom, selling_price, low_level, is_below)
                    try:
                        item_code = r[0] or ""
                        name = r[1] or ""
                        uom = r[3] or ""
                        total_qty = float(r[2] or 0)
                    except Exception:
                        continue
                    display = f"{item_code} - {name}" if item_code else str(
                        name)
                    # optionally include available qty in display — keep concise
                    entries.append(display)
                    self._inline_item_map[display] = {
                        "item_code": item_code,
                        "item_name": name,
                        "uom": uom,
                        "total_qty": total_qty
                    }
            except Exception:
                pass
        if entries:
            self.inline_combo.addItems(entries)
        else:
            self.inline_combo.setEditable(True)

    def load_invoice(self):
        """Load invoice header + items (linked mode)."""
        if not fetch_invoice:
            QMessageBox.warning(self, "Unavailable",
                                "Invoice fetch function not available.")
            return
        inv_no = self.input_invoice_no.text().strip()
        if not inv_no:
            QMessageBox.warning(self, "Input", "Enter invoice number first.")
            return
        try:
            header, items = fetch_invoice(inv_no)
        except Exception as e:
            QMessageBox.warning(self, "Load failed",
                                f"Failed to fetch invoice: {e}")
            return
        if not header:
            QMessageBox.information(
                self, "Not found", f"Invoice '{inv_no}' not found.")
            return

        # helper to extract candidate keys/indices robustly
        def _get_field_generic(row_or_dict, candidates, default=""):
            if row_or_dict is None:
                return default
            # mapping-like
            try:
                if hasattr(row_or_dict, "keys") or hasattr(row_or_dict, "get"):
                    for c in candidates:
                        try:
                            if isinstance(c, str):
                                if hasattr(row_or_dict, "get"):
                                    v = row_or_dict.get(c)
                                else:
                                    v = row_or_dict[c] if c in row_or_dict else None
                            else:
                                v = None
                        except Exception:
                            v = None
                        if v not in (None, ""):
                            return v
            except Exception:
                pass
            # sequence-like fallback (indices)
            try:
                if isinstance(row_or_dict, (list, tuple)):
                    for c in candidates:
                        if isinstance(c, int) and 0 <= c < len(row_or_dict):
                            v = row_or_dict[c]
                            if v not in (None, ""):
                                return v
            except Exception:
                pass
            return default

        self.current_invoice_no = inv_no
        self.linked_header = header

        inv_display = _get_field_generic(
            header, ["invoice_no", "inv_no", 1, 0], default=inv_no)
        sp = _get_field_generic(header, [
                                "salesman_name", "sales_person", "salesperson", "salesman", 18, 17], default="")
        bill_to = _get_field_generic(
            header, ["bill_to", "bill_to_display", "customer_name", 4, 3], default="")

        self.lbl_invoice_display.setText(str(inv_display or "-"))
        self.lbl_salesperson_display.setText(str(sp or "-"))
        self.lbl_bill_to_display.setText(str(bill_to or "-"))

        # normalize items
        norm_items = []
        for it in (items or []):
            if isinstance(it, dict):
                code = it.get("item_code") or it.get("code") or ""
                name = it.get("item_name") or it.get(
                    "item") or it.get("name") or ""
                uom = it.get("uom") or ""
                try:
                    qty = float(it.get("quantity") or it.get("qty") or 0)
                except Exception:
                    qty = 0.0
            else:
                row = list(it) + [None] * 10
                code = row[3] or ""
                name = row[4] or ""
                uom = row[5] or ""
                try:
                    qty = float(row[7] or 0)
                except Exception:
                    qty = 0.0
            norm_items.append({"item_code": str(code), "item_name": str(
                name), "uom": str(uom), "qty": qty})
        self.items = norm_items
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(0)
        for idx, it in enumerate(self.items, start=1):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(idx)))
            self.table.setItem(r, 1, QTableWidgetItem(
                str(it.get("item_code") or "")))
            self.table.setItem(r, 2, QTableWidgetItem(
                str(it.get("item_name") or "")))
            self.table.setItem(r, 3, QTableWidgetItem(
                str(it.get("uom") or "")))
            self.table.setItem(r, 4, QTableWidgetItem(
                fmt_qty(it.get("qty") or 0)))

    def on_add_item(self):
        text = self.inline_combo.currentText().strip()
        if not text:
            QMessageBox.warning(self, "Item required",
                                "Select or type an item to add.")
            return

        info = self._inline_item_map.get(text)
        item_code = ""
        item_name = ""
        uom = (self.inline_uom.text().strip() or "")

        if info:
            item_code = info.get("item_code") or ""
            item_name = info.get("item_name") or text
            if not uom:
                uom = info.get("uom") or ""
        else:
            if " - " in text:
                parts = text.split(" - ", 1)
                item_code = parts[0].strip()
                item_name = parts[1].strip() if len(parts) > 1 else ""
            else:
                item_name = text

        if item_code and get_latest_item_details_by_code:
            try:
                row = get_latest_item_details_by_code(item_code)
                if row:
                    # (item_id, name, item_code, uom, vat_percentage, selling_price, total_qty)
                    try:
                        item_name_master = row[1] or ""
                        uom_master = row[3] or ""
                    except Exception:
                        item_name_master = ""
                        uom_master = ""
                    if item_name_master:
                        item_name = item_name_master
                    if uom_master:
                        uom = uom_master or uom
            except Exception:
                pass

        qty = int(self.inline_qty.value() or 0)
        if qty <= 0:
            QMessageBox.warning(
                self, "Qty", "Quantity must be greater than zero.")
            return

        self.items.append(
            {"item_code": item_code, "item_name": item_name, "uom": uom, "qty": qty})
        self._refresh_table()

    def on_delete_selected(self):
        rows = sorted(
            set([idx.row() for idx in self.table.selectedIndexes()]), reverse=True)
        if not rows:
            QMessageBox.information(
                self, "Select", "Select row(s) to delete first.")
            return
        ok = QMessageBox.question(
            self, "Confirm", f"Delete {len(rows)} selected row(s)?")
        if ok != QMessageBox.Yes:
            return
        for r in rows:
            if 0 <= r < len(self.items):
                del self.items[r]
        self._refresh_table()

    def _build_header_for_pdf(self) -> Dict[str, Any]:
        inv_no = self.lbl_invoice_display.text().strip()
        if inv_no in ("", "-") and self.linked_header:
            try:
                inv_no = self.linked_header.get("invoice_no") if hasattr(self.linked_header, "get") else (
                    self.linked_header[1] if len(self.linked_header) > 1 else "")
            except Exception:
                inv_no = inv_no
        sales_person = self.lbl_salesperson_display.text().strip()
        if sales_person in ("", "-") and self.linked_header:
            try:
                sales_person = (self.linked_header.get("salesman_name") if hasattr(self.linked_header, "get") else "") or str(
                    self.linked_header[18] if isinstance(self.linked_header, (list, tuple)) and len(self.linked_header) > 18 else "")
            except Exception:
                sales_person = sales_person
        bill_to = self.lbl_bill_to_display.text().strip()
        if bill_to in ("", "-") and self.linked_header:
            try:
                bill_to = (self.linked_header.get("bill_to") if hasattr(self.linked_header, "get") else "") or str(
                    self.linked_header[4] if isinstance(self.linked_header, (list, tuple)) and len(self.linked_header) > 4 else "")
            except Exception:
                bill_to = bill_to
        created_by = self.input_created_by.text().strip()
        return {
            "invoice_no": inv_no or "",
            "sales_person": sales_person or "",
            "salesperson": sales_person or "",
            "created_by": created_by or "",
            "bill_to": bill_to or "",
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    def on_print(self):
        if not self.items:
            QMessageBox.warning(
                self, "No items", "No items to print. Add some first.")
            return
        header = self._build_header_for_pdf()
        pdf_items = []
        for i, it in enumerate(self.items, start=1):
            pdf_items.append({
                "sl_no": i,
                "item_code": it.get("item_code") or "",
                "item_name": it.get("item_name") or "",
                "unit": it.get("uom") or it.get("unit") or "",
                "qty": it.get("qty") or 0,
                "remarks": it.get("remarks") or ""
            })

        company_profile = None
        try:
            from models.company_model import get_company_profile
            company_profile = get_company_profile()
        except Exception:
            company_profile = None

        default_name = f"delivery_note_{header.get('invoice_no') or datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", default_name, "PDF files (*.pdf)")
        if not path:
            return

        # prefer project helper
        if generate_delivery_note_pdf:
            try:
                generate_delivery_note_pdf(
                    path, header, pdf_items, company_profile=company_profile, open_after=True)
                QMessageBox.information(
                    self, "Printed", f"Delivery note saved to {path}")
                return
            except Exception as e:
                QMessageBox.warning(
                    self, "PDF helper failed", f"Helper raised error: {e}\nFalling back (if available).")

        # fallback minimal writer: try reportlab inline (very small fallback)
        try:
            # simple fallback uses generate_delivery_note_pdf if present; we've already tried it.
            # To keep this file concise we ask user to install reportlab or implement helper.
            QMessageBox.information(
                self, "PDF helper missing", "Please implement utils.delivery_pdf.generate_delivery_note_pdf or install reportlab and re-run.")
            return
        except Exception as e:
            QMessageBox.warning(self, "Failed", f"Failed to generate PDF: {e}")
            return
