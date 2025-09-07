# ui/invoice_pdf_viewer.py

import os
import shutil
import subprocess
import platform
from datetime import datetime
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
    QFileDialog, QLabel, QSizePolicy
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QIcon, QDesktopServices

# Try to import QWebEngineView (for embedding PDF)
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except Exception:
    WEB_ENGINE_AVAILABLE = False

# local helpers / models (adjust import paths if needed)
from utils.pdf_helper import generate_invoice_pdf
from models.invoice_model import fetch_invoice
from models.company_model import get_company_profile


OUT_DIR = os.path.join("data", "invoices")
os.makedirs(OUT_DIR, exist_ok=True)


class InvoicePdfViewer(QWidget):
    """
    A window to generate & view invoice PDF, with Save / Print / Mail / WhatsApp actions.

    Usage:
        w = InvoicePdfViewer("RAD-0001")
        w.show()
    """

    def __init__(self, invoice_no: str, parent=None):
        super().__init__(parent)
        self.invoice_no = invoice_no
        self.setWindowTitle(f"Invoice Viewer — {invoice_no}")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png")
                           if os.path.exists("data/logos/billmate_logo.png") else QIcon())
        self.setMinimumSize(900, 700)

        self.current_pdf_path = None

        self._build_ui()
        self.load_and_show_invoice()

    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # toolbar (top)
        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_save = QPushButton("💾 Save As...")
        self.btn_print = QPushButton("🖨️ Print")
        self.btn_mail = QPushButton("✉️ Mail")
        self.btn_whatsapp = QPushButton("🟩 WhatsApp")
        self.btn_open = QPushButton("Open PDF")

        self.btn_refresh.clicked.connect(self.on_refresh)
        self.btn_save.clicked.connect(self.on_save_as)
        self.btn_print.clicked.connect(self.on_print)
        self.btn_mail.clicked.connect(self.on_mail)
        self.btn_whatsapp.clicked.connect(self.on_whatsapp)
        self.btn_open.clicked.connect(self.on_open_file)

        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.btn_print)
        toolbar.addWidget(self.btn_mail)
        toolbar.addWidget(self.btn_whatsapp)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_open)
        root.addLayout(toolbar)

        # Viewer area
        if WEB_ENGINE_AVAILABLE:
            self.viewer = QWebEngineView()
            # allow the embedded viewer to expand
            self.viewer.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            root.addWidget(self.viewer, stretch=1)
        else:
            # fallback message
            fallback_layout = QVBoxLayout()
            lbl = QLabel(
                "PDF viewer not available in this environment.\nUse 'Open PDF' to open in the system viewer.")
            lbl.setAlignment(Qt.AlignCenter)
            fallback_layout.addWidget(lbl, stretch=1)
            root.addLayout(fallback_layout)

        # bottom status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #444; font-size: 12px;")
        root.addWidget(self.status_label)

        self.setLayout(root)

    def _collect_invoice_data(self):
        """
        Fetch invoice header and items from models and convert to pdf_helper format.
        """
        header_row, items_rows = fetch_invoice(self.invoice_no)
        if not header_row:
            raise ValueError(f"Invoice not found: {self.invoice_no}")

        # header_row is the raw sqlite row — map by index (safe if schema known)
        # In our invoice model header tuple structure (see models/invoice_model):
        # (id, invoice_no, invoice_date, customer_id, bill_to, ship_to, lpo_no,
        #  discount, total_amount, vat_amount, net_total, created_at, updated_at, balance, paid_amount, remarks, status, salesman_id)
        # We'll map to dict for helper
        hdr = {}
        # defensive mapping (only if positions exist)
        # prefer named fields if model returns dicts in future
        try:
            hdr['invoice_no'] = header_row[1]
            # invoice_date might be iso string -> convert to readable
            try:
                dt = datetime.fromisoformat(header_row[2])
                hdr['invoice_date'] = dt.strftime("%d-%m-%Y %H:%M")
            except Exception:
                hdr['invoice_date'] = str(header_row[2])
            hdr['bill_to'] = header_row[4] or ""
            hdr['ship_to'] = header_row[5] or ""
            hdr['lpo_no'] = header_row[6] or ""
            hdr['discount'] = float(header_row[7] or 0.0)
            hdr['total_amount'] = float(header_row[8] or 0.0)
            hdr['vat_amount'] = float(header_row[9] or 0.0)
            hdr['net_total'] = float(header_row[10] or 0.0)
            hdr['paid_amount'] = float(header_row[14] or 0.0) if len(
                header_row) > 14 else 0.0
            hdr['balance'] = float(header_row[13] or hdr['net_total']) if len(
                header_row) > 13 else hdr['net_total']
            hdr['remarks'] = header_row[15] if len(header_row) > 15 else ""
            hdr['status'] = header_row[16] if len(header_row) > 16 else ""
        except Exception:
            # fallback to minimal header
            hdr = {
                "invoice_no": self.invoice_no,
                "invoice_date": "",
                "bill_to": "",
                "ship_to": "",
                "discount": 0.0,
                "total_amount": 0.0,
                "vat_amount": 0.0,
                "net_total": 0.0,
                "paid_amount": 0.0,
                "balance": 0.0,
                "remarks": ""
            }

        # items_rows is a list of tuples as returned by fetch_invoice
        items = []
        for it in items_rows:
            # item tuple shape: (serial_no, item_code, item_name, uom, per_box_qty, quantity, rate, sub_total, vat_percentage, vat_amount, net_amount)
            item_d = {
                "serial_no": it[0],
                "item_code": it[1],
                "item_name": it[2],
                "uom": it[3] or "",
                "per_box_qty": it[4] or 1,
                "quantity": float(it[5] or 0),
                "rate": float(it[6] or 0),
                "vat_percentage": float(it[8] or 0),
                # "discount" not stored per-line in this schema; default 0
                "discount": 0.0,
                "free": float(it[6] or 0) == 0.0  # treat zero-rate as FOC
            }
            items.append(item_d)

        return hdr, items

    def load_and_show_invoice(self):
        """
        Generate PDF using helper and show inside embedded viewer (if available)
        """
        try:
            self.status_label.setText("Generating PDF...")
            QApplication_process_events = None
        except Exception:
            pass

        try:
            company = get_company_profile() or {}
        except Exception:
            company = {}

        # collect data
        try:
            header, items = self._collect_invoice_data()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load invoice data: {e}")
            return

        # convert company profile dict to a shape expected by pdf_helper
        company_profile = {
            "company_name": company.get("company_name") if isinstance(company, dict) else (company[1] if len(company) > 1 else "Company"),
            "trn_no": company.get("trn_no") if isinstance(company, dict) else "",
            "address": " ".join(filter(None, [company.get("address_line1", ""), company.get("address_line2", "")])) if isinstance(company, dict) else "",
            "phone1": company.get("phone1") if isinstance(company, dict) else "",
            "email": company.get("email") if isinstance(company, dict) else "",
            "website": company.get("website") if isinstance(company, dict) else "",
            "bank_details": " ".join(filter(None, [
                company.get("bank_name", ""), company.get("account_name", ""), company.get(
                    "account_number", ""), company.get("iban", ""), company.get("swift_code", "")
            ])) if isinstance(company, dict) else "",
            "logo_path": company.get("logo_path") if isinstance(company, dict) else company.get("logo_path") if isinstance(company, dict) else ""
        }

        # generate PDF file
        safe_no = "".join(ch for ch in str(header.get(
            "invoice_no", self.invoice_no)) if ch.isalnum() or ch in "-_")
        out_filename = os.path.join(OUT_DIR, f"{safe_no}.pdf")

        try:
            pdf_path = generate_invoice_pdf(
                header, items, company_profile=company_profile, filename=out_filename)
            self.current_pdf_path = pdf_path
            self.status_label.setText(
                f"PDF generated: {os.path.abspath(pdf_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {e}")
            return

        # display in viewer (or provide open button)
        if WEB_ENGINE_AVAILABLE:
            # load local file via file:// URL
            url = QUrl.fromLocalFile(os.path.abspath(self.current_pdf_path))
            self.viewer.load(url)
        else:
            # fallback - let user open it manually
            pass

    # ---- Actions ----
    def on_refresh(self):
        self.load_and_show_invoice()
        QMessageBox.information(self, "Refreshed", "Invoice PDF refreshed.")

    def on_open_file(self):
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            QMessageBox.warning(self, "No PDF", "PDF not found. Try Refresh.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(
            os.path.abspath(self.current_pdf_path)))

    def on_save_as(self):
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            QMessageBox.warning(self, "No PDF", "PDF not found. Try Refresh.")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save Invoice As", os.path.basename(
            self.current_pdf_path), "PDF Files (*.pdf)")
        if not dest:
            return
        try:
            shutil.copy(self.current_pdf_path, dest)
            QMessageBox.information(self, "Saved", f"Saved PDF to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save PDF: {e}")

    def on_print(self):
        """
        Try platform printing:
         - Windows: os.startfile(path, "print")
         - Linux/macOS: try lp
        """
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            QMessageBox.warning(self, "No PDF", "PDF not found. Try Refresh.")
            return

        try:
            sys_plat = platform.system()
            if sys_plat == "Windows":
                # this will send to default printer
                os.startfile(self.current_pdf_path, "print")
                QMessageBox.information(
                    self, "Print", "Sent to default printer (Windows).")
                return
            else:
                # try 'lp' command (common on Linux / macOS)
                proc = subprocess.run(["lp", os.path.abspath(
                    self.current_pdf_path)], capture_output=True, text=True)
                if proc.returncode == 0:
                    QMessageBox.information(
                        self, "Print", "Sent to printer (via lp).")
                    return
                # fallback: open in system viewer
                QDesktopServices.openUrl(QUrl.fromLocalFile(
                    os.path.abspath(self.current_pdf_path)))
                QMessageBox.information(
                    self, "Print", "Opened PDF in system viewer. Use the viewer's Print option.")
        except FileNotFoundError:
            QMessageBox.warning(self, "Print Not Available",
                                "Printing command not found on this system. The PDF has been opened in the system viewer.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(
                os.path.abspath(self.current_pdf_path)))
        except Exception as e:
            QMessageBox.critical(self, "Print Error", f"Failed to print: {e}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(
                os.path.abspath(self.current_pdf_path)))

    def on_mail(self):
        """
        Open default mail client with a prefilled subject/body. 
        Attachments via mailto: are unsupported; user must attach file manually.
        """
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            QMessageBox.warning(self, "No PDF", "PDF not found. Try Refresh.")
            return

        subject = f"Invoice {self.invoice_no}"
        body = f"Please find attached invoice {self.invoice_no}.\n\nInvoice file: {os.path.abspath(self.current_pdf_path)}"
        mailto = QUrl(
            f"mailto:?subject={QUrl.toPercentEncoding(subject).data().decode() if hasattr(QUrl, 'toPercentEncoding') else subject}&body={QUrl.toPercentEncoding(body).data().decode() if hasattr(QUrl, 'toPercentEncoding') else body}")
        # QDesktopServices will open the default mail client
        QDesktopServices.openUrl(mailto)
        QMessageBox.information(
            self, "Mail", f"Mail client opened. Please attach the file manually:\n{os.path.abspath(self.current_pdf_path)}")

    def on_whatsapp(self):
        """
        Open WhatsApp Web with a prefilled message. User must attach PDF manually.
        """
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            QMessageBox.warning(self, "No PDF", "PDF not found. Try Refresh.")
            return

        text = f"Please find invoice {self.invoice_no}. File: {os.path.abspath(self.current_pdf_path)}"
        url_text = QUrl(
            f"https://web.whatsapp.com/send?text={QUrl.toPercentEncoding(text).data().decode() if hasattr(QUrl, 'toPercentEncoding') else text}")
        QDesktopServices.openUrl(url_text)
        QMessageBox.information(
            self, "WhatsApp", "WhatsApp Web opened. Attach the invoice file manually in the chat.")

    def closeEvent(self, event):
        # optionally keep or remove the generated file; we keep it for record.
        event.accept()
