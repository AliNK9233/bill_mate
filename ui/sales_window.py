# ui/sales_report_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QComboBox, QDateEdit, QGridLayout, QSplitter, QFrame,
    QFileDialog
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QIcon

from openpyxl import Workbook
import datetime
import os
import sqlite3
from typing import Optional, Union, List, Tuple, Any

# Models (these must exist in your models.invoice_model)
from models.invoice_model import (
    get_all_invoices,
    fetch_invoice,
    update_invoice_entry,
    cancel_invoice,
    get_sales_summary_range,
)

# PDF helper (optional)
# from utils.pdf_helper import generate_invoice_pdf


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
    Sales / Invoice viewer and actions.
    Defensive about the DB row shapes: supports both tuple/list rows and dict-like rows
    returned by model functions.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("💸 Sales / Invoices")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setGeometry(150, 80, 1200, 750)

        self.invoices = []
        self.selected_invoice_no = None
        self.current_start = None
        self.current_end = None

        self.setup_ui()

        # default date range: this month
        today = datetime.date.today()
        start = today.replace(day=1)
        end = today
        self.range_start.setDate(QDate(start.year, start.month, start.day))
        self.range_end.setDate(QDate(end.year, end.month, end.day))

        self.load_invoices()

    # -------------------------
    # Helpers
    # -------------------------
    def format_currency(self, val) -> str:
        # Return numeric string without currency symbol, two decimals
        try:
            return f"{float(val or 0):.2f}"
        except Exception:
            try:
                cleaned = "".join(ch for ch in str(
                    val) if (ch.isdigit() or ch in ".-"))
                return f"{float(cleaned or 0):.2f}"
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
                cleaned = s.replace(",", "").replace("₹", "").strip()
                return float(cleaned) if cleaned else float(default)
            except Exception:
                return float(default)

    def _get_field(self, row_or_dict: Union[dict, tuple, list, None], candidates: List[Union[str, int]], default: Any = None):
        """
        Try to get a value from a dict-like or sequence-like header/item.
        candidates is a list of possible keys (str) or indices (int) in order of preference.
        """
        if row_or_dict is None:
            return default

        # dict-like
        try:
            if hasattr(row_or_dict, "get"):
                for c in candidates:
                    if isinstance(c, str):
                        v = row_or_dict.get(c, None)
                        if v is not None and v != "":
                            return v
                    elif isinstance(c, int):
                        # some dicts may have numeric-string keys
                        v = row_or_dict.get(c, None)
                        if v is not None and v != "":
                            return v
                        v2 = row_or_dict.get(str(c), None)
                        if v2 is not None and v2 != "":
                            return v2
                return default
        except Exception:
            pass

        # sequence-like
        try:
            if isinstance(row_or_dict, (tuple, list)):
                for c in candidates:
                    if isinstance(c, int):
                        if 0 <= c < len(row_or_dict):
                            v = row_or_dict[c]
                            if v is not None and v != "":
                                return v
        except Exception:
            pass

        return default

    # -------------------------
    # UI
    # -------------------------
    def setup_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # toolbar
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

        load_btn = QPushButton("🔍 Load")
        load_btn.clicked.connect(self.on_load_clicked)
        toolbar.addWidget(load_btn)

        export_btn = QPushButton("📥 Export Invoices (Excel)")
        export_btn.clicked.connect(self.export_invoices_excel)
        toolbar.addWidget(export_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setToolTip("Reload latest invoices from database")
        refresh_btn.clicked.connect(self.on_load_clicked)
        toolbar.addWidget(refresh_btn)

        root.addLayout(toolbar)  # end toolbar

        # splitter: left invoice list, right detail pane
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # Left
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search invoice no / customer / sales person / status")
        self.search_input.textChanged.connect(self.filter_invoices)
        search_row.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Date Desc", "Date Asc", "Customer", "Sales Person", "Pending Amount"])
        self.sort_combo.currentIndexChanged.connect(self.apply_sort)
        search_row.addWidget(self.sort_combo)
        left_layout.addLayout(search_row)

        # NOTE: columns changed -> Invoice No, Date, Customer, Sales Person, Total, VAT, Net, Paid, Balance, Status
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

        # Right (details)
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
        self.h_salesman = QLabel("-")  # label text later shown as Sales Person
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

        self.header_grid.addWidget(QLabel("Ship To:"), 2, 0)
        self.header_grid.addWidget(self.h_shipto, 2, 1)

        self.header_grid.addWidget(QLabel("Sales Person:"), 1, 2)
        self.header_grid.addWidget(self.h_salesman, 1, 3)

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

        # items table (keep existing columns)
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(8)
        self.items_table.setHorizontalHeaderLabels([
            "S.No", "Item Code", "Item Name", "UOM", "Qty", "Rate", "VAT", "Line Total"
        ])
        self.items_table.setEditTriggers(self.items_table.NoEditTriggers)
        right_layout.addWidget(self.items_table)

        # actions (unchanged)
        actions_row = QHBoxLayout()
        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self.edit_invoice_dialog)
        self.edit_btn.setEnabled(False)
        actions_row.addWidget(self.edit_btn)

        self.cancel_btn = QPushButton("🗑️ Cancel Invoice (3 days)")
        self.cancel_btn.clicked.connect(self.cancel_invoice_action)
        self.cancel_btn.setEnabled(False)
        actions_row.addWidget(self.cancel_btn)

        self.view_pdf_btn = QPushButton("📄 View PDF")
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

    # -------------------------
    # Load / populate
    # -------------------------
    def load_invoices(self, start_date=None, end_date=None, **filters):
        """
        Load invoices using model helper. Attempts get_all_invoices(start_date=..., end_date=...)
        and falls back to parameterless get_all_invoices() if model signature differs.
        """
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
        Fill left invoice table showing human-friendly customer and sales person names (not ids).
        Defensive about different shapes returned by the model.
        """
        self.invoice_table.setRowCount(0)
        total_sales = 0.0

        for r in invoices or []:
            if r is None:
                continue
            # Use the generic accessor; pass the raw row/dict to it
            row = r

            # Try common mappings (works for both tuple and dict via _get_field)
            invoice_no = self._get_field(
                row, ["invoice_no", "id", 0, 1], default="-")
            invoice_date = self._get_field(
                row, ["invoice_date", 1, 2], default="")
            # Prefer customer_name (if model returns it), then bill_to (human), then customer id/display
            customer = self._get_field(
                row, ["customer_name", "customer", "bill_to", 3, 2], default="")
            # Sales person: prefer salesman_name (returned by JOIN), then salesman, then id
            sales_person = self._get_field(
                row, ["salesman_name", "salesman", "salesman_id", 11, 16], default="")

            total_amount = self._safe_float(self._get_field(
                row, ["total_amount", 5], default=0.0))
            vat_amount = self._safe_float(self._get_field(
                row, ["vat_amount", 6], default=0.0))
            net_total = self._safe_float(self._get_field(
                row, ["net_total", 7], default=(total_amount + vat_amount)))
            paid_amount = self._safe_float(self._get_field(
                row, ["paid_amount", 9], default=0.0))
            balance = self._safe_float(self._get_field(
                row, ["balance", 8], default=(net_total - paid_amount)))
            status = self._get_field(row, ["status", 10], default="")

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
                self.format_currency(total_amount)))
            self.invoice_table.setItem(row_pos, 5, QTableWidgetItem(
                self.format_currency(vat_amount)))
            self.invoice_table.setItem(
                row_pos, 6, QTableWidgetItem(self.format_currency(net_total)))
            self.invoice_table.setItem(row_pos, 7, QTableWidgetItem(
                self.format_currency(paid_amount)))
            self.invoice_table.setItem(
                row_pos, 8, QTableWidgetItem(self.format_currency(balance)))
            self.invoice_table.setItem(
                row_pos, 9, QTableWidgetItem(str(status)))

            total_sales += net_total

        self.total_sales_lbl.setText(f"Total Sales: {total_sales:.2f}")

    # -------------------------
    # Filter / sort
    # -------------------------
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
            rows.sort(key=lambda r: parse_db_date(self._get_field(
                r, ["invoice_date", 1, 2], default="")) or datetime.datetime.min, reverse=True)
        elif idx == 1:
            rows.sort(key=lambda r: parse_db_date(self._get_field(
                r, ["invoice_date", 1, 2], default="")) or datetime.datetime.min)
        elif idx == 2:
            rows.sort(key=lambda r: str(self._get_field(
                r, ["customer_name", "bill_to", 3, 2], default="")).lower())
        elif idx == 3:
            rows.sort(key=lambda r: str(self._get_field(
                r, ["salesman_name", "salesman", 11, 16], default="")).lower())
        elif idx == 4:
            rows.sort(key=lambda r: float(self._get_field(
                r, ["balance", 8], default=0.0) or 0.0), reverse=True)
        self.populate_invoice_table(rows)

    # -------------------------
    # Selection & details
    # -------------------------
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

        # Show details
        self.show_invoice_header(header)
        self.show_invoice_items(items)

        # enable/disable actions
        inv_date = self._get_field(
            header, ["invoice_date", 2, 1], default=None)
        dt = parse_db_date(inv_date)
        allow_edit = allow_cancel = False
        if dt:
            age_days = (datetime.datetime.now() - dt).days
            if age_days <= 3:
                allow_edit = allow_cancel = True

        status = self._get_field(header, ["status", 15, 10], default="")
        status_str = str(status or "").lower()
        self.edit_btn.setEnabled(
            bool(allow_edit) and status_str in ("", "active", "partial"))
        self.cancel_btn.setEnabled(bool(allow_cancel) and (
            status_str not in ("cancelled", "canceled", "voided")))
        self.view_pdf_btn.setEnabled(True)

    def show_invoice_header(self, header):
        """
        Display the invoice header in the right panel. Accepts both dict-rows and tuple/list rows.
        """
        if not header:
            self.h_invoice_no.setText("-")
            self.h_date.setText("-")
            self.h_customer.setText("-")
            self.h_shipto.setText("-")
            self.h_salesman.setText("-")
            self.h_total.setText("-")
            self.h_paid.setText("-")
            self.h_balance.setText("-")
            self.h_status.setText("-")
            self.h_last_modified.setText("-")
            return

        for i, v in enumerate(header):
            print(f"Header[{i}]: {v}")

        invoice_no = self._get_field(
            header, ["invoice_no", "id", 1, 2], default="-")
        invoice_date = self._get_field(
            header, ["invoice_date", 3, 3], default="")
        bill_to = self._get_field(
            header, ["bill_to", 4, "bill_to_display"], default="")
        ship_to = self._get_field(
            header, ["ship_to", 5, "ship_to_display"], default="")
        sales_person = self._get_field(
            header, ["salesman_name", "salesman", "salesman_id", 18, 19], default="")
        total_amount = self._safe_float(self._get_field(
            header, ["total_amount", 9, 5], default=0.0))
        vat_amount = self._safe_float(self._get_field(
            header, ["vat_amount", 10, 6], default=0.0))
        net_total = self._safe_float(self._get_field(
            header, ["net_total", 11, 7], default=(total_amount + vat_amount)))
        balance = self._safe_float(self._get_field(header, ["balance", 14, 8], default=(
            net_total - self._safe_float(self._get_field(header, ["paid_amount", 14, 9], default=0.0)))))
        paid = self._safe_float(self._get_field(
            header, ["paid_amount", 15, 9], default=0.0))
        status = self._get_field(header, ["status", 17, "status"], default="")
        last_mod = self._get_field(
            header, ["updated_at", "created_at", 12, 13], default=None)

        # format date
        dt = parse_db_date(invoice_date) if invoice_date else None
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else str(invoice_date)

        # populate labels (human friendly)
        self.h_invoice_no.setText(str(invoice_no))
        self.h_date.setText(date_str)
        self.h_customer.setText(str(bill_to or ""))
        self.h_shipto.setText(str(ship_to or ""))
        self.h_salesman.setText(str(sales_person or ""))
        self.h_total.setText(f"{float(total_amount or 0):.2f}")
        self.h_paid.setText(f"{float(paid or 0):.2f}")
        self.h_balance.setText(f"{float(balance or 0):.2f}")
        self.h_status.setText(str(status or ""))
        if last_mod:
            udt = parse_db_date(last_mod)
            self.h_last_modified.setText(udt.strftime(
                "%Y-%m-%d %H:%M") if udt else str(last_mod))
        else:
            self.h_last_modified.setText("-")

    def show_invoice_items(self, items):
        """
        Display invoice_item rows in the right-hand items table.
        Accepts `items` as a list of tuples (rows) or list of dicts.
        """
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
            if isinstance(it, dict):
                serial = it.get("serial_no") or it.get(
                    "id") or (self.items_table.rowCount() + 1)
                code = it.get("item_code") or it.get("code") or ""
                name = it.get("item_name") or it.get("name") or ""
                uom = it.get("uom") or ""
                qty = safe_float(it.get("quantity") or it.get("qty") or 0)
                rate = safe_float(
                    it.get("rate") or it.get("selling_price") or 0)
                vat_amt = safe_float(it.get("vat_amount")
                                     or it.get("vat_amt") or 0)
                net = safe_float(it.get("net_amount") or it.get(
                    "net") or (qty * rate + vat_amt))
                foc = bool(it.get("free") or it.get("foc")
                           or it.get("is_free") or False)
            else:
                row = list(it) + [None] * 16
                serial = row[2] or row[0] or (self.items_table.rowCount() + 1)
                code = row[3] or row[1] or ""
                name = row[4] or row[2] or ""
                uom = row[5] or ""
                # Try likely qty slots
                qty_candidates = [7, 6, 8, 5]
                qty = 0
                for idx in qty_candidates:
                    val = None
                    try:
                        val = row[idx]
                    except Exception:
                        val = None
                    if val is not None:
                        qty = safe_float(val)
                        break
                # rate candidates
                rate = 0.0
                for idx in (8, 6, 9):
                    val = None
                    try:
                        val = row[idx]
                    except Exception:
                        val = None
                    if val is not None:
                        rate = safe_float(val)
                        break
                vat_amt = 0.0
                for idx in (11, 10, 9):
                    try:
                        v = row[idx]
                        if v is not None:
                            vat_amt = safe_float(v)
                            break
                    except Exception:
                        continue
                net = None
                for idx in (12, 11, 10):
                    try:
                        v = row[idx]
                        if v is not None:
                            net = safe_float(v)
                            break
                    except Exception:
                        continue
                if net is None:
                    net = safe_float(qty * rate + vat_amt)
                # detect FOC heuristically (columns 13-15)
                foc = False
                for maybe in (13, 14, 15):
                    try:
                        val = row[maybe]
                    except Exception:
                        val = None
                    if val is not None:
                        if isinstance(val, bool):
                            foc = val
                            break
                        try:
                            sval = str(val).strip().lower()
                            if sval in ("1", "true", "yes", "y"):
                                foc = True
                                break
                        except Exception:
                            pass

            # Insert into table
            r = self.items_table.rowCount()
            self.items_table.insertRow(r)
            self.items_table.setItem(r, 0, QTableWidgetItem(str(serial)))
            self.items_table.setItem(r, 1, QTableWidgetItem(str(code)))
            self.items_table.setItem(r, 2, QTableWidgetItem(str(name)))
            self.items_table.setItem(r, 3, QTableWidgetItem(str(uom)))

            qty_display = f"{int(qty) if float(qty).is_integer() else qty}"
            if foc:
                qty_display = f"{qty_display} (FOC)"

            self.items_table.setItem(r, 4, QTableWidgetItem(str(qty_display)))
            self.items_table.setItem(
                r, 5, QTableWidgetItem(self.format_currency(rate)))
            self.items_table.setItem(
                r, 6, QTableWidgetItem(self.format_currency(vat_amt)))
            self.items_table.setItem(
                r, 7, QTableWidgetItem(self.format_currency(net)))

    # -------------------------
    # Actions
    # -------------------------
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

    def edit_invoice_dialog(self):
        if not self.selected_invoice_no:
            return
        header, _ = fetch_invoice(self.selected_invoice_no)
        if not header:
            QMessageBox.warning(self, "Error", "Invoice not found.")
            return

        # determine status and allow edit only if active-like
        status_val = self._get_field(header, ["status", 15, 10], default="")
        if status_val and str(status_val).strip().lower() not in ("", "active", "partial"):
            QMessageBox.warning(self, "Edit not allowed",
                                "Only active/partial invoices can be edited.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Invoice {self.selected_invoice_no}")
        layout = QFormLayout(dialog)

        # Bill To (human-friendly string)
        bill_to_val = self._get_field(header, ["bill_to", 4], default="")
        bill_to_input = QLineEdit(str(bill_to_val))
        layout.addRow("Bill To:", bill_to_input)

        # Ship To (outlet) - free-text or outlet id/code
        ship_to_val = self._get_field(header, ["ship_to", 5], default="")
        ship_to_input = QLineEdit(str(ship_to_val))
        layout.addRow("Ship To (outlet):", ship_to_input)

        # Sales Person - free-text or id
        salesman_val = self._get_field(
            header, ["salesman_name", "salesman", 16, 11], default="")
        salesman_input = QLineEdit(str(salesman_val))
        layout.addRow("Sales Person:", salesman_input)

        # Status selection
        status_combo = QComboBox()
        status_combo.addItems(["Active", "Partial", "Paid", "Cancelled"])
        try:
            cur_status = str(status_val or "Active")
            ix = status_combo.findText(cur_status, Qt.MatchFixedString)
            if ix >= 0:
                status_combo.setCurrentIndex(ix)
        except Exception:
            pass
        layout.addRow("Status:", status_combo)

        # LPO and remarks
        lpo_val = self._get_field(header, ["lpo_no", 6], default="")
        lpo_input = QLineEdit(str(lpo_val))
        remarks_val = self._get_field(header, ["remarks", 12], default="")
        remarks_input = QLineEdit(str(remarks_val))
        layout.addRow("LPO No:", lpo_input)
        layout.addRow("Remarks:", remarks_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_invoice_entry(
                    self.selected_invoice_no,
                    bill_to=bill_to_input.text().strip(),
                    ship_to=ship_to_input.text().strip(),
                    lpo_no=lpo_input.text().strip(),
                    remarks=remarks_input.text().strip(),
                    status=status_combo.currentText(),
                    salesman_id=salesman_input.text().strip()
                )
                QMessageBox.information(self, "Success", "Invoice updated.")
                self.load_invoices()
            except Exception as e:
                QMessageBox.warning(self, "Failed to update",
                                    f"Failed to update: {e}")

    def cancel_invoice_action(self):
        if not self.selected_invoice_no:
            return
        try:
            header, _ = fetch_invoice(self.selected_invoice_no)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load invoice: {e}")
            return

        inv_date = self._get_field(
            header, ["invoice_date", 2, 1], default=None)
        dt = parse_db_date(inv_date)
        if dt and (datetime.datetime.now() - dt).days > 3:
            QMessageBox.warning(self, "Cancel not allowed",
                                "Cancel allowed only within 3 days of invoice date.")
            return

        ok = QMessageBox.question(
            self, "Confirm Cancel", f"Cancel invoice {self.selected_invoice_no}? This will restore stock.")
        if ok != QMessageBox.Yes:
            return

        try:
            cancel_invoice(self.selected_invoice_no)
            QMessageBox.information(
                self, "Canceled", "Invoice canceled and stock restored.")
            self.load_invoices()
        except sqlite3.OperationalError as e:
            errmsg = str(e).lower()
            if "locked" in errmsg:
                QMessageBox.warning(
                    self, "Failed to cancel", "Database is busy/locked. Please try again in a moment and press Refresh.")
            else:
                QMessageBox.warning(self, "Failed to cancel",
                                    f"Failed to cancel invoice: {e}")
        except Exception as e:
            QMessageBox.warning(self, "Failed to cancel",
                                f"Failed to cancel invoice: {e}")

    # -------------------------
    # Export / report
    # -------------------------
    def export_invoices_excel(self):
        if not self.invoices:
            QMessageBox.information(self, "No data", "No invoices to export.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Invoices", f"invoices_{datetime.date.today().isoformat()}.xlsx", "Excel Files (*.xlsx)")
        if not filename:
            return
        try:
            wb = Workbook()
            ws = wb.active
            headers = ["Invoice No", "Date", "Customer", "Bill To",
                       "Ship To", "Total", "VAT", "Net", "Paid", "Balance", "Status"]
            ws.append(headers)
            for r in self.invoices:
                rowdata = r
                invoice_no = self._get_field(
                    rowdata, ["invoice_no", "id", 0, 1], default="")
                date = self._get_field(
                    rowdata, ["invoice_date", 1, 2], default="")
                customer = self._get_field(
                    rowdata, ["customer_name", "bill_to", 3, 2], default="")
                bill_to = self._get_field(rowdata, ["bill_to", 4], default="")
                ship_to = self._get_field(rowdata, ["ship_to", 5], default="")
                total = self._safe_float(self._get_field(
                    rowdata, ["total_amount", 5], default=0.0))
                vat = self._safe_float(self._get_field(
                    rowdata, ["vat_amount", 6], default=0.0))
                net = self._safe_float(self._get_field(
                    rowdata, ["net_total", 7], default=(total + vat)))
                paid = self._safe_float(self._get_field(
                    rowdata, ["paid_amount", 9], default=0.0))
                balance = self._safe_float(self._get_field(
                    rowdata, ["balance", 8], default=(net - paid)))
                status = self._get_field(rowdata, ["status", 10], default="")
                ws.append([invoice_no, date, customer, bill_to,
                          ship_to, total, vat, net, paid, balance, status])
            wb.save(filename)
            QMessageBox.information(
                self, "Exported", f"Exported to {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed",
                                f"Failed to export: {e}")

    def generate_report_excel(self):
        start = self.range_start.date().toPyDate()
        end = self.range_end.date().toPyDate()
        self.current_start = start
        self.current_end = end

        # filter invoices by date
        filtered = []
        for r in self.invoices:
            try:
                inv_date = parse_db_date(self._get_field(
                    r, ["invoice_date", 1, 2], default=""))
                if inv_date:
                    inv_date_only = inv_date.date()
                    if start <= inv_date_only <= end:
                        filtered.append(r)
            except Exception:
                continue

        if not filtered:
            QMessageBox.information(
                self, "No Data", "No invoices in selected range.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Sales Report", f"sales_report_{start}_{end}.xlsx", "Excel Files (*.xlsx)")
        if not filename:
            return
        try:
            wb = Workbook()
            ws = wb.active
            ws.append(["Sales Report"])
            ws.append([f"From: {start} To: {end}"])
            ws.append([])
            ws.append(["Invoice No", "Date", "Customer", "Total (Net)"])
            total_sales = 0.0
            for r in filtered:
                net = self._safe_float(self._get_field(
                    r, ["net_total", 7], default=0.0))
                ws.append([self._get_field(r, ["invoice_no", "id", 0, 1], default=""), self._get_field(
                    r, ["invoice_date", 1, 2], default=""), self._get_field(r, ["customer_name", "bill_to", 3, 2], default=""), net])
                total_sales += net
            try:
                summary = get_sales_summary_range(
                    start.isoformat(), end.isoformat())
                ws.append([])
                ws.append(["Summary"])
                ws.append(["Total Sales", summary.get("total_sales", 0.0)])
                ws.append(
                    ["Total Purchase", summary.get("total_purchase", 0.0)])
            except Exception:
                pass
            wb.save(filename)
            QMessageBox.information(
                self, "Report", f"Saved report: {filename}\nTotal Sales: {total_sales:.2f}")
        except Exception as e:
            QMessageBox.warning(
                self, "Failed", f"Failed to generate report: {e}")

    # -------------------------
    # UI helpers
    # -------------------------
    def on_preset_changed(self, idx):
        today = datetime.date.today()
        if idx == 0:
            return
        if idx == 1:  # Today
            start = end = today
        elif idx == 2:  # This Week
            start = today - datetime.timedelta(days=today.weekday())
            end = start + datetime.timedelta(days=6)
        elif idx == 3:  # This Month
            start = today.replace(day=1)
            end = today
        elif idx == 4:  # This Quarter
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
        else:  # This Year
            start = today.replace(month=1, day=1)
            end = today
        self.range_start.setDate(QDate(start.year, start.month, start.day))
        self.range_end.setDate(QDate(end.year, end.month, end.day))

    def on_load_clicked(self):
        self.load_invoices()
