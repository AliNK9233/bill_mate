from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QFormLayout, QMessageBox, QFileDialog, QGroupBox,
    QGridLayout, QSizePolicy, QSpacerItem
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt
from models.company_model import get_company_profile, save_company_profile, update_logo
import os


class CompanyProfileWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏢 Company Profile")
        self.setWindowIcon(QIcon("data/logos/billmate_logo.png"))
        self.setGeometry(400, 200, 920, 640)

        # state
        self.profile_data = self.fetch_profile_dict()
        self.is_edit_mode = False
        self.pending_logo_path = None  # store selected logo path until Save
        self.inputs = {}
        self.changed_labels = {}  # small "Changed" indicators
        self.original_values = {}  # keep originals to detect changes

        self.setup_ui()
        self.apply_styles()

    def fetch_profile_dict(self):
        row = get_company_profile()
        if not row:
            return {}
        columns = [
            "id", "company_name", "trn_no", "address_line1", "address_line2",
            "city", "state", "country", "phone1", "phone2", "email", "website",
            "bank_name", "account_name", "account_number", "iban", "swift_code", "logo_path"
        ]
        return dict(zip(columns, row))

    def _sync_button_states(self):
        """
        Internal helper: ensure Edit/Save/Logo buttons reflect current edit mode.
        Call after toggling or saving.
        """
        if getattr(self, "is_edit_mode", False):
            self.edit_btn.setText("Cancel")
            self.save_btn.setEnabled(True)
            self.logo_btn.setEnabled(True)
        else:
            self.edit_btn.setText("✏️ Edit")
            self.save_btn.setEnabled(False)
            self.logo_btn.setEnabled(False)

    def setup_ui(self):
        """
        Professional compact Company Profile layout with top toolbar
        (Edit/Save buttons moved to top). Replace existing setup_ui.
        """
        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ---------- Top bar: Title (left) + toolbar (right) ----------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        title = QLabel("🏢 Company Profile")
        title.setObjectName("smallHeader")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title.setMaximumHeight(36)
        top_bar.addWidget(title, 1)

        # toolbar: Edit / Save / Change Logo placed on top-right
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Edit button toggles edit mode
        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setFixedSize(100, 30)
        self.edit_btn.clicked.connect(self.toggle_edit_mode)

        # Save button (disabled until edit mode)
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setFixedSize(100, 30)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_profile)

        # Change logo button (enabled only in edit mode)
        self.logo_btn = QPushButton("🖼️ Change Logo")
        self.logo_btn.setFixedSize(120, 30)
        self.logo_btn.setEnabled(False)
        self.logo_btn.clicked.connect(self.change_logo_preview)

        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.logo_btn)

        # wrap toolbar in widget so it aligns properly on the top row
        tb_widget = QWidget()
        tb_layout = QHBoxLayout(tb_widget)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(8)
        tb_layout.addLayout(toolbar)
        top_bar.addWidget(tb_widget, 0, Qt.AlignRight)

        root.addLayout(top_bar)

        # ---------- Main content: compact card with logo + dense form ----------
        card = QGroupBox()
        card_layout = QHBoxLayout()
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(12)
        card.setLayout(card_layout)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Left: logo (compact)
        logo_v = QVBoxLayout()
        logo_v.setSpacing(6)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(150, 150)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet(
            "border:1px solid #e6eef8; background:#fafcff;")
        self.set_logo(self.profile_data.get("logo_path"))
        logo_v.addWidget(self.logo_label, alignment=Qt.AlignTop)

        note = QLabel("Logo preview (saved when you press Save)")
        note.setStyleSheet("color:#666; font-size:11px;")
        note.setMaximumHeight(16)
        logo_v.addWidget(note, alignment=Qt.AlignTop)

        # small placeholder for logo-changed indicator
        self.logo_changed_label = QLabel("Changed")
        self.logo_changed_label.setStyleSheet(
            "color:#c62828; font-weight:700; font-size:11px;")
        self.logo_changed_label.hide()
        logo_v.addWidget(self.logo_changed_label, alignment=Qt.AlignTop)

        card_layout.addLayout(logo_v, 0)

        # vertical separator
        from PyQt5.QtWidgets import QFrame
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setLineWidth(1)
        card_layout.addWidget(sep)

        # Right: dense form (QFormLayout for tight alignment)
        form_container = QWidget()
        form_outer = QVBoxLayout()
        form_outer.setContentsMargins(0, 0, 0, 0)
        form_outer.setSpacing(6)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)

        fields = [
            ("Company Name", "company_name"),
            ("TRN No.", "trn_no"),
            ("Address Line 1", "address_line1"),
            ("Address Line 2", "address_line2"),
            ("City", "city"),
            ("State", "state"),
            ("Country", "country"),
            ("Phone 1", "phone1"),
            ("Phone 2", "phone2"),
            ("Email", "email"),
            ("Website", "website"),
            ("Bank Name", "bank_name"),
            ("Account Holder", "account_name"),
            ("Account Number", "account_number"),
            ("IBAN", "iban"),
            ("SWIFT Code", "swift_code"),
        ]

        # prepare originals
        for _, k in fields:
            self.original_values[k] = str(self.profile_data.get(k, "") or "")

        for label_text, key in fields:
            lbl = QLabel(label_text + ":")
            lbl.setMinimumWidth(110)
            lbl.setFixedHeight(20)
            lbl.setStyleSheet("font-size:13px;")

            if key == "company_name":
                widget = QLineEdit(self.original_values[key])
                widget.setReadOnly(True)
                widget.setStyleSheet("background:#f6f7f9;")
            else:
                widget = QLineEdit(self.original_values[key])
                widget.setReadOnly(True)
                widget.textChanged.connect(
                    lambda txt, k=key: self.on_field_changed(k, txt))

            widget.setMinimumWidth(340)
            widget.setMaximumHeight(26)
            self.inputs[key] = widget

            # inline changed indicator (subtle)
            changed = QLabel("Changed")
            changed.setStyleSheet(
                "color:#c62828; font-weight:700; font-size:11px;")
            changed.hide()
            self.changed_labels[key] = changed

            # pack field + indicator inline
            hwrap = QHBoxLayout()
            hwrap.setContentsMargins(0, 0, 0, 0)
            hwrap.setSpacing(8)
            hwrap.addWidget(widget)
            hwrap.addWidget(changed)

            cont = QWidget()
            cont.setLayout(hwrap)

            form.addRow(lbl, cont)

        form_outer.addLayout(form)
        form_container.setLayout(form_outer)
        card_layout.addWidget(form_container, 1)

        root.addWidget(card)

        # ---------- Footer hint (very compact) ----------
        footer = QLabel(
            "Fields marked 'Changed' will be saved. Company Name is read-only.")
        footer.setStyleSheet("color:#666; font-size:11px;")
        footer.setMaximumHeight(18)
        root.addWidget(footer)

        # finalize
        self.setLayout(root)

        # ensure buttons states reflect current edit_mode
        self._sync_button_states()

    def apply_styles(self):
        """
        Compact professional styling that cooperates with external theme.
        Replace existing apply_styles.
        """
        self.setStyleSheet("""
            /* Card + form look */
            QWidget { background: #ffffff; color: #222; font-size:14px; }
            QGroupBox { border: 1px solid #e9f3fb; border-radius:6px; padding:8px; background:#ffffff; }
            QLabel#smallHeader { font-size:18px; font-weight:700; color:#16324a; }
            QLabel { font-size:13px; }
            QLineEdit { padding:6px 8px; border:1px solid #e6eff9; border-radius:4px; font-size:13px; }
            QLineEdit:read-only { background:#f6f7f9; color:#333; }
            QPushButton { background:#1f77b4; color:#fff; border-radius:6px; padding:6px; font-size:13px; }
            QPushButton:disabled { background:#cfe4f6; color:#f4f9ff; }
        """)

    def set_logo(self, logo_path):
        """Set the displayed logo (safe handling)."""
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                self.logo_label.width(), self.logo_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("No Logo")
            self.logo_label.setFont(QFont("Segoe UI", 10, QFont.Bold))

    # ---- Edit / Cancel ----
    def toggle_edit_mode(self):
        """Enter or exit edit mode. Cancel reverts changes."""
        entering = not self.is_edit_mode
        self.is_edit_mode = entering

        # enable/disable fields - company_name always read-only
        for key, widget in self.inputs.items():
            if key == "company_name":
                widget.setReadOnly(True)
            else:
                widget.setReadOnly(not entering)

        # buttons
        self.logo_btn.setEnabled(entering)
        self.save_btn.setEnabled(entering)
        self.edit_btn.setText("Cancel" if entering else "✏️ Edit")

        if not entering:
            # Cancel: revert to DB values and clear changed indicators & pending logo
            self.profile_data = self.fetch_profile_dict()
            for k, w in self.inputs.items():
                w.setText(str(self.profile_data.get(k, "") or ""))
                self.changed_labels[k].hide()
            self.pending_logo_path = None
            self.logo_changed_label.hide()
            self.set_logo(self.profile_data.get("logo_path"))

    # ---- Field change tracking ----
    def on_field_changed(self, key, new_text):
        """
        Mark field as changed if its text differs from the original value.
        Only show indicator when in edit mode.
        """
        if not self.is_edit_mode:
            # ignore modifications when read-only
            return

        orig = str(self.original_values.get(key, "") or "")
        if new_text.strip() != orig:
            self.changed_labels[key].show()
        else:
            self.changed_labels[key].hide()

    # ---- Logo selection: only preview, not saved until Save pressed ----
    def change_logo_preview(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not file_path:
            return

        # Update preview immediately
        try:
            pixmap = QPixmap(file_path).scaled(
                self.logo_label.width(), self.logo_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
            self.pending_logo_path = file_path
            self.logo_changed_label.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load logo: {e}")

    # ---- Save all changes ----
    def save_profile(self):
        # gather only changed values (and also include company_name to keep DB consistent)
        data = {}
        for key, widget in self.inputs.items():
            # company_name will always be saved from the DB/display but not edited
            val = widget.text().strip()
            # add if changed OR company_name (to ensure row completeness)
            if key == "company_name" or self.changed_labels[key].isVisible():
                data[key] = val

        if not data and not self.pending_logo_path:
            QMessageBox.information(self, "No Changes", "No changes to save.")
            return

        # persist textual fields
        try:
            save_company_profile(data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save profile: {e}")
            return

        # persist logo only after textual save succeeds
        if self.pending_logo_path:
            try:
                update_logo(self.pending_logo_path)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to update logo: {e}")
                # do not return — textual fields already saved
            self.pending_logo_path = None

        QMessageBox.information(
            self, "Success", "Company profile saved successfully ✅")

        # exit edit mode and reset indicators
        self.is_edit_mode = False
        for key, widget in self.inputs.items():
            widget.setReadOnly(True)
            self.changed_labels[key].hide()

        self.logo_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.edit_btn.setText("✏️ Edit")
        self.logo_changed_label.hide()

        # refresh in-memory profile and logo from DB (ensure consistency)
        self.profile_data = self.fetch_profile_dict()
        self.set_logo(self.profile_data.get("logo_path"))
        # refresh original_values snapshot
        for k in self.original_values.keys():
            self.original_values[k] = str(self.profile_data.get(k, "") or "")
