from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox


class AdminLogin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔑 Admin Login")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        label = QLabel("Enter Admin Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.check_password)

        layout.addWidget(label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

        self.setLayout(layout)
        self.authenticated = False

    def check_password(self):
        if self.password_input.text() == "0000":
            self.authenticated = True
            self.accept()
        else:
            QMessageBox.warning(self, "Access Denied", "❌ Incorrect password.")
