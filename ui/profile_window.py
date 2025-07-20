from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QFormLayout, QMessageBox, QFrame
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt
from models.company_model import get_company_profile, save_company_profile
import os


class CompanyProfileWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏢 Company Profile")
        self.setGeometry(400, 200, 700, 600)
        self.profile_data = get_company_profile()
        self.is_edit_mode = False
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()

        # 🌟 SAP-inspired header
        header = QLabel("🏢 Company Profile")
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "background-color: #F3F4F6; padding: 12px; border-radius: 8px; color: #0A3D62;")
        main_layout.addWidget(header)

        # --- Company Logo (Fixed)
        self.logo_display = QLabel()
        self.logo_display.setFixedSize(150, 150)
        self.logo_display.setAlignment(Qt.AlignCenter)
        self.logo_display.setStyleSheet(
            "border: 1px solid #ccc; background: #f8f9fa;")
        main_layout.addWidget(self.logo_display)
        self.load_logo()

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)

        # Form for Profile Details
        self.form_layout = QFormLayout()
        self.fields = {}

        # Company Name (Non-editable)
        name_label = QLabel(self.profile_data["name"])
        name_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        name_label.setStyleSheet("color: #0078D7;")
        self.form_layout.addRow("🏢 Company Name:", name_label)

        # Other editable fields
        for field, label in [
            ("gst_no", "GST No"), ("address", "Address"),
            ("phone1", "Phone 1"), ("phone2", "Phone 2"),
            ("email", "Email"), ("website", "Website"),
            ("bank_name", "Bank Name"), ("bank_account", "Account No"),
            ("ifsc_code", "IFSC Code"), ("branch_address", "Branch Address")
        ]:
            line_edit = QLineEdit(self.profile_data.get(field, ""))
            line_edit.setReadOnly(True)  # Start in view mode
            line_edit.setStyleSheet("background-color: #F3F4F6; padding: 4px;")
            self.fields[field] = line_edit
            self.form_layout.addRow(f"{label}:", line_edit)

        main_layout.addLayout(self.form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setStyleSheet(
            "background-color: #0078D7; color: white; border-radius: 5px; padding: 6px 12px;")
        self.edit_btn.clicked.connect(self.toggle_edit_mode)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(
            "background-color: #28A745; color: white; border-radius: 5px; padding: 6px 12px;")
        self.save_btn.clicked.connect(self.save_profile)
        self.save_btn.hide()  # Hidden until edit mode

        button_layout.addWidget(self.edit_btn)
        button_layout.addWidget(self.save_btn)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def load_logo(self):
        """
        Load company logo from fixed path.
        """
        logo_path = os.path.join("data", "logos", "billmate_logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_display.setPixmap(pixmap)
        else:
            self.logo_display.setText("📄 No Logo Available")
            self.logo_display.setStyleSheet(
                "color: #6C757D; font-style: italic;")

    def toggle_edit_mode(self):
        """
        Toggle between view and edit mode for profile fields.
        """
        if not self.is_edit_mode:
            self.edit_btn.setText("🚫 Cancel")
            self.save_btn.show()
            for field_widget in self.fields.values():
                field_widget.setReadOnly(False)
                field_widget.setStyleSheet(
                    "background-color: #FFFFFF; border: 1px solid #CED4DA; padding: 4px;")
        else:
            self.edit_btn.setText("✏️ Edit")
            self.save_btn.hide()
            for field_widget in self.fields.values():
                field_widget.setReadOnly(True)
                field_widget.setStyleSheet(
                    "background-color: #F3F4F6; padding: 4px;")
            self.load_profile_data()
        self.is_edit_mode = not self.is_edit_mode

    def save_profile(self):
        """
        Save profile data to DB.
        """
        for field, widget in self.fields.items():
            self.profile_data[field] = widget.text()
        save_company_profile(self.profile_data)
        QMessageBox.information(
            self, "✅ Success", "Company profile updated successfully.")
        self.toggle_edit_mode()
        self.load_profile_data()

    def load_profile_data(self):
        """
        Reload profile data to discard unsaved changes.
        """
        self.profile_data = get_company_profile()
        for field, widget in self.fields.items():
            widget.setText(self.profile_data.get(field, ""))
