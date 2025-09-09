# ui/sales_report_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QComboBox, QDateEdit, QGridLayout, QSplitter, QFrame,
    QFileDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QIcon

from openpyxl import Workbook
import datetime
import os
import sqlite3
from typing import Optional, Union, List, Any

# Models
from models.invoice_model import (
    get_all_invoices,
    fetch_invoice,
    update_invoice_entry,
    cancel_invoice,
    get_sales_summary_range,
)


def parse_db_date(s):
    if not s:
        return None
    if isinstance(s, (datetime.date, datetime.datetime)):
        return s if isinstance(s, datetime.datetime) else datetime.datetime.combine(s, datetime.time())
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(s), fmt)
        except Exception:
            continue
    try:
        import dateutil.parser
        return dateutil.parser.parse(s)
    except Exception:
        return None


class SalesReportWindow(QWidget):
    """
    Sales / Invoice viewer.
    This version uses explicit mapping for tuple rows matching:
    (invoice_no, invoice_date, customer_id, bill_to, ship_to,
     total_amount, vat_amount, net_total, balance, paid_amount, status, salesman_id)
    It also supports dict-like rows (with keys like 'salesman_name' or 'customer_name').
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sales / Invoices")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setGeometry(150, 80, 1200, 750)

        self.invoices = []
        self.selected_invoice_no = None
        self.current_start = None
        self.current_end = None

        self.setup_ui()

        # default range: this month
        today = datetime.date.today()
        start = today.replace(day=1)
        end = today
        self.range_start.setDate(QDate(start.year, start.month, start.day))
        self.range_end.setDate(QDate(end.year, end.month, end.day))

        self.load_invoices()

    # Helpers
    def format_number(self, value):
        try:
            return f"{float(value or 0):.2f}"
        except Exception:
            return "0.00"

    def _safe_float(self, v, default=0.0):
        try:
            if v is None:
                return float(default)
            return float(v)
        except Exception:
            try:
                s = str(v)
                cleaned = s.replace(",", "").strip()
                return float(cleaned) if cleaned else float(default)
            except Exception:
                return float(default)

    def _get_field_generic(self, row_or_dict, candidates, default=None):
        """
        Try keys (if mapping-like) then indices (if sequence-like).
        candidates: list of str (column names) and/or int (indices),
        tried in order. Returns first non-empty found value or default.
        Works with sqlite3.Row, dict, tuple/list.
        """
        if row_or_dict is None:
            return default

        # Mapping-like first: sqlite3.Row supports .keys() and name indexing
        try:
            if hasattr(row_or_dict, "keys"):
                for c in candidates:
                    if isinstance(c, str):
                        try:
                            # works for sqlite3.Row and dict
                            v = row_or_dict[c]
                        except Exception:
                            v = None
                        if v not in (None, ""):
                            return v
                    elif isinstance(c, int):
                        # try numeric-string key first (some rows may have str indices)
                        try:
                            v = row_or_dict.get(c) if hasattr(
                                row_or_dict, "get") else None
                        except Exception:
                            v = None
                        if v not in (None, ""):
                            return v
                        try:
                            v = row_or_dict.get(str(c)) if hasattr(
                                row_or_dict, "get") else None
                        except Exception:
                            v = None
                        if v not in (None, ""):
                            return v
                return default
        except Exception:
            pass

        # Sequence-like fallback (tuple/list)
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

    # UI

    def setup_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        title = QLabel("Invoices & Sales")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        toolbar.addWidget(title)
        toolbar.addStretch()

        toolbar.addWidget(QLabel("From:"))
        self.range_start = QDateEdit(calendarPopup=True)
        self.range_start.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.range_start)

        toolbar.addWidget(QLabel("To:"))
        self.range_end = QDateEdit(calendarPopup=True)
        self.range_end.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.range_end)

        self.range_preset = QComboBox()
        self.range_preset.addItems(
            ["Custom", "Today", "This Week", "This Month", "This Quarter", "This Year"])
        self.range_preset.currentIndexChanged.connect(self.on_preset_changed)
        toolbar.addWidget(self.range_preset)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.on_load_clicked)
        toolbar.addWidget(load_btn)

        export_btn = QPushButton("Export (Excel)")
        export_btn.clicked.connect(self.export_invoices_excel)
        toolbar.addWidget(export_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.on_load_clicked)
        toolbar.addWidget(refresh_btn)

        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # Left: invoice list
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search invoice / customer / sales person / status")
        self.search_input.textChanged.connect(self.filter_invoices)
        row.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Date Desc", "Date Asc", "Customer", "Sales Person", "Pending Amount"])
        self.sort_combo.currentIndexChanged.connect(self.apply_sort)
        row.addWidget(self.sort_combo)
        left_layout.addLayout(row)

        # columns: invoice_no, date, customer, sales person, total, vat, net, paid, balance, status
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(10)
        self.invoice_table.setHorizontalHeaderLabels([
            "Invoice No", "Date", "Customer", "Sales Person",
            "Total", "VAT", "Net", "Paid", "Balance", "Status"
        ])
        self.invoice_table.setSelectionBehavior(self.invoice_table.SelectRows)
        self.invoice_table.setEditTriggers(self.invoice_table.NoEditTriggers)
        self.invoice_table.itemSelectionChanged.connect(
            self.on_invoice_selected)
        left_layout.addWidget(self.invoice_table)

        totals_row = QHBoxLayout()
        self.total_sales_lbl = QLabel("Total Sales: 0.00")
        self.total_purchase_lbl = QLabel("Total Purchase: 0.00")
        totals_row.addWidget(self.total_sales_lbl)
        totals_row.addSpacing(16)
        totals_row.addWidget(self.total_purchase_lbl)
        totals_row.addStretch()
        left_layout.addLayout(totals_row)

        splitter.addWidget(left)

        # Right: details
        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(8)

        hdr = QLabel("Invoice Details")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Bold))
        right_layout.addWidget(hdr)

        self.header_grid = QGridLayout()
        self.h_invoice_no = QLabel("-")
        self.h_date = QLabel("-")
        self.h_customer = QLabel("-")
        self.h_shipto = QLabel("-")
        self.h_salesperson = QLabel("-")  # gender-neutral label variable
        self.h_total = QLabel("-")
        self.h_paid = QLabel("-")
        self.h_balance = QLabel("-")
        self.h_status = QLabel("-")
        self.h_last_modified = QLabel("-")

        self.header_grid.addWidget(QLabel("Invoice No:"), 0, 0)
        self.header_grid.addWidget(self.h_invoice_no, 0, 1)
        self.header_grid.addWidget(QLabel("Date:"), 0, 2)
        self.header_grid.addWidget(self.h_date, 0, 3)

        self.header_grid.addWidget(QLabel("Customer:"), 1, 0)
        self.header_grid.addWidget(self.h_customer, 1, 1)

        self.header_grid.addWidget(QLabel("Ship To:"), 1, 2)
        self.header_grid.addWidget(self.h_shipto, 1, 3)

        self.header_grid.addWidget(QLabel("Sales Person:"), 2, 0)  # 2,0
        self.header_grid.addWidget(self.h_salesperson, 2, 1)  # 2,1

        self.header_grid.addWidget(QLabel("Last Modified:"), 2, 2)
        self.header_grid.addWidget(self.h_last_modified, 2, 3)

        self.header_grid.addWidget(QLabel("Total:"), 3, 0)
        self.header_grid.addWidget(self.h_total, 3, 1)
        self.header_grid.addWidget(QLabel("Paid:"), 3, 2)
        self.header_grid.addWidget(self.h_paid, 3, 3)

        self.header_grid.addWidget(QLabel("Balance:"), 4, 0)
        self.header_grid.addWidget(self.h_balance, 4, 1)
        self.header_grid.addWidget(QLabel("Status:"), 4, 2)
        self.header_grid.addWidget(self.h_status, 4, 3)

        right_layout.addLayout(self.header_grid)

        # items
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(8)
        self.items_table.setHorizontalHeaderLabels(
            ["S.No", "Item Code", "Item Name", "UOM", "Qty", "Rate", "VAT", "Line Total"])
        self.items_table.setEditTriggers(self.items_table.NoEditTriggers)
        right_layout.addWidget(self.items_table)

        # actions
        actions_row = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.edit_invoice_dialog)
        self.edit_btn.setEnabled(False)
        actions_row.addWidget(self.edit_btn)

        self.cancel_btn = QPushButton("Cancel Invoice (3 days)")
        self.cancel_btn.clicked.connect(self.cancel_invoice_action)
        self.cancel_btn.setEnabled(False)
        actions_row.addWidget(self.cancel_btn)

        self.view_pdf_btn = QPushButton("View PDF")
        self.view_pdf_btn.clicked.connect(self.on_view_invoice)
        self.view_pdf_btn.setEnabled(False)
        actions_row.addWidget(self.view_pdf_btn)

        actions_row.addStretch()
        right_layout.addLayout(actions_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)
        self.setLayout(root)

    # Load / populate
    def load_invoices(self, start_date=None, end_date=None, **filters):
        try:
            if start_date is None:
                start_date = self.range_start.date().toPyDate()
            if end_date is None:
                end_date = self.range_end.date().toPyDate()

            self.current_start = start_date
            self.current_end = end_date

            try:
                rows = get_all_invoices(start_date=start_date.isoformat(
                ), end_date=end_date.isoformat(), **filters)
            except TypeError:
                rows = get_all_invoices()
            self.invoices = rows or []
            self.populate_invoice_table(self.invoices)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load invoices: {e}")
            self.invoices = []
            self.populate_invoice_table([])

    def populate_invoice_table(self, invoices):
        """
        Fill left invoice table showing customer (human-friendly) and sales person name.
        Works with sqlite3.Row (mapping), dicts, or tuple rows.
        """
        self.invoice_table.setRowCount(0)
        total_sales = 0.0

        for r in invoices or []:
            if r is None:
                continue

            # invoice_no / date
            invoice_no = self._get_field_generic(
                r, ["invoice_no", "id", 0, 1], default="-")
            invoice_date = self._get_field_generic(
                r, ["invoice_date", 1, 2], default="")

            # customer display: prefer stored human-friendly bill_to then customer name/id
            customer = self._get_field_generic(
                r, ["bill_to", "customer_name", 3, 2], default="")

            # sales person: model returns 'salesman_name' (thanks to LEFT JOIN) — prefer that
            sales_person = self._get_field_generic(
                r, ["salesman_name", "salesman", 11, 15], default="")

            total_amount = float(self._get_field_generic(
                r, ["total_amount", 5], default=0.0) or 0.0)
            vat_amount = float(self._get_field_generic(
                r, ["vat_amount", 6], default=0.0) or 0.0)
            net_total = float(self._get_field_generic(r, ["net_total", 7], default=(
                total_amount + vat_amount)) or (total_amount + vat_amount))
            paid_amount = float(self._get_field_generic(
                r, ["paid_amount", 9], default=0.0) or 0.0)
            balance = float(self._get_field_generic(r, ["balance", 8], default=(
                net_total - paid_amount)) or (net_total - paid_amount))
            status = self._get_field_generic(r, ["status", 10], default="")

            # format date nicely
            dt = parse_db_date(invoice_date)
            date_str = dt.strftime(
                "%Y-%m-%d %H:%M") if dt else str(invoice_date)

            row_pos = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row_pos)
            self.invoice_table.setItem(
                row_pos, 0, QTableWidgetItem(str(invoice_no)))
            self.invoice_table.setItem(row_pos, 1, QTableWidgetItem(date_str))
            self.invoice_table.setItem(
                row_pos, 2, QTableWidgetItem(str(customer)))
            self.invoice_table.setItem(
                row_pos, 3, QTableWidgetItem(str(sales_person)))
            self.invoice_table.setItem(row_pos, 4, QTableWidgetItem(
                self.format_number(total_amount)))
            self.invoice_table.setItem(
                row_pos, 5, QTableWidgetItem(self.format_number(vat_amount)))
            self.invoice_table.setItem(
                row_pos, 6, QTableWidgetItem(self.format_number(net_total)))
            self.invoice_table.setItem(
                row_pos, 7, QTableWidgetItem(self.format_number(paid_amount)))
            self.invoice_table.setItem(
                row_pos, 8, QTableWidgetItem(self.format_number(balance)))
            self.invoice_table.setItem(
                row_pos, 9, QTableWidgetItem(str(status)))

            total_sales += net_total

        self.total_sales_lbl.setText(
            f"Total Sales: {total_sales:.2f}")    # Filtering / sorting

    def filter_invoices(self):
        q = self.search_input.text().strip().lower()
        if not q:
            self.populate_invoice_table(self.invoices)
            return
        filtered = []
        for r in self.invoices:
            combined = " ".join([str(x) for x in r]).lower()
            if q in combined:
                filtered.append(r)
        self.populate_invoice_table(filtered)

    def apply_sort(self):
        idx = self.sort_combo.currentIndex()
        rows = list(self.invoices)
        if idx == 0:
            rows.sort(key=lambda r: parse_db_date(self._get_field_generic(
                r, ["invoice_date", 1], "")) or datetime.datetime.min, reverse=True)
        elif idx == 1:
            rows.sort(key=lambda r: parse_db_date(self._get_field_generic(
                r, ["invoice_date", 1], "")) or datetime.datetime.min)
        elif idx == 2:
            rows.sort(key=lambda r: str(self._get_field_generic(
                r, ["customer_name", "bill_to", 3, 2], "")).lower())
        elif idx == 3:
            rows.sort(key=lambda r: str(self._get_field_generic(
                r, ["salesman_name", "salesman", 11], "")).lower())
        elif idx == 4:
            rows.sort(key=lambda r: float(self._get_field_generic(
                r, ["balance", 8], 0.0) or 0.0), reverse=True)
        self.populate_invoice_table(rows)

    # Selection & details
    def on_invoice_selected(self):
        row = self.invoice_table.currentRow()
        if row < 0:
            return
        inv_no_item = self.invoice_table.item(row, 0)
        if not inv_no_item:
            return
        inv_no = inv_no_item.text().strip()
        self.selected_invoice_no = inv_no
        try:
            header, items = fetch_invoice(inv_no)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to fetch invoice details: {e}")
            return

        # Show the detail side

        self.show_invoice_header(header)
        self.show_invoice_items(items)

        # determine editing/cancel permissions using generic getter
        inv_date = self._get_field_generic(
            header, ["invoice_date", 2, 1], default=None)
        dt = parse_db_date(inv_date)
        allow_edit = allow_cancel = False
        if dt:
            age_days = (datetime.datetime.now() - dt).days
            if age_days <= 3:
                allow_edit = allow_cancel = True

        status = self._get_field_generic(
            header, ["status", 15, 10], default="")
        status_str = str(status or "").lower()
        self.edit_btn.setEnabled(
            bool(allow_edit) and status_str in ("", "active", "partial"))
        self.cancel_btn.setEnabled(bool(allow_cancel) and (
            status_str not in ("cancelled", "canceled", "voided")))
        self.view_pdf_btn.setEnabled(True)

    def show_invoice_header(self, header):
        """
        header is sqlite3.Row (mapping-like) or a tuple/list.
        Read named columns where possible (salesman_name is provided by your LEFT JOIN).
        """
        if not header:
            self.h_invoice_no.setText("-")
            self.h_date.setText("-")
            self.h_customer.setText("-")
            self.h_shipto.setText("-")
            self.h_salesperson.setText("-")
            self.h_total.setText("-")
            self.h_paid.setText("-")
            self.h_balance.setText("-")
            self.h_status.setText("-")
            self.h_last_modified.setText("-")
            return

        invoice_no = self._get_field_generic(
            header, ["invoice_no", "id", 0, 1], default="-")
        invoice_date = self._get_field_generic(
            header, ["invoice_date", 1, 2], default="")
        bill_to = self._get_field_generic(
            header, ["bill_to", "bill_to_display", 3, 4], default="")
        ship_to = self._get_field_generic(
            header, ["ship_to", "ship_to_display", 5], default="")
        salesperson = self._get_field_generic(
            header, ["salesman_name", "salesman", 11, 15], default="")
        total_amount = float(self._get_field_generic(
            header, ["total_amount", 5, 8], default=0.0) or 0.0)
        vat_amount = float(self._get_field_generic(
            header, ["vat_amount", 6, 9], default=0.0) or 0.0)
        net_total = float(self._get_field_generic(header, ["net_total", 7, 10], default=(
            total_amount + vat_amount)) or (total_amount + vat_amount))
        paid_amount = float(self._get_field_generic(
            header, ["paid_amount", 9, 14], default=0.0) or 0.0)
        balance = float(self._get_field_generic(header, ["balance", 8, 13], default=(
            net_total - paid_amount)) or (net_total - paid_amount))
        status = self._get_field_generic(
            header, ["status", 15, "status"], default="")
        last_mod = self._get_field_generic(
            header, ["updated_at", "created_at", 12, 11], default=None)

        dt = parse_db_date(invoice_date) if invoice_date else None
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else str(invoice_date)

        self.h_invoice_no.setText(str(invoice_no))
        self.h_date.setText(date_str)
        self.h_customer.setText(str(bill_to or ""))
        self.h_shipto.setText(str(ship_to or ""))
        self.h_salesperson.setText(str(salesperson or ""))
        self.h_total.setText(self.format_number(net_total))
        self.h_paid.setText(self.format_number(paid_amount))
        self.h_balance.setText(self.format_number(balance))
        self.h_status.setText(str(status or ""))
        if last_mod:
            udt = parse_db_date(last_mod)
            self.h_last_modified.setText(udt.strftime(
                "%Y-%m-%d %H:%M") if udt else str(last_mod))
        else:
            self.h_last_modified.setText("-")

    def show_invoice_items(self, items):
        self.items_table.setRowCount(0)

        def safe_float(v, default=0.0):
            try:
                if v is None:
                    return float(default)
                return float(v)
            except Exception:
                try:
                    s = str(v).replace(",", "").strip()
                    return float(s) if s != "" else float(default)
                except Exception:
                    return float(default)

        for it in items or []:
            if hasattr(it, "get"):
                serial = it.get("serial_no") or it.get(
                    "id") or (self.items_table.rowCount() + 1)
                code = it.get("item_code") or it.get("code") or ""
                name = it.get("item_name") or it.get("name") or ""
                uom = it.get("uom") or ""
                qty = safe_float(it.get("quantity") or it.get("qty") or 0)
                rate = safe_float(
                    it.get("rate") or it.get("selling_price") or 0)
                vat_amt = safe_float(it.get("vat_amount")
                                     or it.get("vat") or 0)
                net = safe_float(it.get("net_amount") or it.get(
                    "line_total") or (qty * rate + vat_amt))
                foc = bool(it.get("free") or it.get("foc") or False)
            else:
                row = list(it) + [None] * 16
                serial = row[2] or row[0] or (self.items_table.rowCount() + 1)
                code = row[3] or row[1] or ""
                name = row[4] or row[2] or ""
                uom = row[5] or ""
                qty = 0.0
                for idx in (7, 6, 8, 5):
                    try:
                        if row[idx] is not None:
                            qty = safe_float(row[idx])
                            break
                    except Exception:
                        continue
                rate = 0.0
                for idx in (8, 6, 9):
                    try:
                        if row[idx] is not None:
                            rate = safe_float(row[idx])
                            break
                    except Exception:
                        continue
                vat_amt = 0.0
                for idx in (11, 10, 9):
                    try:
                        if row[idx] is not None:
                            vat_amt = safe_float(row[idx])
                            break
                    except Exception:
                        continue
                net = None
                for idx in (12, 11, 10):
                    try:
                        if row[idx] is not None:
                            net = safe_float(row[idx])
                            break
                    except Exception:
                        continue
                if net is None:
                    net = safe_float(qty * rate + vat_amt)
                foc = False
                for maybe in (13, 14, 15):
                    try:
                        val = row[maybe]
                        if val is not None:
                            if isinstance(val, bool):
                                foc = val
                                break
                            sval = str(val).strip().lower()
                            if sval in ("1", "true", "yes", "y"):
                                foc = True
                                break
                    except Exception:
                        pass

            r = self.items_table.rowCount()
            self.items_table.insertRow(r)
            self.items_table.setItem(r, 0, QTableWidgetItem(str(serial)))
            self.items_table.setItem(r, 1, QTableWidgetItem(str(code)))
            self.items_table.setItem(r, 2, QTableWidgetItem(str(name)))
            self.items_table.setItem(r, 3, QTableWidgetItem(str(uom)))
            qty_display = f"{int(qty) if float(qty).is_integer() else qty}"
            if foc:
                qty_display = f"{qty_display} (FOC)"
            self.items_table.setItem(r, 4, QTableWidgetItem(qty_display))
            self.items_table.setItem(
                r, 5, QTableWidgetItem(self.format_number(rate)))
            self.items_table.setItem(
                r, 6, QTableWidgetItem(self.format_number(vat_amt)))
            self.items_table.setItem(
                r, 7, QTableWidgetItem(self.format_number(net)))

    # Actions
    def on_view_invoice(self):
        row = self.invoice_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Invoice",
                                "Please select an invoice to view.")
            return
        invoice_no = self.invoice_table.item(row, 0).text().strip()
        try:
            from utils.pdf_helper import generate_invoice_pdf
            generate_invoice_pdf(invoice_no, open_after=True)
        except Exception as e:
            QMessageBox.warning(self, "Failed to open PDF",
                                f"Could not generate/open PDF:\n{e}")

    def edit_invoice_dialog(self):
        """
        Edit allowed fields for an invoice:
        - LPO No
        - Remarks
        - Record an additional Paid Amount (positive; cannot make total paid > net_total)
        Other fields (bill_to, ship_to, sales person, status) are not editable here.
        """
        if not self.selected_invoice_no:
            return

        header, _ = fetch_invoice(self.selected_invoice_no)
        if not header:
            QMessageBox.warning(self, "Error", "Invoice not found.")
            return

        # Get current values (support sqlite3.Row or tuple)
        def gf(h, candidates, default=None):
            # use same helper pattern as elsewhere; minimal inline version
            try:
                # dict-like (sqlite Row supports dict access)
                if hasattr(h, "get"):
                    for c in candidates:
                        if isinstance(c, str):
                            v = h.get(c)
                        else:
                            v = h.get(str(c)) if str(c) in h.keys() else None
                        if v not in (None, ""):
                            return v
                # sequence-like fallback
                if isinstance(h, (list, tuple)):
                    for c in candidates:
                        if isinstance(c, int) and 0 <= c < len(h):
                            v = h[c]
                            if v not in (None, ""):
                                return v
            except Exception:
                pass
            return default

        # read existing totals
        net_total = float(gf(header, ["total_amount", 10, 7], 0.0) or 0.0)
        print("Net total:", net_total)
        paid_amount_existing = float(
            gf(header, ["paid_amount", 14, 9], 0.0) or 0.0)
        lpo_existing = gf(header, ["lpo_no", 6], "") or ""
        remarks_existing = gf(header, ["remarks", 12], "") or ""

        # create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Invoice {self.selected_invoice_no}")
        layout = QFormLayout(dialog)

        # LPO and Remarks (editable)
        lpo_input = QLineEdit(str(lpo_existing))
        remarks_input = QLineEdit(str(remarks_existing))
        layout.addRow("LPO No:", lpo_input)
        layout.addRow("Remarks:", remarks_input)

        # Paid amount entry: amount to ADD to existing paid (not absolute unless you want absolute)
        paid_input = QLineEdit()
        paid_input.setPlaceholderText("Enter amount to record now (positive)")
        paid_input.setText("0.00")
        layout.addRow("Paid amount (now):", paid_input)

        # show current totals as read-only labels under the input to help user
        current_totals_lbl = QLabel(
            f"Current Paid: {paid_amount_existing:.2f}   Net Total: {net_total:.2f}")
        layout.addRow("", current_totals_lbl)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            # validate paid amount
            amt_text = paid_input.text().strip() or "0"
            try:
                amt = float(amt_text)
            except Exception:
                QMessageBox.warning(self, "Invalid amount",
                                    "Please enter a valid numeric paid amount.")
                return

            if amt < 0:
                QMessageBox.warning(self, "Invalid amount",
                                    "Paid amount must be positive (>= 0).")
                return

            new_paid_total = paid_amount_existing + amt
            # don't allow total paid to exceed net_total
            # If your business rule allows small rounding tolerance, you can adjust epsilon
            if new_paid_total - net_total > 0.0001:
                QMessageBox.warning(self, "Invalid amount",
                                    f"Recorded payment would make total paid ({new_paid_total:.2f}) exceed net total ({net_total:.2f}).")
                return

            # compute new balance (never negative)
            new_balance = max(0.0, net_total - new_paid_total)

            # update invoice: only allowed fields
            try:
                update_invoice_entry(
                    self.selected_invoice_no,
                    paid_amount=new_paid_total,
                    balance=new_balance,
                    lpo_no=lpo_input.text().strip(),
                    remarks=remarks_input.text().strip()
                )
                QMessageBox.information(self, "Success", "Invoice updated.")
                # reload to refresh both left list and right details
                self.load_invoices()
            except Exception as e:
                QMessageBox.warning(self, "Failed to update",
                                    f"Failed to update invoice: {e}")

    def cancel_invoice_action(self):
        if not self.selected_invoice_no:
            return

        try:
            header, _ = fetch_invoice(self.selected_invoice_no)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load invoice: {e}")
            return

        inv_date = self._get_field_generic(
            header, ["invoice_date", 1, 2], None)
        dt = parse_db_date(inv_date)
        if dt and (datetime.datetime.now() - dt).days > 3:
            QMessageBox.warning(self, "Cancel not allowed",
                                "Cancel allowed only within 3 days of invoice date.")
            return

        # Ask user for an optional reason (string) before confirming cancel
        reason, ok = QInputDialog.getText(
            self, "Cancel Reason (optional)",
            f"Provide a reason for cancelling invoice {self.selected_invoice_no} (optional):"
        )
        if not ok:
            # user cancelled reason dialog -> abort cancel
            return

        ok2 = QMessageBox.question(
            self, "Confirm Cancel",
            f"Cancel invoice {self.selected_invoice_no}?\nThis will mark the invoice as Cancelled."
            + ("\n\nReason: " + reason if reason else "")
        )
        if ok2 != QMessageBox.Yes:
            return

        try:
            # call model function which now flips status and stores reason (no stock adjustments)
            cancel_invoice(self.selected_invoice_no, reason=reason)
            QMessageBox.information(
                self, "Canceled", "Invoice marked as Cancelled.")
            self.load_invoices()
        except sqlite3.OperationalError as e:
            errmsg = str(e).lower()
            if "locked" in errmsg:
                QMessageBox.warning(
                    self, "Failed to cancel", "Database is busy/locked. Try again later and press Refresh.")
            else:
                QMessageBox.warning(self, "Failed to cancel",
                                    f"Failed to cancel invoice: {e}")
        except Exception as e:
            QMessageBox.warning(self, "Failed to cancel",
                                f"Failed to cancel invoice: {e}")

    # Export / report (kept simple)

    def export_invoices_excel(self):
        """
        Export current self.invoices to an .xlsx file including Cancel Reason column.
        Works with tuple rows (older model) or dict-like sqlite3.Row (newer model).
        """
        if not self.invoices:
            QMessageBox.information(self, "No data", "No invoices to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Invoices",
            f"invoices_{datetime.date.today().isoformat()}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not filename:
            return

        try:
            wb = Workbook()
            ws = wb.active

            # Header row: include Cancel Reason
            headers = [
                "Invoice No", "Date", "Customer (Bill To)", "Bill To (raw)", "Ship To",
                "Total", "VAT", "Net", "Paid", "Balance", "Status", "Sales Person", "Cancel Reason"
            ]
            ws.append(headers)

            # helper to safely get field from row/dict using your helpers if available
            def gf(row, candidates, default=""):
                # prefer your generic getter if available
                try:
                    if hasattr(self, "_get_field_generic"):
                        return self._get_field_generic(row, candidates, default)
                except Exception:
                    pass
                # fallback: dict-like
                try:
                    if hasattr(row, "get"):
                        for c in candidates:
                            if isinstance(c, str):
                                v = row.get(c, None)
                                if v not in (None, ""):
                                    return v
                            elif isinstance(c, int):
                                v = row.get(c, None) if hasattr(
                                    row, "get") else None
                                if v not in (None, ""):
                                    return v
                except Exception:
                    pass
                # fallback: sequence-like indices
                try:
                    if isinstance(row, (list, tuple)):
                        for c in candidates:
                            if isinstance(c, int) and 0 <= c < len(row):
                                v = row[c]
                                if v not in (None, ""):
                                    return v
                except Exception:
                    pass
                return default

            for r in self.invoices:
                rowdata = r if not isinstance(r, dict) else r

                invoice_no = gf(rowdata, ["invoice_no", "id", 0, 1], "")
                date_val = gf(rowdata, ["invoice_date", 1, 2], "")
                customer_display = gf(
                    rowdata, ["bill_to", "customer_name", 3, 2], "")
                bill_to_raw = gf(rowdata, ["bill_to", 4], "")
                ship_to = gf(rowdata, ["ship_to", 5], "")
                total = float(gf(rowdata, ["total_amount", 5, 8], 0.0) or 0.0)
                vat = float(gf(rowdata, ["vat_amount", 6, 9], 0.0) or 0.0)
                net = float(
                    gf(rowdata, ["net_total", 7, 10], (total + vat)) or (total + vat))
                paid = float(gf(rowdata, ["paid_amount", 9, 14], 0.0) or 0.0)
                balance = float(
                    gf(rowdata, ["balance", 8, 13], (net - paid)) or (net - paid))
                status = gf(rowdata, ["status", 10], "")
                sales_person = gf(
                    rowdata, ["salesman_name", "salesman", 11, 15], "")
                cancel_reason = gf(
                    rowdata, ["cancel_reason", "cancel_reason_text", "remarks", "remarks_cancel"], "")

                # Append row to worksheet. Use plain numbers for amounts (no currency symbol).
                ws.append([
                    str(invoice_no),
                    str(date_val),
                    str(customer_display),
                    str(bill_to_raw),
                    str(ship_to),
                    float(total),
                    float(vat),
                    float(net),
                    float(paid),
                    float(balance),
                    str(status),
                    str(sales_person),
                    str(cancel_reason)
                ])

            wb.save(filename)
            QMessageBox.information(
                self, "Exported", f"Exported to {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed",
                                f"Failed to export: {e}")

    # UI helpers

    def on_preset_changed(self, idx):
        today = datetime.date.today()
        if idx == 0:
            return
        if idx == 1:
            start = end = today
        elif idx == 2:
            start = today - datetime.timedelta(days=today.weekday())
            end = start + datetime.timedelta(days=6)
        elif idx == 3:
            start = today.replace(day=1)
            end = today
        elif idx == 4:
            q = (today.month - 1) // 3 + 1
            start_month = 3 * (q - 1) + 1
            start = today.replace(month=start_month, day=1)
            end_month = start_month + 2
            next_month = end_month % 12 + 1
            year = start.year + (1 if end_month > 12 else 0)
            last_day = (datetime.date(year, next_month, 1) -
                        datetime.timedelta(days=1)).day
            end = today.replace(
                month=(end_month if end_month <= 12 else 12), day=last_day)
        else:
            start = today.replace(month=1, day=1)
            end = today
        self.range_start.setDate(QDate(start.year, start.month, start.day))
        self.range_end.setDate(QDate(end.year, end.month, end.day))

    def on_load_clicked(self):
        self.load_invoices()
