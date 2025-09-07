# ui/admin_stock_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFormLayout, QDialogButtonBox, QMessageBox,
    QSplitter, QSizePolicy, QInputDialog, QDateEdit
)
from PyQt5.QtGui import QIcon, QColor, QBrush
from PyQt5.QtCore import Qt, QDate
from models.stock_model import (
    get_consolidated_stock, get_all_batches, update_item, add_stock, add_item,
    reduce_stock_quantity, init_db, get_item_by_item_code
)
from openpyxl import Workbook
import sqlite3
import datetime


def _parse_date_to_dateobj(s):
    """
    Try common date formats -> return a datetime.date object or None.
    Accepts: 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS', ISO variants, 'DD-MMM-YYYY', etc.
    If s is already a date/datetime, returns a date object.
    """
    if not s:
        return None

    # If already a date / datetime, return a date
    if isinstance(s, (datetime.date, datetime.datetime)):
        return s.date() if isinstance(s, datetime.datetime) else s

    s = str(s).strip()

    # Common formats to try (add any other patterns your DB uses)
    fmts = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d-%b-%Y",
        "%d-%b-%Y %I:%M %p",
    )
    for f in fmts:
        try:
            return datetime.datetime.strptime(s, f).date()
        except Exception:
            pass

    # final fallback: try date.fromisoformat()
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return None


def _format_display_date_for_table(dt):
    """
    Return user-friendly display for an expiry (date only).
    Accepts a date/datetime or a parseable string.
    Returns '' when no valid date.
    """
    if not dt:
        return ""

    if isinstance(dt, str):
        dt = _parse_date_to_dateobj(dt)
    if not dt:
        return ""

    # e.g. '05-Aug-2025'
    return dt.strftime("%d-%b-%Y")


def _format_created_at_display(s):
    """
    Format created_at (which may include time) as 'DD-MMM-YYYY hh:mm AM/PM'.
    Accepts:
      - a datetime or date object
      - various strings (ISO, 'YYYY-MM-DD HH:MM:SS', with optional fractional seconds or timezone)
    Returns the original input as string when parsing fails.
    """
    if not s:
        return ""

    # If already a datetime
    if isinstance(s, datetime.datetime):
        return s.strftime("%d-%b-%Y %I:%M %p")
    # If it's a date (no time), combine with midnight
    if isinstance(s, datetime.date):
        dt = datetime.datetime.combine(s, datetime.time.min)
        return dt.strftime("%d-%b-%Y %I:%M %p")

    s = str(s).strip()

    # Try several datetime formats (including timezone-aware)
    fmts = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y",
    )
    for f in fmts:
        try:
            dt = datetime.datetime.strptime(s, f)
            return dt.strftime("%d-%b-%Y %I:%M %p")
        except Exception:
            pass

    # As a last attempt, if the string looks like an ISO date, try fromisoformat()
    try:
        dt = datetime.datetime.fromisoformat(s)
        return dt.strftime("%d-%b-%Y %I:%M %p")
    except Exception:
        pass

    # give up and return original
    return s


class AdminStockWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📦 Admin Stock Management")
        self.setGeometry(200, 100, 1200, 700)
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))

        # Ensure DB initialized (safe)
        try:
            init_db()
        except Exception:
            pass

        self.showing_low_stock_only = False
        self.consolidated = []  # cached master rows
        self.batches = []  # cached current item's batches

        self.setup_ui()
        self.load_master_table()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Compact Title + toolbar row
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        title_label = QLabel("📦 Admin Stock Management")
        title_label.setStyleSheet(
            "font-size: 15px; font-weight: 700; margin: 2px 0;")
        title_label.setMaximumHeight(28)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_row.addWidget(title_label)

        # toolbar (compact) - Add Item + Edit Master + Edit Batch + Export + Low stock toggle
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search Item code or name...")
        self.search_input.textChanged.connect(self.filter_master_table)
        self.search_input.setFixedWidth(320)

        self.add_item_btn = QPushButton("➕ Add Item")
        self.add_item_btn.setFixedHeight(28)
        self.add_item_btn.clicked.connect(self.add_item_dialog)

        self.edit_master_btn = QPushButton("✏️ Edit Master")
        self.edit_master_btn.setFixedHeight(28)
        self.edit_master_btn.clicked.connect(self.edit_master_data)

        self.edit_batch_btn = QPushButton("✏️ Edit Batch")
        self.edit_batch_btn.setFixedHeight(28)
        self.edit_batch_btn.clicked.connect(self.edit_batch_data)

        self.export_master_btn = QPushButton("📥 Export Master")
        self.export_master_btn.setFixedHeight(28)
        self.export_master_btn.clicked.connect(self.export_master_to_excel)

        self.export_batch_btn = QPushButton("📥 Export Batches")
        self.export_batch_btn.setFixedHeight(28)
        self.export_batch_btn.clicked.connect(self.export_batches_to_excel)

        self.low_stock_btn = QPushButton("📉 Toggle Low Stock")
        self.low_stock_btn.setFixedHeight(28)
        self.low_stock_btn.clicked.connect(self.toggle_low_stock_view)

        # New: Refresh All (refresh master and batches)
        self.refresh_all_btn = QPushButton("🔄 Refresh All")
        self.refresh_all_btn.setFixedHeight(28)
        self.refresh_all_btn.clicked.connect(self.refresh_all)

        # pack toolbar items on the right
        top_row.addWidget(self.search_input, 0, Qt.AlignRight)
        top_row.addWidget(self.add_item_btn)
        top_row.addWidget(self.edit_master_btn)
        top_row.addWidget(self.edit_batch_btn)
        top_row.addWidget(self.export_master_btn)
        top_row.addWidget(self.export_batch_btn)
        top_row.addWidget(self.low_stock_btn)
        top_row.addWidget(self.refresh_all_btn)

        layout.addLayout(top_row)

        # Splitter: left = master table, right = batches + info
        splitter = QSplitter(Qt.Horizontal)

        # Master table (left)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.master_table = QTableWidget()
        # columns: Item Code, Name, Unit, Sell Price, Available Qty, Low Level, Status
        self.master_table.setColumnCount(7)
        self.master_table.setHorizontalHeaderLabels([
            "Item Code", "Item Name", "Unit", "Sell Price", "Available Qty", "Low Level", "Status"
        ])
        self.master_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.master_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.master_table.cellClicked.connect(self.on_master_selected)
        self.master_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        left_layout.addWidget(self.master_table)
        splitter.addWidget(left_widget)

        # Right side: batches table + quick info
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        info_label = QLabel("Batches for selected item")
        info_label.setStyleSheet("font-weight:600;")
        right_layout.addWidget(info_label)

        self.batch_table = QTableWidget()
        # columns: ID, Batch No, Purchase Price, Qty, Expiry Date, Type, Created At
        self.batch_table.setColumnCount(7)
        self.batch_table.setHorizontalHeaderLabels([
            "ID", "Batch No", "Purchase Price", "Qty", "Expiry Date", "Type", "Created At"
        ])
        # hide internal ID but keep it for edits
        self.batch_table.hideColumn(0)
        self.batch_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.batch_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.batch_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_layout.addWidget(self.batch_table)

        # Quick actions under batch table
        batch_actions = QHBoxLayout()
        self.reduce_qty_btn = QPushButton("➖ Reduce Qty (simulate billing)")
        self.reduce_qty_btn.clicked.connect(self.reduce_qty_for_selected_batch)
        self.refresh_batches_btn = QPushButton("🔄 Refresh Batches")
        self.refresh_batches_btn.clicked.connect(self.refresh_batches)

        batch_actions.addWidget(self.reduce_qty_btn)
        batch_actions.addWidget(self.refresh_batches_btn)
        batch_actions.addStretch()
        right_layout.addLayout(batch_actions)

        splitter.addWidget(right_widget)

        # default stretch
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.setLayout(layout)

    # -------------------------
    # Loading / display helpers
    # -------------------------
    def load_master_table(self):
        """
        Load consolidated stock (master) and populate left table.
        Uses get_consolidated_stock() which returns rows:
        (item_code, name, total_qty, uom, selling_price, low_stock_level, is_below)
        """
        try:
            self.master_table.setRowCount(0)
            self.consolidated = get_consolidated_stock()
            for row in self.consolidated:
                item_code, name, total_qty, uom, selling_price, low_level, is_below = row

                # If we're in low-stock-only mode skip others
                if self.showing_low_stock_only and not is_below:
                    continue

                r = self.master_table.rowCount()
                self.master_table.insertRow(r)
                self.master_table.setItem(
                    r, 0, QTableWidgetItem(str(item_code)))
                self.master_table.setItem(r, 1, QTableWidgetItem(str(name)))
                self.master_table.setItem(r, 2, QTableWidgetItem(str(uom)))
                self.master_table.setItem(r, 3, QTableWidgetItem(
                    f"{float(selling_price):.2f}" if selling_price is not None else "0.00"))
                self.master_table.setItem(
                    r, 4, QTableWidgetItem(f"{float(total_qty):.2f}"))
                self.master_table.setItem(
                    r, 5, QTableWidgetItem(str(low_level)))
                status_item = QTableWidgetItem("LOW" if is_below else "OK")
                self.master_table.setItem(r, 6, status_item)

                # highlight entire row if low
                if is_below:
                    for c in range(self.master_table.columnCount()):
                        cell = self.master_table.item(r, c)
                        if cell:
                            cell.setBackground(QBrush(QColor(255, 200, 200)))

            # select first row by default and load its batches
            if self.master_table.rowCount() > 0:
                self.master_table.selectRow(0)
                first_code = self.master_table.item(0, 0).text()
                self.load_batches_for_item(first_code)
            else:
                self.batch_table.setRowCount(0)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to load master stock: {e}")

    def filter_master_table(self):
        text = self.search_input.text().strip().lower()
        # naive filtering over self.consolidated
        self.master_table.setRowCount(0)
        for row in self.consolidated:
            item_code, name, total_qty, uom, selling_price, low_level, is_below = row
            if text == "" or text in str(item_code).lower() or text in str(name).lower():
                # skip if low-only mode and not low
                if self.showing_low_stock_only and not is_below:
                    continue
                r = self.master_table.rowCount()
                self.master_table.insertRow(r)
                self.master_table.setItem(
                    r, 0, QTableWidgetItem(str(item_code)))
                self.master_table.setItem(r, 1, QTableWidgetItem(str(name)))
                self.master_table.setItem(r, 2, QTableWidgetItem(str(uom)))
                self.master_table.setItem(r, 3, QTableWidgetItem(
                    f"{float(selling_price):.2f}" if selling_price is not None else "0.00"))
                self.master_table.setItem(
                    r, 4, QTableWidgetItem(f"{float(total_qty):.2f}"))
                self.master_table.setItem(
                    r, 5, QTableWidgetItem(str(low_level)))
                status_item = QTableWidgetItem("LOW" if is_below else "OK")
                self.master_table.setItem(r, 6, status_item)
                if is_below:
                    for c in range(self.master_table.columnCount()):
                        cell = self.master_table.item(r, c)
                        if cell:
                            cell.setBackground(QBrush(QColor(255, 200, 200)))

    def on_master_selected(self, row, col):
        item_code_item = self.master_table.item(row, 0)
        if not item_code_item:
            return
        item_code = item_code_item.text()
        self.load_batches_for_item(item_code)

    def load_batches_for_item(self, item_code):
        try:
            self.batch_table.setRowCount(0)
            self.batches = get_all_batches(item_code)
            for b in self.batches:
                # Expected b: (id, batch_no, purchase_price, quantity, expiry_date, stock_type, created_at, updated_at)
                b_id = b[0]
                batch_no = b[1]
                purchase_price = b[2]
                qty = b[3]
                expiry_raw = b[4] or ""
                stype = b[5]
                created_raw = b[6] or ""

                expiry_display = _format_display_date_for_table(expiry_raw)
                created_display = _format_created_at_display(created_raw)

                r = self.batch_table.rowCount()
                self.batch_table.insertRow(r)
                self.batch_table.setItem(r, 0, QTableWidgetItem(str(b_id)))
                self.batch_table.setItem(r, 1, QTableWidgetItem(str(batch_no)))
                self.batch_table.setItem(r, 2, QTableWidgetItem(
                    f"{float(purchase_price):.2f}" if purchase_price is not None else "0.00"))
                qty_item = QTableWidgetItem(f"{float(qty):.2f}")
                if float(qty) <= 0:
                    qty_item.setBackground(QBrush(QColor(255, 180, 180)))
                self.batch_table.setItem(r, 3, qty_item)
                # show formatted expiry
                self.batch_table.setItem(
                    r, 4, QTableWidgetItem(expiry_display))
                self.batch_table.setItem(r, 5, QTableWidgetItem(str(stype)))
                # show nicely formatted created datetime
                self.batch_table.setItem(
                    r, 6, QTableWidgetItem(created_display))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load batches: {e}")

    def refresh_batches(self):
        cur = self.master_table.currentRow()
        if cur < 0:
            return
        item_code = self.master_table.item(cur, 0).text()
        self.load_batches_for_item(item_code)

    def refresh_all(self):
        """Refresh both master and currently visible batches."""
        self.load_master_table()
        # refresh batches for currently selected master row
        cur = self.master_table.currentRow()
        if cur >= 0:
            self.load_batches_for_item(
                self.master_table.item(cur, 0).text())

    # -------------------------
    # Actions: Add / Edit master/batch
    # -------------------------
    def add_item_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("➕ Add New Item Master")
        form = QFormLayout(dialog)

        item_code_input = QLineEdit()
        name_input = QLineEdit()
        uom_input = QLineEdit("pcs")
        per_box_input = QLineEdit("1")
        vat_input = QLineEdit("5")
        sell_input = QLineEdit("0.00")
        low_input = QLineEdit("0")
        remarks_input = QLineEdit("")

        form.addRow("Item Code:", item_code_input)
        form.addRow("Name:", name_input)
        form.addRow("UOM (e.g. pcs, kg):", uom_input)
        form.addRow("Per Box Qty:", per_box_input)
        form.addRow("VAT %:", vat_input)
        form.addRow("Selling Price:", sell_input)
        # HSN removed per request
        form.addRow("Low Stock Level:", low_input)
        form.addRow("Remarks:", remarks_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            code = item_code_input.text().strip().upper()
            name = name_input.text().strip()
            uom = uom_input.text().strip()
            try:
                per_box = int(per_box_input.text().strip() or 1)
            except Exception:
                per_box = 1
            try:
                vat = float(vat_input.text().strip() or 0)
            except Exception:
                vat = 0.0
            try:
                sell = float(sell_input.text().strip() or 0)
            except Exception:
                sell = 0.0
            try:
                lowlvl = int(low_input.text().strip() or 0)
            except Exception:
                lowlvl = 0
            remarks = remarks_input.text().strip()

            if not code or not name:
                QMessageBox.warning(self, "Validation",
                                    "Item Code and Name are required.")
                return

            try:
                item_id = add_item(item_code=code, name=name, uom=uom, per_box_qty=per_box,
                                   vat_percentage=vat, selling_price=sell, remarks=remarks, low_stock_level=lowlvl)
                QMessageBox.information(
                    self, "Added", f"✅ Item {code} added (id={item_id}).")
                self.load_master_table()
                # try select newly added item
                for r in range(self.master_table.rowCount()):
                    if self.master_table.item(r, 0).text() == code:
                        self.master_table.selectRow(r)
                        self.load_batches_for_item(code)
                        break
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to add item: {e}")

    def edit_master_data(self):
        row = self.master_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Item",
                                "⚠️ Please select an item to edit.")
            return
        item_code = self.master_table.item(row, 0).text()

        # fetch full item from model to get all editable columns
        try:
            item = get_item_by_item_code(item_code)
            # expected dict or tuple; we'll support both
            if isinstance(item, dict):
                item_obj = item
            else:
                # assume tuple: (id, item_code, name, uom, per_box_qty, vat_percentage, selling_price, remarks, low_stock_level, ...)
                item_obj = {
                    "item_code": item[1],
                    "name": item[2] if len(item) > 2 else "",
                    "uom": item[3] if len(item) > 3 else "",
                    "per_box_qty": item[4] if len(item) > 4 else 1,
                    "vat_percentage": item[5] if len(item) > 5 else 0,
                    "selling_price": item[6] if len(item) > 6 else 0,
                    "remarks": item[7] if len(item) > 7 else "",
                    "low_stock_level": item[8] if len(item) > 8 else 0
                }
        except Exception:
            # fallback: use limited data from table
            item_obj = {
                "item_code": item_code,
                "name": self.master_table.item(row, 1).text(),
                "uom": self.master_table.item(row, 2).text(),
                "selling_price": float(self.master_table.item(row, 3).text()),
                "low_stock_level": int(self.master_table.item(row, 5).text()),
                "per_box_qty": 1,
                "vat_percentage": 0,
                "remarks": ""
            }

        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Master Data")
        form = QFormLayout(dialog)

        # show item code but make it read-only
        code_input = QLineEdit(item_obj.get("item_code", ""))
        code_input.setReadOnly(True)
        name_input = QLineEdit(item_obj.get("name", ""))
        uom_input = QLineEdit(item_obj.get("uom", ""))
        per_box_input = QLineEdit(str(item_obj.get("per_box_qty", 1)))
        vat_input = QLineEdit(str(item_obj.get("vat_percentage", 0)))
        sell_input = QLineEdit(str(item_obj.get("selling_price", 0)))
        low_input = QLineEdit(str(item_obj.get("low_stock_level", 0)))
        remarks_input = QLineEdit(str(item_obj.get("remarks", "")))

        form.addRow("Item Code (read-only):", code_input)
        form.addRow("Item Name:", name_input)
        form.addRow("Unit (UOM):", uom_input)
        form.addRow("Per Box Qty:", per_box_input)
        form.addRow("VAT %:", vat_input)
        form.addRow("Selling Price:", sell_input)
        form.addRow("Low Stock Level:", low_input)
        form.addRow("Remarks:", remarks_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                update_item(item_code,
                            name=name_input.text().strip(),
                            uom=uom_input.text().strip(),
                            per_box_qty=int(per_box_input.text().strip() or 1),
                            vat_percentage=float(
                                vat_input.text().strip() or 0),
                            selling_price=float(
                                sell_input.text().strip() or 0),
                            low_stock_level=int(low_input.text().strip() or 0),
                            remarks=remarks_input.text().strip())
                QMessageBox.information(
                    self, "Success", "✅ Master data updated.")
                self.load_master_table()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"❌ Failed to update: {e}")

    def edit_batch_data(self):
        row = self.batch_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Batch",
                                "⚠️ Please select a batch to edit.")
            return

        stock_id = int(self.batch_table.item(row, 0).text())
        batch_no = self.batch_table.item(row, 1).text()
        purchase_price = self.batch_table.item(row, 2).text()
        qty = self.batch_table.item(row, 3).text()
        expiry_display = self.batch_table.item(
            row, 4).text()  # formatted display
        # But we also still have raw data in self.batches list; find matching batch to get raw expiry if available
        expiry_raw = ""
        for b in self.batches:
            if int(b[0]) == stock_id:
                expiry_raw = b[4] or ""
                break

        dialog = QDialog(self)
        dialog.setWindowTitle("✏️ Edit Batch")
        form = QFormLayout(dialog)

        purchase_input = QLineEdit(str(purchase_price))
        qty_input = QLineEdit(str(qty))

        expiry_input = QDateEdit()
        expiry_input.setCalendarPopup(True)
        expiry_input.setDisplayFormat("yyyy-MM-dd")
        parsed = _parse_date_to_dateobj(expiry_raw or expiry_display)
        if parsed:
            expiry_input.setDate(QDate(parsed.year, parsed.month, parsed.day))
        else:
            # set to current but we will allow user to clear later if you implement clearing
            expiry_input.setDate(QDate.currentDate())

        form.addRow("Purchase Price:", purchase_input)
        form.addRow("Quantity:", qty_input)
        form.addRow("Expiry (pick date):", expiry_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                from models.stock_model import DB_FILE as MODEL_DB_FILE
                conn = sqlite3.connect(MODEL_DB_FILE)
                cursor = conn.cursor()
                now = datetime.datetime.now().isoformat(timespec="seconds")

                expiry_val = expiry_input.date().toString(
                    "yyyy-MM-dd") if expiry_input.date().isValid() else None

                cursor.execute("""
                    UPDATE stock SET purchase_price = ?, quantity = ?, expiry_date = ?, updated_at = ?
                    WHERE id = ?
                """, (float(purchase_input.text().strip() or 0),
                      float(qty_input.text().strip() or 0),
                      expiry_val or None,
                      now, stock_id))
                conn.commit()
                conn.close()

                QMessageBox.information(self, "Success", "✅ Batch updated.")
                self.refresh_all()
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"❌ Failed to update batch: {e}")

    def reduce_qty_for_selected_batch(self):
        """
        Convenience: ask user qty to reduce for the selected master item (simulate billing)
        This will call reduce_stock_quantity(item_code, qty) which reduces across batches FIFO.
        """
        cur = self.master_table.currentRow()
        if cur < 0:
            QMessageBox.warning(self, "Select Item",
                                "⚠️ Please select an item to reduce.")
            return
        item_code = self.master_table.item(cur, 0).text()

        qty_text, ok = QInputDialog.getText(
            self, "Reduce Quantity", "Quantity to reduce:")
        if not ok or not qty_text.strip():
            return
        try:
            qty = float(qty_text.strip())
        except Exception:
            QMessageBox.warning(
                self, "Invalid", "Please enter a numeric quantity.")
            return

        try:
            res = reduce_stock_quantity(item_code, qty)
            msg = f"Reduced {qty}. Remaining: {res['remaining_qty']:.2f}."
            if res.get("fell_below"):
                msg += f"Item fell below its low stock level ({res['low_stock_level']})."
            QMessageBox.information(self, "Success", msg)
            # refresh
            self.load_master_table()
            self.load_batches_for_item(item_code)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to reduce stock: {e}")

    # -------------------------
    # Export helpers
    # -------------------------
    def export_master_to_excel(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Master Stock"

            headers = ["Item Code", "Name", "UOM", "Sell Price",
                       "Available Qty", "Low Level", "Status"]
            ws.append(headers)
            for row in self.consolidated:
                item_code, name, total_qty, uom, selling_price, low_level, is_below = row
                status = "LOW" if is_below else "OK"
                ws.append([item_code, name, uom, selling_price,
                          total_qty, low_level, status])

            today = datetime.date.today().strftime("%Y-%m-%d")
            fname = f"Master_Stock_{today}.xlsx"
            wb.save(fname)
            QMessageBox.information(
                self, "Exported", f"✅ Master exported to {fname}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"❌ Failed export: {e}")

    def export_batches_to_excel(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Batches"

            headers = ["ID", "Batch No", "Purchase Price",
                       "Qty", "Expiry", "Type", "Created At"]
            ws.append(headers)
            for b in self.batches:
                # id, batch_no, purchase_price, quantity, expiry_date, stock_type, created_at
                ws.append(list(b[:7]))

            today = datetime.date.today().strftime("%Y-%m-%d")
            fname = f"Batches_{today}.xlsx"
            wb.save(fname)
            QMessageBox.information(
                self, "Exported", f"✅ Batches exported to {fname}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"❌ Failed export: {e}")

    def toggle_low_stock_view(self):
        self.showing_low_stock_only = not self.showing_low_stock_only
        self.load_master_table()
