import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QFormLayout, QHBoxLayout, QGroupBox
)
from PyQt5.QtGui import QPixmap, QIcon
from models.company_model import get_company_profile, save_company_profile


class CompanyProfileWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏢 Company Profile")
        self.setGeometry(300, 150, 800, 500)
        self.setWindowIcon(QIcon("data/logos/rayani_logo.png"))

        self.profile_data = get_company_profile()
        if not self.profile_data:
            # If no profile exists, create a blank one
            save_company_profile("", "", "", "", "", "")
            self.profile_data = get_company_profile()

        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout()

        # Title
        title_label = QLabel("🏢 Company Profile")
        title_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; margin: 10px 0;")
        self.layout.addWidget(title_label)

        # --- Display Section ---
        self.display_widget = QWidget()
        self.display_layout = QFormLayout(self.display_widget)

        self.logo_label = QLabel()
        self.load_logo(self.profile_data[5])

        self.name_display = QLabel(self.profile_data[0])
        self.gst_display = QLabel(self.profile_data[1])
        self.address_display = QLabel(self.profile_data[2])
        self.email_display = QLabel(self.profile_data[3])
        self.phone_display = QLabel(self.profile_data[4])

        self.display_layout.addRow("Company Logo:", self.logo_label)
        self.display_layout.addRow("Company Name:", self.name_display)
        self.display_layout.addRow("GST Number:", self.gst_display)
        self.display_layout.addRow("Address:", self.address_display)
        self.display_layout.addRow("Email:", self.email_display)
        self.display_layout.addRow("Phone Number:", self.phone_display)

        self.layout.addWidget(self.display_widget)

        # --- Edit Section ---
        self.edit_widget = QWidget()
        self.edit_layout = QFormLayout(self.edit_widget)

        self.name_input = QLineEdit(self.profile_data[0])
        self.gst_input = QLineEdit(self.profile_data[1])
        self.address_input = QLineEdit(self.profile_data[2])
        self.email_input = QLineEdit(self.profile_data[3])
        self.phone_input = QLineEdit(self.profile_data[4])
        self.logo_path = self.profile_data[5]

        self.logo_edit_label = QLabel()
        self.load_logo(self.logo_path)
        upload_logo_btn = QPushButton("📁 Upload Logo")
        upload_logo_btn.clicked.connect(self.upload_logo)

        self.edit_layout.addRow("Company Logo:", self.logo_edit_label)
        self.edit_layout.addRow("", upload_logo_btn)
        self.edit_layout.addRow("Company Name:", self.name_input)
        self.edit_layout.addRow("GST Number:", self.gst_input)
        self.edit_layout.addRow("Address:", self.address_input)
        self.edit_layout.addRow("Email:", self.email_input)
        self.edit_layout.addRow("Phone Number:", self.phone_input)

        self.layout.addWidget(self.edit_widget)
        self.edit_widget.setVisible(False)  # Start in view mode

        # --- Buttons ---
        button_layout = QHBoxLayout()
        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self.enable_edit_mode)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_profile)
        self.save_btn.setVisible(False)

        button_layout.addWidget(self.edit_btn)
        button_layout.addWidget(self.save_btn)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def enable_edit_mode(self):
        self.display_widget.setVisible(False)
        self.edit_widget.setVisible(True)
        self.edit_btn.setVisible(False)
        self.save_btn.setVisible(True)

    def load_logo(self, path):
        if path and os.path.exists(path):
            pixmap = QPixmap(path).scaled(150, 150)
            self.logo_label.setPixmap(pixmap)
            if hasattr(self, 'logo_edit_label'):
                self.logo_edit_label.setPixmap(pixmap)
        else:
            placeholder = QPixmap(150, 150)
            placeholder.fill()
            self.logo_label.setPixmap(placeholder)
            if hasattr(self, 'logo_edit_label'):
                self.logo_edit_label.setPixmap(placeholder)

    def upload_logo(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select Company Logo", "", "Image Files (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.logo_path = file_path
            self.load_logo(file_path)

    def save_profile(self):
        try:
            name = self.name_input.text().strip()
            gst = self.gst_input.text().strip()
            address = self.address_input.text().strip()
            email = self.email_input.text().strip()
            phone = self.phone_input.text().strip()
            logo = self.logo_path

            save_company_profile(name, gst, address, email, phone, logo)
            QMessageBox.information(
                self, "Success", "✅ Profile saved successfully!")

            # Update display values
            self.profile_data = (name, gst, address, email, phone, logo)
            self.name_display.setText(name)
            self.gst_display.setText(gst)
            self.address_display.setText(address)
            self.email_display.setText(email)
            self.phone_display.setText(phone)
            self.load_logo(logo)

            self.edit_widget.setVisible(False)
            self.display_widget.setVisible(True)
            self.edit_btn.setVisible(True)
            self.save_btn.setVisible(False)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"❌ Failed to save profile: {e}")
