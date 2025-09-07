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

# Models (these must exist in your models.invoice_model)
from models.invoice_model import (
    get_all_invoices,
    fetch_invoice,
    update_invoice_entry,
    cancel_invoice,
    get_sales_summary_range
)

# PDF helper (generate and open). This file should implement generate_invoice_pdf(invoice_no, open_after=False)
# We call it inside a try/except so missing helper won't crash the UI.
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

    def format_currency(self, val) -> str:
        try:
            return f"{float(val or 0):.2f}"
        except Exception:
            try:
                cleaned = "".join(ch for ch in str(
                    val) if (ch.isdigit() or ch in ".-"))
                return f"{float(cleaned or 0):.2f}"
            except Exception:
                return "0.00"

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

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setToolTip("Reload latest invoices from database")
        refresh_btn.clicked.connect(
            self.on_load_clicked)   # same behaviour as Load
        toolbar.addWidget(refresh_btn)

        export_btn = QPushButton("📥 Export Invoices (Excel)")
        export_btn.clicked.connect(self.export_invoices_excel)
        toolbar.addWidget(export_btn)

        root.addLayout(toolbar)

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
            "Search invoice no / customer / salesman / status")
        self.search_input.textChanged.connect(self.filter_invoices)
        search_row.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Date Desc", "Date Asc", "Customer", "Salesman", "Pending Amount"])
        self.sort_combo.currentIndexChanged.connect(self.apply_sort)
        search_row.addWidget(self.sort_combo)
        left_layout.addLayout(search_row)

        # NOTE: columns = 11 -> Invoice No, Date, Customer, Bill To, Ship To, Total, VAT, Net, Paid, Balance, Status
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(11)
        self.invoice_table.setHorizontalHeaderLabels([
            "Invoice No", "Date", "Customer", "Bill To", "Ship To",
            "Total (₹)", "VAT (₹)", "Net (₹)", "Paid (₹)", "Balance (₹)", "Status"
        ])
        self.invoice_table.setSelectionBehavior(self.invoice_table.SelectRows)
        self.invoice_table.setEditTriggers(self.invoice_table.NoEditTriggers)
        self.invoice_table.itemSelectionChanged.connect(
            self.on_invoice_selected)
        left_layout.addWidget(self.invoice_table)

        totals_row = QHBoxLayout()
        self.total_sales_lbl = QLabel("Total Sales: ₹0.00")
        self.total_purchase_lbl = QLabel("Total Purchase: ₹0.00")
        totals_row.addWidget(self.total_sales_lbl)
        totals_row.addSpacing(16)
        totals_row.addWidget(self.total_purchase_lbl)
        totals_row.addStretch()
        left_layout.addLayout(totals_row)

        splitter.addWidget(left)

        # Right
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
        self.h_salesman = QLabel("-")
        self.h_total = QLabel("-")
        self.h_paid = QLabel("-")
        self.h_balance = QLabel("-")
        self.h_status = QLabel("-")

        self.header_grid.addWidget(QLabel("Invoice No:"), 0, 0)
        self.header_grid.addWidget(self.h_invoice_no, 0, 1)
        self.header_grid.addWidget(QLabel("Date:"), 0, 2)
        self.header_grid.addWidget(self.h_date, 0, 3)

        self.header_grid.addWidget(QLabel("Customer:"), 1, 0)
        self.header_grid.addWidget(self.h_customer, 1, 1)
        self.header_grid.addWidget(QLabel("Salesman:"), 1, 2)
        self.header_grid.addWidget(self.h_salesman, 1, 3)

        self.header_grid.addWidget(QLabel("Total:"), 2, 0)
        self.header_grid.addWidget(self.h_total, 2, 1)
        self.header_grid.addWidget(QLabel("Paid:"), 2, 2)
        self.header_grid.addWidget(self.h_paid, 2, 3)

        self.header_grid.addWidget(QLabel("Balance:"), 3, 0)
        self.header_grid.addWidget(self.h_balance, 3, 1)
        self.header_grid.addWidget(QLabel("Status:"), 3, 2)
        self.header_grid.addWidget(self.h_status, 3, 3)

        right_layout.addLayout(self.header_grid)

        # items table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(8)
        self.items_table.setHorizontalHeaderLabels([
            "S.No", "Item Code", "Item Name", "UOM", "Qty", "Rate (₹)", "VAT (₹)", "Line Total (₹)"
        ])
        self.items_table.setEditTriggers(self.items_table.NoEditTriggers)
        right_layout.addWidget(self.items_table)

        # actions
        actions_row = QHBoxLayout()
        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self.edit_invoice_dialog)
        self.edit_btn.setEnabled(False)
        actions_row.addWidget(self.edit_btn)

        self.record_payment_btn = QPushButton("💰 Record Payment")
        self.record_payment_btn.clicked.connect(self.record_payment_dialog)
        self.record_payment_btn.setEnabled(False)
        actions_row.addWidget(self.record_payment_btn)

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
        # remember current range
        try:
            if start_date is None:
                start_date = self.range_start.date().toPyDate()
            if end_date is None:
                end_date = self.range_end.date().toPyDate()
            self.current_start = start_date
            self.current_end = end_date

            # try to call model with range parameters if supported
            try:
                rows = get_all_invoices(start_date=start_date.isoformat(
                ), end_date=end_date.isoformat(), **filters)
            except TypeError:
                # fallback if model does not accept keywords
                rows = get_all_invoices()
            self.invoices = rows or []
            self.populate_invoice_table(self.invoices)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load invoices: {e}")
            self.invoices = []
            self.populate_invoice_table([])

    def populate_invoice_table(self, invoices):
        self.invoice_table.setRowCount(0)
        total_sales = 0.0

        for r in invoices:
            if r is None:
                continue
            # pad to at least 12 cols for safe indexing
            rowdata = list(r) + [None] * max(0, 12 - len(r))

            invoice_no = rowdata[0]
            invoice_date = rowdata[1]
            customer = rowdata[2] or ""
            bill_to = rowdata[3] or ""
            ship_to = rowdata[4] or ""
            total_amount = float(rowdata[5]) if rowdata[5] not in (
                None, "") else 0.0
            vat_amount = float(rowdata[6]) if rowdata[6] not in (
                None, "") else 0.0
            net_total = float(rowdata[7]) if rowdata[7] not in (
                None, "") else 0.0
            paid_amount = float(rowdata[9]) if rowdata[9] not in (
                None, "") else 0.0
            balance = float(rowdata[8]) if rowdata[8] not in (
                None, "") else (net_total - paid_amount)
            status = rowdata[10] or ""

            row_pos = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row_pos)
            self.invoice_table.setItem(
                row_pos, 0, QTableWidgetItem(str(invoice_no)))
            self.invoice_table.setItem(
                row_pos, 1, QTableWidgetItem(str(invoice_date)))
            self.invoice_table.setItem(
                row_pos, 2, QTableWidgetItem(str(customer)))
            self.invoice_table.setItem(
                row_pos, 3, QTableWidgetItem(str(bill_to)))
            self.invoice_table.setItem(
                row_pos, 4, QTableWidgetItem(str(ship_to)))
            self.invoice_table.setItem(row_pos, 5, QTableWidgetItem(
                self.format_currency(total_amount)))
            self.invoice_table.setItem(row_pos, 6, QTableWidgetItem(
                self.format_currency(vat_amount)))
            self.invoice_table.setItem(
                row_pos, 7, QTableWidgetItem(self.format_currency(net_total)))
            self.invoice_table.setItem(row_pos, 8, QTableWidgetItem(
                self.format_currency(paid_amount)))
            self.invoice_table.setItem(
                row_pos, 9, QTableWidgetItem(self.format_currency(balance)))
            self.invoice_table.setItem(
                row_pos, 10, QTableWidgetItem(str(status)))

            total_sales += net_total

        self.total_sales_lbl.setText(f"Total Sales: ₹{total_sales:.2f}")

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
            rows.sort(key=lambda r: parse_db_date(
                r[1]) or datetime.datetime.min, reverse=True)
        elif idx == 1:
            rows.sort(key=lambda r: parse_db_date(
                r[1]) or datetime.datetime.min)
        elif idx == 2:
            rows.sort(key=lambda r: str(r[2] or "").lower())
        elif idx == 3:
            rows.sort(key=lambda r: str(r[11] or "").lower())
        elif idx == 4:
            rows.sort(key=lambda r: float(r[8] or 0.0), reverse=True)
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

        self.show_invoice_header(header)
        self.show_invoice_items(items)

        # decide button enabling
        inv_date = header[2] if len(header) > 2 else header[1]
        dt = parse_db_date(inv_date)
        allow_edit = False
        allow_cancel = False
        if dt:
            age_days = (datetime.datetime.now() - dt).days
            if age_days <= 3:
                allow_edit = allow_cancel = True

        status = header[15] if len(header) > 15 else (
            header[14] if len(header) > 14 else "")
        self.edit_btn.setEnabled(bool(allow_edit))
        self.cancel_btn.setEnabled(bool(allow_cancel) and (
            str(status).lower() not in ("canceled", "cancelled", "voided")))
        self.record_payment_btn.setEnabled(True)
        self.view_pdf_btn.setEnabled(True)

    def show_invoice_header(self, header):
        inv_no = header[1] if len(header) > 1 else header[0]
        inv_date = header[2] if len(header) > 2 else ""
        bill_to = header[4] if len(header) > 4 else ""
        salesman = header[16] if len(header) > 16 else ""
        total = header[8] if len(header) > 8 else 0.0
        vat = header[9] if len(header) > 9 else 0.0
        net = header[10] if len(header) > 10 else (total + vat)
        balance = header[13] if len(header) > 13 else 0.0
        paid = header[14] if len(header) > 14 else 0.0
        status = header[15] if len(header) > 15 else ""

        dt = parse_db_date(inv_date)
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else str(inv_date)
        self.h_invoice_no.setText(str(inv_no))
        self.h_date.setText(date_str)
        self.h_customer.setText(str(bill_to))
        self.h_salesman.setText(str(salesman or ""))
        self.h_total.setText(f"₹{(float(total or 0)): .2f}")
        self.h_paid.setText(f"₹{(float(paid or 0)): .2f}")
        self.h_balance.setText(f"₹{(float(balance or 0)): .2f}")
        self.h_status.setText(str(status or ""))

    def show_invoice_items(self, items):
        self.items_table.setRowCount(0)
        for it in items:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            serial = it[0] if len(it) > 0 else row + 1
            code = it[1] if len(it) > 1 else ""
            name = it[2] if len(it) > 2 else ""
            uom = it[3] if len(it) > 3 else ""
            qty = it[5] if len(it) > 5 else 0
            rate = it[6] if len(it) > 6 else 0
            vat_amt = it[9] if len(it) > 9 else 0
            net = it[10] if len(it) > 10 else (
                float(qty or 0) * float(rate or 0) + float(vat_amt or 0))

            self.items_table.setItem(row, 0, QTableWidgetItem(str(serial)))
            self.items_table.setItem(row, 1, QTableWidgetItem(str(code)))
            self.items_table.setItem(row, 2, QTableWidgetItem(str(name)))
            self.items_table.setItem(row, 3, QTableWidgetItem(str(uom)))
            self.items_table.setItem(row, 4, QTableWidgetItem(str(qty)))
            self.items_table.setItem(
                row, 5, QTableWidgetItem(self.format_currency(rate)))
            self.items_table.setItem(
                row, 6, QTableWidgetItem(self.format_currency(vat_amt)))
            self.items_table.setItem(
                row, 7, QTableWidgetItem(self.format_currency(net)))

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
        inv_date = header[2] if len(header) > 2 else ""
        dt = parse_db_date(inv_date)
        if dt and (datetime.datetime.now() - dt).days > 3:
            QMessageBox.warning(
                self, "Edit not allowed", "Editing allowed only within 3 days of invoice date.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Invoice {self.selected_invoice_no}")
        layout = QFormLayout(dialog)
        bill_to = QLineEdit(str(header[4] if len(header) > 4 else ""))
        ship_to = QLineEdit(str(header[5] if len(header) > 5 else ""))
        lpo_input = QLineEdit(str(header[6] if len(header) > 6 else ""))
        remarks_input = QLineEdit(str(header[12] if len(header) > 12 else ""))

        layout.addRow("Bill To:", bill_to)
        layout.addRow("Ship To:", ship_to)
        layout.addRow("LPO No:", lpo_input)
        layout.addRow("Remarks:", remarks_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_invoice_entry(self.selected_invoice_no,
                                     bill_to=bill_to.text().strip(),
                                     ship_to=ship_to.text().strip(),
                                     lpo_no=lpo_input.text().strip(),
                                     remarks=remarks_input.text().strip())
                QMessageBox.information(self, "Success", "Invoice updated.")
                self.load_invoices()
            except Exception as e:
                QMessageBox.warning(self, "Failed to update",
                                    f"Failed to update: {e}")

    def record_payment_dialog(self):
        if not self.selected_invoice_no:
            return
        header, _ = fetch_invoice(self.selected_invoice_no)
        balance = float(header[13] if len(header) > 13 else 0.0)
        paid = float(header[14] if len(header) > 14 else 0.0)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Record Payment - {self.selected_invoice_no}")
        form = QFormLayout(dialog)
        paid_input = QLineEdit()
        paid_input.setPlaceholderText("Amount paid now")
        paid_input.setText("0.00")
        form.addRow("Amount:", paid_input)

        method = QComboBox()
        method.addItems(["Cash", "Card", "Bank Transfer", "Cheque", "Other"])
        form.addRow("Method:", method)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                amt = float(paid_input.text().strip() or 0.0)
                new_paid = paid + amt
                new_balance = max(0.0, balance - amt)
                status = "Paid" if new_balance <= 0 else (
                    "Partial" if new_paid > 0 else "Unpaid")
                update_invoice_entry(
                    self.selected_invoice_no, paid_amount=new_paid, balance=new_balance, status=status)
                QMessageBox.information(self, "Success", "Payment recorded.")
                self.load_invoices()
            except Exception as e:
                QMessageBox.warning(
                    self, "Failed", f"Failed to record payment: {e}")

    def cancel_invoice_action(self):
        if not self.selected_invoice_no:
            return
        # confirm date rule
        try:
            header, _ = fetch_invoice(self.selected_invoice_no)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load invoice: {e}")
            return

        inv_date = header[2] if len(header) > 2 else ""
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
            # attempt cancel
            cancel_invoice(self.selected_invoice_no)
            QMessageBox.information(
                self, "Canceled", "Invoice canceled and stock restored.")
            # reload latest
            self.load_invoices()
        except sqlite3.OperationalError as e:
            errmsg = str(e).lower()
            if "locked" in errmsg:
                QMessageBox.warning(
                    self, "Failed to cancel",
                    "Database is busy/locked. Please try again in a moment (close other apps that may use the DB) and press Refresh.")
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
                rowdata = list(r) + [None] * max(0, 11 - len(r))
                ws.append([
                    rowdata[0], rowdata[1], rowdata[2], rowdata[3], rowdata[4],
                    rowdata[5], rowdata[6], rowdata[7], rowdata[9], rowdata[8], rowdata[10]
                ])
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
            inv_date = None
            try:
                inv_date = parse_db_date(r[1]).date()
            except Exception:
                pass
            if inv_date and start <= inv_date <= end:
                filtered.append(r)

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
                net = float(r[7]) if len(
                    r) > 7 and r[7] not in (None, "") else 0.0
                ws.append([r[0], r[1], r[2], net])
                total_sales += net
            # try to append model summary
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
                self, "Report", f"Saved report: {filename}\nTotal Sales: ₹{total_sales:.2f}")
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
            # compute last day of end_month
            next_month = end_month % 12 + 1
            year = start.year + (1 if end_month > 12 else 0)
            last_day = (datetime.date(year, next_month, 1) -
                        datetime.timedelta(days=1)).day
            end = today.replace(
                month=end_month if end_month <= 12 else 12, day=last_day)
        else:  # This Year
            start = today.replace(month=1, day=1)
            end = today
        self.range_start.setDate(QDate(start.year, start.month, start.day))
        self.range_end.setDate(QDate(end.year, end.month, end.day))

    def on_load_clicked(self):
        self.load_invoices()
