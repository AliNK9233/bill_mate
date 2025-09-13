# ui/edit_invoice_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QFormLayout,
    QDoubleSpinBox, QHeaderView, QComboBox, QFrame, QSpinBox, QCompleter
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon, QPixmap

import datetime
from typing import List, Dict, Any, Sequence

# Models - import what we need. Run from project root so `models` package is resolvable.
from models.invoice_model import fetch_invoice, update_invoice_entry
# optional helper (implement in invoice_model): saves items and adjusts stock
try:
    from models.invoice_model import save_invoice_items_and_recalc
except Exception:
    save_invoice_items_and_recalc = None

# optional helpers for readable displays
try:
    from models.salesman_model import get_all_salesmen
except Exception:
    get_all_salesmen = None

try:
    from models.customer_model import get_customer_dict, get_outlets, get_all_customers
except Exception:
    get_customer_dict = None
    get_outlets = None
    get_all_customers = None

# ---- CORRECT: use stock_model helper that exists in your project ----
try:
    from models.stock_model import get_item_by_item_code
except Exception:
    get_item_by_item_code = None


def parse_db_date(s):
    if not s:
        return None
    import datetime as _dt
    if isinstance(s, (_dt.date, _dt.datetime)):
        return s if isinstance(s, _dt.datetime) else _dt.datetime.combine(s, _dt.time())
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(str(s), fmt)
        except Exception:
            continue
    try:
        import dateutil.parser
        return dateutil.parser.parse(s)
    except Exception:
        return None


