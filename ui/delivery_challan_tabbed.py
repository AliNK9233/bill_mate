import datetime
import os
import webbrowser
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QMessageBox, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QLabel, QLineEdit, QTextEdit,
    QGridLayout, QComboBox, QDoubleSpinBox, QCompleter
)
from PyQt5.QtCore import Qt
from models import delivery_model, stock_model
from models.invoice_model import get_invoice_items_by_no
from models.jobwork_model import get_jobwork_invoice_items
from utils.pdf_helper import generate_challan_pdf

class DeliveryChallanWindow(QWidget):
    """
    An integrated tabbed window for creating, viewing, and editing Delivery Challans.
    The creation form is embedded directly in a tab and can fetch from different invoice types.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delivery Challans")
        self.resize(1000, 700)
        self.edit_mode = False
        self.current_challan_id = None
        self.stock_list = []
        self.stock_code_map = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_change)

        self.create_edit_tab = self._create_create_edit_tab()
        self.view_tab = self._create_view_tab()

        self.tabs.addTab(self.create_edit_tab, "📝 Create / Edit Challan")
        self.tabs.addTab(self.view_tab, "📂 View Challans")

        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.new_challan_setup()

    def _create_create_edit_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # --- Feature: Fetch from Invoice ---
        fetch_layout = QHBoxLayout()
        fetch_layout.addWidget(QLabel("<b>Fetch Items from:</b>"))
        self.invoice_type_combo = QComboBox()
        self.invoice_type_combo.addItems(["Material Invoice", "Job Work Invoice"])
        self.invoice_fetch_input = QLineEdit()
        self.invoice_fetch_input.setPlaceholderText("Enter Invoice No...")
        fetch_btn = QPushButton("🔍 Fetch Items")
        fetch_btn.clicked.connect(self.fetch_items_from_invoice)
        fetch_layout.addWidget(self.invoice_type_combo)
        fetch_layout.addWidget(self.invoice_fetch_input, 1)
        fetch_layout.addWidget(fetch_btn)
        layout.addLayout(fetch_layout)
        
        # --- Header Grid ---
        header_grid = QGridLayout()
        self.company_text = QTextEdit()
        self.company_text.setReadOnly(True)
        self.challan_no_field = QLineEdit()
        self.challan_no_field.setReadOnly(True)
        self.datetime_field = QLineEdit()
        self.datetime_field.setReadOnly(True)
        header_grid.addWidget(QLabel("From (Company):"), 0, 0)
        header_grid.addWidget(self.company_text, 0, 1, 2, 1)
        header_grid.addWidget(QLabel("Challan No:"), 0, 2)
        header_grid.addWidget(self.challan_no_field, 0, 3)
        header_grid.addWidget(QLabel("Date / Time:"), 1, 2)
        header_grid.addWidget(self.datetime_field, 1, 3)
        layout.addLayout(header_grid)

        # --- To / Transport fields ---
        to_grid = QGridLayout()
        self.to_address = QTextEdit()
        self.to_gst = QLineEdit()
        self.transporter = QLineEdit()
        self.vehicle_no = QLineEdit()
        self.delivery_location = QLineEdit()
        to_grid.addWidget(QLabel("To (Address):"), 0, 0)
        to_grid.addWidget(self.to_address, 0, 1, 1, 3)
        to_grid.addWidget(QLabel("To GST No:"), 1, 0)
        to_grid.addWidget(self.to_gst, 1, 1)
        to_grid.addWidget(QLabel("Transporter Name:"), 1, 2)
        to_grid.addWidget(self.transporter, 1, 3)
        to_grid.addWidget(QLabel("Vehicle No:"), 2, 0)
        to_grid.addWidget(self.vehicle_no, 2, 1)
        to_grid.addWidget(QLabel("Delivery Location:"), 2, 2)
        to_grid.addWidget(self.delivery_location, 2, 3)
        layout.addLayout(to_grid)

        # --- Items table ---
        self.items_table = QTableWidget(0, 5, self)
        self.items_table.setHorizontalHeaderLabels(["Item Code", "Item Name", "HSN", "Qty", "Unit"])
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.items_table)

        # --- Row buttons + total ---
        row_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("➕ Add Row")
        add_row_btn.clicked.connect(self.add_row)
        remove_row_btn = QPushButton("➖ Remove Selected Row")
        remove_row_btn.clicked.connect(self.remove_selected_row)
        self.total_qty_label = QLabel("<b>Total Qty: 0</b>")
        row_btn_layout.addWidget(add_row_btn)
        row_btn_layout.addWidget(remove_row_btn)
        row_btn_layout.addStretch()
        row_btn_layout.addWidget(self.total_qty_label)
        layout.addLayout(row_btn_layout)
        
        # --- Bottom Action Buttons ---
        bottom_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save New Challan")
        self.save_btn.clicked.connect(self.save_challan)
        reset_btn = QPushButton("🔄 Reset Form")
        reset_btn.clicked.connect(self.new_challan_setup)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(reset_btn)
        layout.addLayout(bottom_layout)
        
        return widget

    def _create_view_tab(self):
        widget = QWidget()
        view_layout = QVBoxLayout(widget)
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_challans_table)
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self.edit_selected_challan)
        self.print_btn = QPushButton("Print Selected (PDF)")
        self.print_btn.clicked.connect(self.print_selected_challan)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.print_btn)
        btn_layout.addStretch()
        view_layout.addLayout(btn_layout)

        self.view_table = QTableWidget(0, 5)
        self.view_table.setHorizontalHeaderLabels(["ID", "Challan No", "Date/Time", "To Address", "Total Qty"])
        header = self.view_table.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        view_layout.addWidget(self.view_table)
        
        return widget

    def on_tab_change(self, index):
        if self.tabs.widget(index) == self.view_tab:
            self.load_challans_table()

    def fetch_items_from_invoice(self):
        invoice_no = self.invoice_fetch_input.text().strip()
        invoice_type = self.invoice_type_combo.currentText()
        if not invoice_no:
            QMessageBox.warning(self, "Input Required", "Please enter an invoice number.")
            return

        try:
            items = []
            if invoice_type == "Material Invoice":
                fetched_items = get_invoice_items_by_no(invoice_no)
                # Ensure the format is consistent for add_row
                for item in fetched_items:
                    items.append({
                        "item_code": item.get("item_code"), "item_name": item.get("item_name"),
                        "hsn_code": item.get("hsn_code"), "qty": item.get("qty"),
                        "unit": item.get("unit", "Nos") # Default unit if missing
                    })

            elif invoice_type == "Job Work Invoice":
                fetched_items = get_jobwork_invoice_items(invoice_no)
                # Transform job work items to fit the challan structure
                for item in fetched_items:
                    items.append({
                        "item_code": "", "item_name": item.get("description"),
                        "hsn_code": "", "qty": 1, "unit": "Job"
                    })

            if not items:
                QMessageBox.warning(self, "Not Found", f"No items found for '{invoice_no}'.")
                return

            self.items_table.setRowCount(0)
            for item in items:
                self.add_row(prefill=item)
            QMessageBox.information(self, "Success", f"Loaded {len(items)} items from {invoice_type}.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch invoice items: {e}")

    def new_challan_setup(self):
        self.edit_mode = False
        self.current_challan_id = None
        self.save_btn.setText("💾 Save New Challan")
        self.tabs.setTabText(0, "📝 Create Challan")
        self.challan_no_field.setText(delivery_model.get_next_challan_no())
        self.datetime_field.setText(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        for field in [self.to_address, self.to_gst, self.transporter, self.vehicle_no, self.delivery_location, self.invoice_fetch_input]:
            field.clear()
        self.items_table.setRowCount(0)
        self.add_row()
        self.update_total_qty()
        
    def load_challan_for_edit(self, challan_id):
        data = delivery_model.get_challan(challan_id)
        if not data:
            QMessageBox.warning(self, "Not Found", "Challan data could not be loaded.")
            return

        self.new_challan_setup()
        self.edit_mode = True
        self.current_challan_id = challan_id
        hdr = data["header"]
        self.save_btn.setText("💾 Save Changes")
        self.tabs.setTabText(0, f"📝 Editing {hdr.get('challan_no')}")
        self.challan_no_field.setText(hdr.get("challan_no", ""))
        self.datetime_field.setText(hdr.get("created_at", ""))
        self.to_address.setPlainText(hdr.get("to_address", ""))
        self.to_gst.setText(hdr.get("to_gst_no", ""))
        self.transporter.setText(hdr.get("transporter_name", ""))
        self.vehicle_no.setText(hdr.get("vehicle_no", ""))
        self.delivery_location.setText(hdr.get("delivery_location", ""))
        self.items_table.setRowCount(0)
        for it in data["items"]:
            self.add_row(prefill=it)
        self.tabs.setCurrentWidget(self.create_edit_tab)

    def add_row(self, prefill=None):
        row_pos = self.items_table.rowCount()
        self.items_table.insertRow(row_pos)
        code_combo = QComboBox()
        code_combo.setEditable(True)
        code_combo.addItems([""] + [s["code"] for s in self.stock_list])
        if prefill: code_combo.setCurrentText(prefill.get("item_code", ""))
        code_combo.currentTextChanged.connect(lambda txt, r=row_pos: self.on_code_changed(r, txt))
        self.items_table.setCellWidget(row_pos, 0, code_combo)
        self.items_table.setItem(row_pos, 1, QTableWidgetItem(prefill.get("item_name", "") if prefill else ""))
        self.items_table.setItem(row_pos, 2, QTableWidgetItem(prefill.get("hsn_code", "") if prefill else ""))
        qty_widget = QDoubleSpinBox()
        qty_widget.setMaximum(1_000_000)
        qty_widget.setDecimals(3)
        if prefill: qty_widget.setValue(float(prefill.get("qty", 0)))
        qty_widget.valueChanged.connect(self.update_total_qty)
        self.items_table.setCellWidget(row_pos, 3, qty_widget)
        self.items_table.setItem(row_pos, 4, QTableWidgetItem(prefill.get("unit", "") if prefill else ""))
        self.update_total_qty()

    def remove_selected_row(self):
        if self.items_table.currentRow() >= 0:
            self.items_table.removeRow(self.items_table.currentRow())
            self.update_total_qty()
            
    def on_code_changed(self, row, code_text):
        if code_text in self.stock_code_map:
            s = self.stock_code_map[code_text]
            self.items_table.setItem(row, 1, QTableWidgetItem(s["name"]))
            self.items_table.setItem(row, 2, QTableWidgetItem(s.get("hsn_code", "")))
            self.items_table.setItem(row, 4, QTableWidgetItem(s.get("unit", "")))

    def update_total_qty(self):
        total = sum(self.items_table.cellWidget(r, 3).value() for r in range(self.items_table.rowCount()) if self.items_table.cellWidget(r, 3))
        self.total_qty_label.setText(f"<b>Total Qty: {total:.3f}</b>")

    def save_challan(self):
        if not self.to_address.toPlainText().strip():
            QMessageBox.warning(self, "Validation", "Please enter a 'To Address'.")
            return
        items = self._get_items_from_table()
        if not items:
            QMessageBox.warning(self, "Validation", "Please add at least one item with a quantity > 0.")
            return

        header = {
            "to_address": self.to_address.toPlainText().strip(), "to_gst_no": self.to_gst.text().strip(),
            "transporter_name": self.transporter.text().strip(), "vehicle_no": self.vehicle_no.text().strip(),
            "delivery_location": self.delivery_location.text().strip(),
        }

        try:
            saved_id = None
            if self.edit_mode:
                delivery_model.update_challan(self.current_challan_id, header, items)
                saved_id = self.current_challan_id
                msg = f"Challan '{self.challan_no_field.text()}' was updated."
            else:
                cid, challan_no = delivery_model.create_challan(header, items)
                saved_id = cid
                msg = f"New challan '{challan_no}' was created."
            
            # Generate and open PDF
            pdf_path = generate_challan_pdf(saved_id, open_pdf=True)
            QMessageBox.information(self, "Success", f"{msg}\nPDF opened at:\n{pdf_path}")
            
            self.new_challan_setup()
            self.tabs.setCurrentWidget(self.view_tab)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save challan: {e}")

    def _get_items_from_table(self):
        items = []
        for r in range(self.items_table.rowCount()):
            code = self.items_table.cellWidget(r, 0).currentText().strip()
            name = self.items_table.item(r, 1).text().strip()
            qty = self.items_table.cellWidget(r, 3).value()
            if name and qty > 0:
                items.append({
                    "item_code": code, "item_name": name,
                    "hsn_code": self.items_table.item(r, 2).text().strip(),
                    "qty": qty, "unit": self.items_table.item(r, 4).text().strip()
                })
        return items

    def load_challans_table(self):
        try:
            rows = delivery_model.list_challans(limit=500)
            self.view_table.setRowCount(0)
            for r in rows:
                row_pos = self.view_table.rowCount()
                self.view_table.insertRow(row_pos)
                for ci, val in enumerate(r):
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    self.view_table.setItem(row_pos, ci, item)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Failed to load challans: {e}")

    def edit_selected_challan(self):
        cid = self.get_selected_challan_id()
        if cid:
            self.load_challan_for_edit(cid)
            
    def print_selected_challan(self):
        cid = self.get_selected_challan_id()
        if cid:
            try:
                generate_challan_pdf(cid, open_pdf=True)
            except Exception as e:
                QMessageBox.critical(self, "PDF Error", f"Failed to generate PDF: {e}")

    def get_selected_challan_id(self):
        row = self.view_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection Required", "Please select a challan.")
            return None
        try:
            return int(self.view_table.item(row, 0).text())
        except (ValueError, AttributeError):
            return None
            
    def showEvent(self, event):
        super().showEvent(event)
        try:
            profile = delivery_model.fetch_company_profile()
            if profile:
                self.company_text.setPlainText(f"{profile.get('name', '')}\n{profile.get('address', '')}")
            self.stock_list = stock_model.get_consolidated_stock_for_challan()
            self.stock_code_map = {s["code"]: s for s in self.stock_list}
            self.load_challans_table()
        except Exception as e:
            QMessageBox.critical(self, "Initialization Error", f"Could not load initial data: {e}")

