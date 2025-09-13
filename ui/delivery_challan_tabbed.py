# ui/delivery_challan_tabbed.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QMessageBox, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QLabel, QVBoxLayout as QV,
    QDialogButtonBox
)
from PyQt5.QtCore import Qt
import models.delivery_model as delivery_model
from ui.delivery_challan_dialog import DeliveryChallanDialog
from utils.pdf_helper import generate_challan_pdf


class DeliveryChallanTabbedWindow(QWidget):
    """
    Tabbed window: Create Challan (opens modal dialog) + View/Edit/Print tab.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delivery Challans")
        self.resize(1000, 700)

        self.setup_ui()
        self.load_challans_table()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()

        # Tab 1: Create (button that opens modal dialog)
        self.create_tab = QWidget()
        create_layout = QVBoxLayout()
        create_btn_layout = QHBoxLayout()
        create_btn = QPushButton("Create New Challan")
        create_btn.clicked.connect(self.create_new_challan)
        create_btn_layout.addStretch()
        create_btn_layout.addWidget(create_btn)
        create_layout.addLayout(create_btn_layout)
        # optional instructions / quick actions area
        create_layout.addWidget(
            QLabel("Click 'Create New Challan' to open the challan editor."))
        self.create_tab.setLayout(create_layout)
        self.tabs.addTab(self.create_tab, "Create Challan")

        # Tab 2: View / Edit / Print
        self.view_tab = QWidget()
        view_layout = QVBoxLayout()

        # Buttons
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_challans_table)
        self.open_btn = QPushButton("Preview Selected")
        self.open_btn.clicked.connect(self.open_selected_challan)
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self.edit_selected_challan)
        self.print_btn = QPushButton("Print Selected (PDF)")
        self.print_btn.clicked.connect(self.print_selected_challan)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.print_btn)
        btn_layout.addStretch()
        view_layout.addLayout(btn_layout)

        # Table of challans
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Challan No", "Date/Time", "To Address", "Total Qty"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        view_layout.addWidget(self.table)

        self.view_tab.setLayout(view_layout)
        self.tabs.addTab(self.view_tab, "View / Edit Challans")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    # ----------------- Actions -----------------
    def create_new_challan(self):
        """
        Open the DeliveryChallanDialog in create mode (modal). Refresh list after successful creation.
        If a challan was created, generate and open its PDF immediately.
        """
        dlg = DeliveryChallanDialog(parent=self, edit_mode=False)
        if dlg.exec_() == QDialog.Accepted:
            # refresh the list to show newly created challan
            self.load_challans_table()

            # If the dialog created a challan it will have challan_id set.
            try:
                cid = getattr(dlg, "challan_id", None)
                if cid:
                    try:
                        pdf_path = generate_challan_pdf(cid, open_pdf=True)
                        QMessageBox.information(
                            self, "Created", f"Challan created and PDF opened:\n{pdf_path}")
                    except Exception as e:
                        # PDF generation shouldn't block the UI — show warning but continue
                        QMessageBox.warning(self, "Created (no PDF)",
                                            f"Challan created but failed to generate PDF:\n{e}")
                else:
                    QMessageBox.information(
                        self, "Created", "Challan created successfully.")
            except Exception:
                # Fallback message if something unexpected happens
                QMessageBox.information(
                    self, "Created", "Challan created successfully.")

    def load_challans_table(self):
        """
        Refresh the table with recent challans.
        """
        try:
            rows = delivery_model.list_challans(limit=500)
        except Exception as e:
            QMessageBox.critical(
                self, "DB Error", f"Failed to load challans: {e}")
            return

        self.table.setRowCount(0)
        for r in rows:
            row_pos = self.table.rowCount()
            self.table.insertRow(row_pos)
            for ci, val in enumerate(r):
                item = QTableWidgetItem(str(val) if val is not None else "")
                # don't allow editing from the table cell directly
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row_pos, ci, item)

    def get_selected_challan_id(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "Select", "Please select a challan in the table.")
            return None
        id_item = self.table.item(row, 0)
        if not id_item:
            QMessageBox.warning(
                self, "Select", "Could not determine selected challan id.")
            return None
        try:
            return int(id_item.text())
        except Exception:
            QMessageBox.warning(self, "Select", "Invalid challan id selected.")
            return None

    def open_selected_challan(self):
        """
        Preview the selected challan in a read-only dialog.
        """
        cid = self.get_selected_challan_id()
        if not cid:
            return
        data = delivery_model.get_challan(cid)
        if not data:
            QMessageBox.warning(self, "Not found",
                                "Selected challan not found.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(
            f"Challan Preview: {data['header'].get('challan_no')}")
        v = QV()
        v.addWidget(QLabel(f"Challan No: {data['header'].get('challan_no')}"))
        v.addWidget(QLabel(f"Date: {data['header'].get('created_at')}"))
        v.addWidget(QLabel(f"To: {data['header'].get('to_address')}"))
        v.addWidget(QLabel(
            f"Transporter: {data['header'].get('transporter_name') or ''}  Vehicle: {data['header'].get('vehicle_no') or ''}"))
        v.addWidget(QLabel(f"Total Qty: {data['header'].get('total_qty')}"))
        v.addWidget(QLabel("Items:"))
        for it in data['items']:
            v.addWidget(QLabel(
                f" - {it.get('item_name')} ({it.get('item_code')}) x {it.get('qty')} {it.get('unit')}"))
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.reject)
        v.addWidget(btn_box)
        dlg.setLayout(v)
        dlg.exec_()

    def edit_selected_challan(self):
        """
        Open selected challan in DeliveryChallanDialog in edit mode.
        The dialog will call update_challan internally and accept() on save.
        """
        cid = self.get_selected_challan_id()
        if not cid:
            return

        # ensure challan exists
        data = delivery_model.get_challan(cid)
        if not data:
            QMessageBox.warning(self, "Not found",
                                "Selected challan not found.")
            return

        dlg = DeliveryChallanDialog(
            parent=self, edit_mode=True, challan_id=cid)
        if dlg.exec_() == QDialog.Accepted:
            # refreshed after edit
            self.load_challans_table()
            QMessageBox.information(
                self, "Saved", "Challan updated successfully.")
        else:
            # user cancelled edit
            pass

    def print_selected_challan(self):
        """
        Generate a PDF for the selected challan using ReportLab and open it.
        """
        cid = self.get_selected_challan_id()
        if not cid:
            return
        try:
            pdf_path = generate_challan_pdf(cid, open_pdf=True)
            QMessageBox.information(
                self, "PDF",
                f"PDF created:\n{pdf_path}\n\nIt should open in your default PDF viewer."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to generate PDF:\n{e}")


# Simple placeholder PDF/text generator so the UI has something to call.
def generate_challan_pdf_placeholder(challan_id):
    """
    Placeholder function called by UI for print/save as PDF.
    Replace or hook this to your real PDF helper later (reportlab).
    """
    data = delivery_model.get_challan(challan_id)
    if not data:
        return False
    import os
    out_dir = "data/exports"
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, f"{data['header'].get('challan_no')}.txt")
    try:
        with open(fname, "w", encoding="utf8") as f:
            f.write(
                f"Challan: {data['header'].get('challan_no')}\nDate: {data['header'].get('created_at')}\nTo: {data['header'].get('to_address')}\n\nItems:\n")
            for it in data['items']:
                f.write(
                    f"- {it.get('item_name')} ({it.get('item_code')}) x {it.get('qty')} {it.get('unit')}\n")
        return True
    except Exception:
        return False