class EditInvoiceWindow(QWidget):
    """
    Invoice editing window.

    Bill To / Ship To / Sales Person are DISPLAY-ONLY (labels) and will not be written on Save.
    Inline item add uses searchable combo + qty.
    VAT detection uses item master if available, else a heuristic scanning numeric stock columns.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Invoice — BillMate")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setGeometry(200, 120, 1000, 720)

        self.current_invoice_no = None
        self.header = None
        self.items: List[Dict[str, Any]] = []

        # inline item map: display_text -> {code,name,avail,uom,rate,vat}
        self._inline_item_map: Dict[str, Dict[str, Any]] = {}

        self._setup_ui()
        # attempt to populate inline items now (if stock_model available)
        self._populate_inline_item_list()

    # ---------------------------
    # UI
    # ---------------------------
    def _setup_ui(self):
        root = QVBoxLayout()
        self.setLayout(root)

        # Title / logo
        header = QHBoxLayout()
        logo = QLabel()
        try:
            pix = QPixmap("data/logos/billmate_logo.png")
            if not pix.isNull():
                logo.setPixmap(pix.scaledToHeight(64, Qt.SmoothTransformation))
        except Exception:
            pass
        header.addWidget(logo, 0, Qt.AlignLeft)

        title_box = QVBoxLayout()
        title = QLabel("BillMate — Invoice Editor")
        title.setFont(QFont("SansSerif", 16, QFont.Bold))
        subtitle = QLabel(
            "Edit existing invoices — header fields are display-only")
        subtitle.setFont(QFont("SansSerif", 9))
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.lbl_edit_status = QLabel("")
        self.lbl_edit_status.setAlignment(Qt.AlignRight)
        self.lbl_edit_status.setFont(QFont("SansSerif", 10, QFont.Bold))
        header.addWidget(self.lbl_edit_status)
        root.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # Search
        sr = QHBoxLayout()
        sr.addWidget(QLabel("Invoice No:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Enter invoice number and press Load")
        sr.addWidget(self.search_input)
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.on_load_clicked)
        sr.addWidget(self.load_btn)
        sr.addStretch()
        root.addLayout(sr)

        # Header form (display-only bill/ship/sales)
        form = QFormLayout()
        self.lbl_invoice_no = QLabel("-")
        self.lbl_date = QLabel("-")
        form.addRow("Invoice No:", self.lbl_invoice_no)
        form.addRow("Date:", self.lbl_date)

        # DISPLAY-ONLY widgets
        self.lbl_bill_to_display = QLabel()
        self.lbl_bill_to_display.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.lbl_bill_to_display.setMinimumHeight(48)
        self.lbl_bill_to_display.setWordWrap(True)

        self.lbl_ship_to_display = QLabel()
        self.lbl_ship_to_display.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.lbl_ship_to_display.setWordWrap(True)

        self.lbl_sales_person_display = QLabel()
        self.lbl_sales_person_display.setFrameStyle(
            QFrame.Panel | QFrame.Sunken)

        # Editable small header fields still allowed
        self.input_lpo = QLineEdit()
        self.input_remarks = QLineEdit()
        form.addRow("Bill To:", self.lbl_bill_to_display)
        form.addRow("Ship To:", self.lbl_ship_to_display)
        form.addRow("Sales Person:", self.lbl_sales_person_display)
        form.addRow("LPO No:", self.input_lpo)
        form.addRow("Remarks:", self.input_remarks)

        # payment / status
        self.input_paid = QDoubleSpinBox()
        self.input_paid.setMaximum(10_000_000_000)
        self.input_paid.setDecimals(2)
        form.addRow("Paid Amount:", self.input_paid)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Active", "Partial", "Paid", "Cancelled"])
        form.addRow("Status:", self.status_combo)

        root.addLayout(form)

        # Inline add controls
        inline_row = QHBoxLayout()
        inline_row.addWidget(QLabel("Item:"))
        self.inline_item_combo = QComboBox()
        self.inline_item_combo.setEditable(True)
        inline_row.addWidget(self.inline_item_combo, 1)
        self.inline_qty = QSpinBox()
        self.inline_qty.setMinimum(1)
        self.inline_qty.setMaximum(999999)
        inline_row.addWidget(QLabel("Qty:"))
        inline_row.addWidget(self.inline_qty)
        self.add_item_btn = QPushButton("Add Item")
        self.add_item_btn.clicked.connect(self.on_add_item)
        inline_row.addWidget(self.add_item_btn)
        inline_row.addStretch()
        root.addLayout(inline_row)

        # Items table
        items_row = QHBoxLayout()
        items_row.addWidget(QLabel("Items:"))
        items_row.addStretch()
        self.del_item_btn = QPushButton("Delete Selected")
        self.del_item_btn.clicked.connect(self.on_delete_selected_items)
        items_row.addWidget(self.del_item_btn)
        root.addLayout(items_row)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(9)
        self.items_table.setHorizontalHeaderLabels([
            "S.No", "Item Code", "Item Name", "UOM", "Qty", "Rate", "VAT %", "FOC", "Line Total"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.setSelectionBehavior(self.items_table.SelectRows)
        # update totals when table cells change
        self.items_table.itemChanged.connect(self._on_table_item_changed)
        root.addWidget(self.items_table)

        # totals / actions
        bottom = QHBoxLayout()
        self.lbl_subtotal = QLabel("Subtotal: 0.00")
        self.lbl_vat = QLabel("VAT: 0.00")
        self.lbl_net = QLabel("Net: 0.00")
        bottom.addWidget(self.lbl_subtotal)
        bottom.addSpacing(12)
        bottom.addWidget(self.lbl_vat)
        bottom.addSpacing(12)
        bottom.addWidget(self.lbl_net)
        bottom.addStretch()

        self.btn_generate_delivery = QPushButton("Delivery Note (PDF)")
        self.btn_generate_delivery.clicked.connect(self.on_generate_delivery)
        bottom.addWidget(self.btn_generate_delivery)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.on_save)
        bottom.addWidget(self.save_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        bottom.addWidget(self.close_btn)

        root.addLayout(bottom)

        # disable until loaded
        self._set_enabled(False)

    def _set_enabled(self, enabled: bool):
        # Disable interactive controls when not editable
        # Bill/Ship/Sales are labels (always shown) and not enabled/disabled
        self.input_lpo.setEnabled(enabled)
        self.input_remarks.setEnabled(enabled)
        self.input_paid.setEnabled(enabled)
        self.status_combo.setEnabled(enabled)
        self.add_item_btn.setEnabled(enabled)
        self.del_item_btn.setEnabled(enabled)
        self.items_table.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.btn_generate_delivery.setEnabled(enabled)

    # ---------------------------
    # Inline item population & VAT detection heuristics
    # ---------------------------
    def _detect_vat_column_index(self, rows: Sequence[Sequence]) -> int:
        """
        Heuristic to detect which column in a sequence-row is VAT%:
        - If rows are mapping-like, caller should prefer dict key 'vat' etc.
        - For sequences, examine numeric columns (index >=4) and score them:
            score = count_in_0_30_range * 2 + count_with_fraction
        - Return best column index or -1 if none found.
        """
        if not rows:
            return -1
        max_sample = min(len(rows), 20)
        # Candidate columns range: start at index 4 (we assume earlier indices are code/name/qty/uom/rate)
        row0 = rows[0]
        if not isinstance(row0, (list, tuple)):
            return -1
        ncols = len(row0)
        start = 4
        if ncols <= start:
            return -1
        scores = {}
        for col in range(start, ncols):
            scores[col] = {"count": 0, "in_range": 0, "non_int": 0}
        for r in rows[:max_sample]:
            for col in range(start, ncols):
                try:
                    v = r[col]
                    if v is None or v == "":
                        continue
                    # try numeric conversion
                    fv = float(v)
                    scores[col]["count"] += 1
                    if 0.0 <= fv <= 100.0:
                        scores[col]["in_range"] += 1
                    # fractional part check (VAT sometimes has decimals)
                    if abs(fv - int(fv)) > 1e-6:
                        scores[col]["non_int"] += 1
                except Exception:
                    continue
        # compute final score
        best_col = -1
        best_score = -1
        for col, s in scores.items():
            # weight in_range higher; fractional part also helps
            score = s["in_range"] * 2 + s["non_int"]
            # also penalize if count is zero
            if s["count"] == 0:
                score = -1
            if score > best_score:
                best_score = score
                best_col = col
        return best_col if best_score > 0 else -1

    def _populate_inline_item_list(self):
        """
        Build inline combo using models.stock_model.get_consolidated_stock (if present).
        Prefer VAT from item master (get_item_by_item_code). If not available, detect vat col heuristically.
        """
        self._inline_item_map.clear()
        self.inline_item_combo.clear()

        try:
            from models.stock_model import get_consolidated_stock
        except Exception:
            get_consolidated_stock = None

        stock_rows = []
        if get_consolidated_stock:
            try:
                stock_rows = list(get_consolidated_stock() or [])
            except Exception:
                stock_rows = []

        # If stock_rows contain mapping rows (dict-like), prefer keys
        vat_index = -1
        if stock_rows and isinstance(stock_rows[0], (list, tuple)):
            vat_index = self._detect_vat_column_index(stock_rows)
            print(f"Detected VAT column index: {vat_index}")

        entries = []
        for r in stock_rows:
            try:
                # support both sequence and mapping rows
                if isinstance(r, dict):
                    code = r.get("item_code") or r.get(
                        "code") or r.get("item") or ""
                    name = r.get("item_name") or r.get(
                        "name") or r.get("description") or ""
                    avail = float(r.get("total_qty") or r.get(
                        "available") or r.get("qty") or 0)
                    uom = r.get("uom") or ""
                    rate = float(r.get("rate") or r.get("price") or 0.0)
                    # try vat keys first
                    vat = None
                    for k in ("vat_percentage", "vat", "vat_pct", "tax_percent"):
                        if k in r and r[k] is not None and str(r[k]).strip() != "":
                            try:
                                vat = float(r[k])
                                break
                            except Exception:
                                vat = None
                    if vat is None:
                        vat = 0.0
                else:
                    # sequence-like row: attempt common ordering
                    row = list(r)
                    code = str(row[0]) if len(row) > 0 else ""
                    name = str(row[1]) if len(row) > 1 else ""
                    try:
                        avail = float(row[2]) if len(
                            row) > 2 and row[2] is not None else 0.0
                    except Exception:
                        avail = 0.0
                    uom = str(row[3]) if len(row) > 3 else ""
                    try:
                        rate = float(row[4]) if len(
                            row) > 4 and row[4] is not None else 0.0
                    except Exception:
                        rate = 0.0
                    # VAT resolution:
                    vat = None
                    # prefer detected vat_index if valid
                    if vat_index >= 0 and vat_index < len(row):
                        try:
                            vat = float(row[vat_index])
                        except Exception:
                            vat = None
                    # fallback: take first numeric column after index 4 that looks like percentage 0..100
                    if vat is None:
                        for ci in range(5, len(row)):
                            try:
                                fv = float(row[ci])
                                if 0.0 <= fv <= 100.0:
                                    vat = fv
                                    break
                            except Exception:
                                continue
                        if vat is None:
                            vat = 0.0

                # if we have item master, prefer its VAT
                if get_item_by_item_code and code:
                    try:
                        im = get_item_by_item_code(code)
                        if im:
                            # accept dict-like returns
                            if isinstance(im, dict):
                                vat_candidate = im.get("vat_percentage") or im.get(
                                    "vat") or im.get("vat_pct")
                                if vat_candidate is not None and str(vat_candidate).strip() != "":
                                    vat = float(vat_candidate)
                            else:
                                # tuple/list -> try known indices (item_master format in stock_model)
                                try:
                                    # stock_model.item_master columns: id, item_code, name, uom, per_box_qty, vat_percentage, selling_price, remarks, low_stock_level, created_at, updated_at
                                    if len(im) > 5:
                                        vat = float(im[5])
                                except Exception:
                                    pass
                    except Exception:
                        pass

                display = f"{code} - {name} (avail: {int(avail) if avail == int(avail) else avail})"
                entries.append(display)
                self._inline_item_map[display] = {
                    "code": code, "name": name, "avail": avail, "uom": uom, "rate": rate, "vat": float(vat or 0.0)}
            except Exception:
                continue

        # add entries to combo, attach completer
        if entries:
            self.inline_item_combo.addItems(entries)
            completer = QCompleter(entries, self.inline_item_combo)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.inline_item_combo.setCompleter(completer)

    # ---------------------------
    # Load / populate
    # ---------------------------
    def on_load_clicked(self):
        inv_no = self.search_input.text().strip()
        if not inv_no:
            QMessageBox.warning(self, "Input required",
                                "Enter invoice number to load.")
            return
        try:
            header, items = fetch_invoice(inv_no)
        except Exception as e:
            QMessageBox.warning(self, "Load failed",
                                f"Could not fetch invoice: {e}")
            return

        if not header:
            QMessageBox.warning(self, "Not found",
                                f"Invoice '{inv_no}' not found.")
            return

        self.current_invoice_no = inv_no
        self.header = header
        self.items = [dict(it) for it in (items or [])]
        # refresh inline map and header/items UI
        self._populate_inline_item_list()
        self._populate_header_and_items()

    def _populate_header_and_items(self):
        h = self.header

        def get(k, idx=None, default=""):
            if h is None:
                return default
            try:
                if hasattr(h, "get"):
                    if k in h:
                        v = h.get(k)
                        return v if v is not None else default
            except Exception:
                pass
            if isinstance(h, (list, tuple)) and idx is not None and idx < len(h):
                v = h[idx]
                return v if v is not None else default
            return default

        inv_no = get("invoice_no", 1, default=self.current_invoice_no or "-")
        inv_date = get("invoice_date", 2, default="")
        inv_dt = parse_db_date(inv_date)
        dt_str = inv_dt.strftime("%Y-%m-%d %H:%M") if inv_dt else str(inv_date)

        bill_to = get("bill_to", 4, "")
        ship_to = get("ship_to", 5, "")
        salesperson = get("salesman_name", 18, "") or get(
            "salesman_name", 18, "")
        lpo = get("lpo_no", 6, "")
        remarks = get("remarks", 15, "")
        paid = get("paid_amount", 14, 0.0)
        status = (get("status", 16, "Active") or "").strip()

        total_amount = get("total_amount", 8, 0.0)
        vat_amount = get("vat_amount", 9, 0.0)
        net_total = get("net_total", 10, None)
        if net_total is None or net_total == "":
            try:
                net_total = float(total_amount or 0.0) + \
                    float(vat_amount or 0.0)
            except Exception:
                net_total = 0.0

        balance = get("balance", 13, None)
        if balance is None or balance == "":
            try:
                balance = float(net_total or 0.0) - float(paid or 0.0)
            except Exception:
                balance = 0.0

        # header labels
        self.lbl_invoice_no.setText(str(inv_no))
        self.lbl_date.setText(dt_str)

        # Bill To display: prefer nice lookup if available, else raw text
        try:
            if get_all_customers:
                matched_display = None
                for r in get_all_customers() or []:
                    code = r[0]
                    name = r[1] if len(r) > 1 else code
                    display = f"{code} - {name}"
                    if str(bill_to).strip() and str(bill_to).strip() in display:
                        matched_display = display
                        break
                self.lbl_bill_to_display.setText(
                    matched_display or str(bill_to))
            else:
                self.lbl_bill_to_display.setText(str(bill_to))
        except Exception:
            self.lbl_bill_to_display.setText(str(bill_to))

        # Ship To
        try:
            outlet_id = h.get("outlet_id") if hasattr(
                h, "get") else (h[19] if len(h) > 19 else None)
            if outlet_id and get_outlets:
                try:
                    outs = get_outlets(outlet_id)
                    if outs:
                        row = outs[0] if isinstance(
                            outs, (list, tuple)) and outs else None
                        outlet_display = row[2] if row and len(
                            row) > 2 else str(ship_to)
                        self.lbl_ship_to_display.setText(outlet_display)
                    else:
                        self.lbl_ship_to_display.setText(str(ship_to))
                except Exception:
                    self.lbl_ship_to_display.setText(str(ship_to))
            else:
                self.lbl_ship_to_display.setText(str(ship_to))
        except Exception:
            self.lbl_ship_to_display.setText(str(ship_to))

        # Salesperson display
        try:
            sid = h.get("salesman_id") if hasattr(h, "get") else None
            shown = None
            if sid and get_all_salesmen:
                for r in get_all_salesmen() or []:
                    emp_id = r[0]
                    name = r[1] if len(r) > 1 else emp_id
                    if str(emp_id) == str(sid):
                        shown = f"{name} ({emp_id})"
                        break
            self.lbl_sales_person_display.setText(shown or str(salesperson))
        except Exception:
            self.lbl_sales_person_display.setText(str(salesperson))

        # LPO / remarks / paid / status
        self.input_lpo.setText(str(lpo))
        self.input_remarks.setText(str(remarks))
        try:
            self.input_paid.setValue(float(paid or 0.0))
        except Exception:
            self.input_paid.setValue(0.0)
        try:
            idx = self.status_combo.findText(str(status), Qt.MatchFixedString)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        except Exception:
            pass

        # Ensure items have net_amount computed
        for it in self.items:
            try:
                qty = float(it.get("quantity") or 0)
                rate = 0.0 if it.get("free") else float(it.get("rate") or 0.0)
                vat_pct = float(it.get("vat_percentage") or 0.0)
                sub = 0.0 if it.get("free") else (qty * rate)
                vat_amt = 0.0 if it.get("free") else (sub * vat_pct / 100.0)
                it["vat_amount"] = vat_amt
                it["net_amount"] = sub + vat_amt
            except Exception:
                it["vat_amount"] = it.get("vat_amount") or 0.0
                it["net_amount"] = it.get("net_amount") or 0.0

        self._refresh_items_table()

        # editability rules
        editable = True
        if inv_dt:
            age_days = (datetime.datetime.now() - inv_dt).days
            if age_days > 3:
                editable = False
                self.lbl_edit_status.setText("Locked: >3 days old")
                self.lbl_edit_status.setStyleSheet("color: darkred")
        if str(status).lower() == "cancelled":
            editable = False
            self.lbl_edit_status.setText("Locked: Cancelled")
            self.lbl_edit_status.setStyleSheet("color: darkred")
        if editable and (not inv_dt):
            self.lbl_edit_status.setText("Editable")
            self.lbl_edit_status.setStyleSheet("color: darkgreen")

        self._set_enabled(editable)

    # ---------------------------
    # Items table helpers
    # ---------------------------
    def _refresh_items_table(self):
        try:
            self.items_table.blockSignals(True)
        except Exception:
            pass

        self.items_table.setRowCount(0)
        subtotal = 0.0
        total_vat = 0.0
        net_total = 0.0
        for idx, it in enumerate(self.items, start=1):
            r = self.items_table.rowCount()
            self.items_table.insertRow(r)
            sno = it.get("serial_no") or idx
            code = it.get("item_code") or ""
            name = it.get("item_name") or ""
            uom = it.get("uom") or ""
            qty = it.get("quantity") or 0
            rate = it.get("rate") or 0
            vat_pct = it.get("vat_percentage") or 0
            foc = bool(it.get("free") or it.get("foc") or False)
            vat_amt = it.get("vat_amount")
            line_net = it.get("net_amount")

            try:
                qty_f = float(qty or 0)
                rate_f = float(rate or 0)
                vat_pct_f = float(vat_pct or 0)
            except Exception:
                qty_f = rate_f = vat_pct_f = 0.0
            sub = 0.0 if foc else (qty_f * rate_f)
            vat_amt_calc = 0.0 if foc else (
                (sub * vat_pct_f / 100.0) if vat_pct_f else (vat_amt or 0.0))
            net_calc = (sub + vat_amt_calc)
            try:
                line_net_val = float(
                    line_net) if line_net is not None else net_calc
            except Exception:
                line_net_val = net_calc

            # Fill cells
            self.items_table.setItem(r, 0, QTableWidgetItem(str(sno)))
            code_item = QTableWidgetItem(str(code))
            code_item.setFlags(code_item.flags() | Qt.ItemIsEditable)
            self.items_table.setItem(r, 1, code_item)
            name_item = QTableWidgetItem(str(name))
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            self.items_table.setItem(r, 2, name_item)
            self.items_table.setItem(r, 3, QTableWidgetItem(str(uom)))
            qty_item = QTableWidgetItem(str(qty_f))
            qty_item.setFlags(qty_item.flags() | Qt.ItemIsEditable)
            self.items_table.setItem(r, 4, qty_item)
            rate_item = QTableWidgetItem(f"{float(rate_f):.2f}")
            rate_item.setFlags(rate_item.flags() | Qt.ItemIsEditable)
            self.items_table.setItem(r, 5, rate_item)
            vat_item = QTableWidgetItem(str(vat_pct or "0"))
            vat_item.setFlags(vat_item.flags() | Qt.ItemIsEditable)
            self.items_table.setItem(r, 6, vat_item)
            foc_item = QTableWidgetItem()
            foc_item.setFlags(foc_item.flags() |
                              Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            foc_item.setCheckState(Qt.Checked if foc else Qt.Unchecked)
            self.items_table.setItem(r, 7, foc_item)
            line_item = QTableWidgetItem(f"{float(line_net_val):.2f}")
            line_item.setFlags(line_item.flags() & ~Qt.ItemIsEditable)
            self.items_table.setItem(r, 8, line_item)

            subtotal += sub
            total_vat += vat_amt_calc
            net_total += line_net_val

        self.lbl_subtotal.setText(f"Subtotal: {subtotal:.2f}")
        self.lbl_vat.setText(f"VAT: {total_vat:.2f}")
        self.lbl_net.setText(f"Net: {net_total:.2f}")

        try:
            self.items_table.blockSignals(False)
        except Exception:
            pass

    def on_add_item(self):
        sel_text = self.inline_item_combo.currentText().strip()
        if not sel_text:
            QMessageBox.warning(self, "Select item",
                                "Select or type an item first.")
            return
        info = self._inline_item_map.get(sel_text)
        # allow substring match
        if not info:
            for k, v in self._inline_item_map.items():
                if sel_text.lower() in k.lower():
                    info = v
                    break
        if not info:
            info = {"code": sel_text, "name": sel_text,
                    "avail": 0, "uom": "", "rate": 0.0, "vat": 0.0}

        qty = int(self.inline_qty.value() or 0)
        if qty <= 0:
            QMessageBox.warning(self, "Invalid qty", "Quantity must be > 0")
            return

        rate = float(info.get("rate", 0.0) or 0.0)
        vat_pct = float(info.get("vat", 0.0) or 0.0)
        sub = qty * rate
        vat_amt = sub * (vat_pct / 100.0) if vat_pct else 0.0
        net_amount = sub + vat_amt

        new_item = {
            "serial_no": len(self.items) + 1,
            "item_code": info.get("code"),
            "item_name": info.get("name"),
            "uom": info.get("uom", ""),
            "quantity": qty,
            "rate": rate,
            "vat_percentage": vat_pct,
            "vat_amount": vat_amt,
            "net_amount": net_amount,
            "free": False,
        }
        self.items.append(new_item)
        self._refresh_items_table()

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if not item:
            return
        row = item.row()
        # prevent recursion
        try:
            self.items_table.blockSignals(True)
        except Exception:
            pass
        try:
            def text_at(c):
                it = self.items_table.item(row, c)
                return it.text() if it and it.text() is not None else ""

            sno = text_at(0)
            code = text_at(1)
            name = text_at(2)
            uom = text_at(3)
            qty_text = text_at(4)
            rate_text = text_at(5)
            vat_text = text_at(6)
            foc_item = self.items_table.item(row, 7)
            foc = False
            try:
                foc = (foc_item.checkState() ==
                       Qt.Checked) if foc_item is not None else False
            except Exception:
                foc = False

            try:
                qty = float(qty_text)
            except Exception:
                qty = 0.0
            try:
                rate = float(rate_text)
            except Exception:
                rate = 0.0
            try:
                vat_pct = float(vat_text)
            except Exception:
                vat_pct = 0.0

            if foc:
                sub = 0.0
                vat_amt = 0.0
            else:
                sub = qty * rate
                vat_amt = sub * (vat_pct / 100.0) if vat_pct else 0.0
            net_amount = sub + vat_amt

            # update line total
            line_item = QTableWidgetItem(f"{net_amount:.2f}")
            line_item.setFlags(line_item.flags() & ~Qt.ItemIsEditable)
            self.items_table.setItem(row, 8, line_item)

            # sync to self.items
            if 0 <= row < len(self.items):
                self.items[row]["serial_no"] = int(
                    sno) if str(sno).isdigit() else (row + 1)
                self.items[row]["item_code"] = code
                self.items[row]["item_name"] = name
                self.items[row]["uom"] = uom
                self.items[row]["quantity"] = qty
                self.items[row]["rate"] = rate if not foc else 0.0
                self.items[row]["vat_percentage"] = vat_pct if not foc else 0.0
                self.items[row]["vat_amount"] = vat_amt
                self.items[row]["net_amount"] = net_amount
                self.items[row]["free"] = foc
        finally:
            self._recalc_totals_from_table()
            try:
                self.items_table.blockSignals(False)
            except Exception:
                pass

    def _recalc_totals_from_table(self):
        subtotal = 0.0
        total_vat = 0.0
        net_total = 0.0
        for r in range(self.items_table.rowCount()):
            try:
                qty = float(self.items_table.item(r, 4).text()
                            if self.items_table.item(r, 4) else 0)
            except Exception:
                qty = 0.0
            try:
                rate = float(self.items_table.item(r, 5).text()
                             if self.items_table.item(r, 5) else 0)
            except Exception:
                rate = 0.0
            try:
                vat_pct = float(self.items_table.item(r, 6).text()
                                if self.items_table.item(r, 6) else 0)
            except Exception:
                vat_pct = 0.0
            foc_it = self.items_table.item(r, 7)
            foc = False
            try:
                foc = (foc_it.checkState() ==
                       Qt.Checked) if foc_it is not None else False
            except Exception:
                foc = False

            sub = 0.0 if foc else (qty * rate)
            vat_amt = 0.0 if foc else (sub * vat_pct / 100.0)
            line_net = sub + vat_amt
            subtotal += sub
            total_vat += vat_amt
            net_total += line_net
            # ensure displayed line total matches computed
            try:
                lt = self.items_table.item(r, 8)
                if lt is None or lt.text() != f"{line_net:.2f}":
                    lt_item = QTableWidgetItem(f"{line_net:.2f}")
                    lt_item.setFlags(lt_item.flags() & ~
                                     Qt.ItemIsEditable) if lt else None
                    self.items_table.setItem(r, 8, lt_item)
            except Exception:
                pass
        self.lbl_subtotal.setText(f"Subtotal: {subtotal:.2f}")
        self.lbl_vat.setText(f"VAT: {total_vat:.2f}")
        self.lbl_net.setText(f"Net: {net_total:.2f}")

    def on_delete_selected_items(self):
        rows = sorted(
            set([idx.row() for idx in self.items_table.selectedIndexes()]), reverse=True)
        if not rows:
            QMessageBox.information(
                self, "Select rows", "Select row(s) to delete first.")
            return
        ok = QMessageBox.question(
            self, "Confirm delete", f"Delete {len(rows)} selected item(s)?")
        if ok != QMessageBox.Yes:
            return
        for r in rows:
            if 0 <= r < len(self.items):
                del self.items[r]
        # renumber
        for i, it in enumerate(self.items, start=1):
            it["serial_no"] = i
        self._refresh_items_table()

    # ---------------------------
    # Save / validations
    # ---------------------------
    def _collect_items_from_table(self) -> List[Dict[str, Any]]:
        items_out = []
        for r in range(self.items_table.rowCount()):
            try:
                sno = self.items_table.item(r, 0).text()
            except Exception:
                sno = r + 1
            code = (self.items_table.item(r, 1).text()
                    if self.items_table.item(r, 1) else "")
            name = (self.items_table.item(r, 2).text()
                    if self.items_table.item(r, 2) else "")
            uom = (self.items_table.item(r, 3).text()
                   if self.items_table.item(r, 3) else "")
            qty_text = (self.items_table.item(r, 4).text()
                        if self.items_table.item(r, 4) else "0")
            rate_text = (self.items_table.item(r, 5).text()
                         if self.items_table.item(r, 5) else "0.00")
            vat_text = (self.items_table.item(r, 6).text()
                        if self.items_table.item(r, 6) else "0")
            foc_item = self.items_table.item(r, 7)
            foc = False
            try:
                foc = (foc_item.checkState() ==
                       Qt.Checked) if foc_item is not None else False
            except Exception:
                foc = False
            try:
                qty = float(qty_text)
            except Exception:
                qty = 0.0
            try:
                rate = float(rate_text)
            except Exception:
                rate = 0.0
            try:
                vat_pct = float(vat_text)
            except Exception:
                vat_pct = 0.0
            sub = 0.0 if foc else (qty * rate)
            vat_amt = 0.0 if foc else (sub * (vat_pct / 100.0))
            net_amount = sub + vat_amt
            items_out.append({
                "serial_no": int(sno) if str(sno).isdigit() else (r + 1),
                "item_code": code,
                "item_name": name,
                "uom": uom,
                "quantity": qty,
                "rate": rate,
                "vat_percentage": vat_pct,
                "vat_amount": vat_amt,
                "net_amount": net_amount,
                "free": foc,
            })
        return items_out

    def on_save(self):
        if not self.current_invoice_no:
            QMessageBox.warning(self, "No invoice", "Load an invoice first.")
            return

        # validation: editable only within 3 days and not cancelled
        inv_date = None
        try:
            inv_date = self.header.get("invoice_date") if hasattr(
                self.header, "get") else (self.header[2] if len(self.header) > 2 else None)
        except Exception:
            inv_date = None
        dt = parse_db_date(inv_date)
        if dt:
            age_days = (datetime.datetime.now() - dt).days
            if age_days > 3:
                QMessageBox.warning(
                    self, "Not allowed", "Editing allowed only within 3 days of invoice date.")
                return

        status = None
        try:
            status = self.header.get("status") if hasattr(self.header, "get") else (
                self.header[16] if len(self.header) > 16 else None)
        except Exception:
            status = None
        if status and str(status).lower() == "cancelled":
            QMessageBox.warning(self, "Not allowed",
                                "Cannot edit a cancelled invoice.")
            return

        # IMPORTANT: Bill To / Ship To / Sales Person are display-only and will NOT be written back.
        lpo_no = self.input_lpo.text().strip()
        remarks = self.input_remarks.text().strip()
        paid_now = float(self.input_paid.value() or 0.0)
        status_val = self.status_combo.currentText(
        ) if self.status_combo.currentIndex() >= 0 else None

        # collect items
        items_payload = self._collect_items_from_table()

        # totals & validate paid <= net_total
        net_total = sum([it["net_amount"]
                        for it in items_payload]) if items_payload else 0.0
        if paid_now < 0:
            QMessageBox.warning(self, "Invalid paid",
                                "Paid amount must be positive.")
            return
        if paid_now > net_total + 0.0001:
            QMessageBox.warning(self, "Invalid paid",
                                "Paid amount cannot exceed invoice net total.")
            return

        # Only update safe header fields (do NOT overwrite bill_to/ship_to/salesman_id)
        header_updates = {
            "lpo_no": lpo_no,
            "remarks": remarks,
            "status": status_val,
            "paid_amount": paid_now,
            "balance": max(0.0, net_total - paid_now)
        }

        try:
            update_invoice_entry(self.current_invoice_no, **header_updates)
        except Exception as e:
            QMessageBox.warning(self, "Save failed",
                                f"Failed to update invoice header: {e}")
            return

        # Save items via model helper (recommended) which will adjust stock if implemented
        items_saved = False
        if save_invoice_items_and_recalc:
            try:
                # adjust_stock=True to reflect item qty changes in stock. Model must implement this safely.
                save_invoice_items_and_recalc(
                    self.current_invoice_no, items_payload, adjust_stock=True)
                items_saved = True
            except Exception as e:
                QMessageBox.warning(self, "Items save failed",
                                    f"Header saved but failed to save items: {e}")
        else:
            if items_payload != self.items:
                QMessageBox.information(
                    self, "Items not saved", "Header saved. Items were modified but model does not provide 'save_invoice_items_and_recalc'. Implement it to persist item edits and adjust stock.")
            else:
                items_saved = True

        QMessageBox.information(self, "Saved", "Invoice updated successfully.")
        # reload to refresh computed values
        self.on_load_clicked()

    # ---------------------------
    # Delivery note stub
    # ---------------------------
    def on_generate_delivery(self):
        if not self.current_invoice_no:
            QMessageBox.warning(self, "No invoice", "Load an invoice first.")
            return
        try:
            QMessageBox.information(
                self, "Delivery Note", "Call your delivery-note generator here.")
        except Exception as e:
            QMessageBox.warning(
                self, "Failed", f"Failed to generate delivery note: {e}")
