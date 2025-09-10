# ui/user_management_window.py
"""
Admin-only User Management window for your PyQt app.

Save this file as `ui/user_management_window.py`.

Features:
- List users from the users table
- Create user (username, password, role)
- Change role
- Delete user
- Enable / Disable user (uses `set_user_active` from models.user_auth)
- set_admin_mode(enabled) to enable/disable admin controls from MainWindow

This expects the following functions in models.user_auth:
- get_all_users(db_path=...)
- create_user(username, password, role, created_by, db_path=...)
- update_user_role(user_id, new_role, db_path=...)
- delete_user(user_id, db_path=...)
- set_user_active(user_id, active_int, db_path=...)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import Qt

# Import the user management helpers (from the latest models/user_auth.py)
from models.user_auth import (
    get_all_users, create_user, update_user_role, delete_user, set_user_active
)


class CreateUserSimpleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.resize(360, 180)
        self.layout = QFormLayout(self)

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        self.role = QComboBox()
        self.role.addItems(["user", "admin"])

        self.layout.addRow("Username:", self.username)
        self.layout.addRow("Password:", self.password)
        self.layout.addRow("Confirm:", self.confirm)
        self.layout.addRow("Role:", self.role)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

    def _on_accept(self):
        if not self.username.text().strip():
            QMessageBox.warning(self, "Validation", "Username cannot be empty")
            return
        if self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Validation", "Passwords do not match")
            return
        if len(self.password.text()) < 4:
            QMessageBox.warning(self, "Validation",
                                "Password must be at least 4 characters")
            return
        self.accept()

    def get_values(self):
        return self.username.text().strip(), self.password.text(), self.role.currentText()


class UserManagementWindow(QWidget):
    def __init__(self, parent=None, db_path="data/database.db"):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("User Management")
        self.layout = QVBoxLayout(self)

        # Table with 6 columns
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Username", "Role", "Active", "Created By", "Created At"])
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setEditTriggers(self.table.NoEditTriggers)
        self.layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Create User")
        self.btn_edit_role = QPushButton("Change Role")
        self.btn_toggle_active = QPushButton("Enable/Disable")
        self.btn_delete = QPushButton("Delete User")
        self.btn_refresh = QPushButton("Refresh")

        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_edit_role)
        btn_layout.addWidget(self.btn_toggle_active)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        self.layout.addLayout(btn_layout)

        # Signals
        self.btn_create.clicked.connect(self.on_create)
        self.btn_edit_role.clicked.connect(self.on_change_role)
        self.btn_toggle_active.clicked.connect(self.on_toggle_active)
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_refresh.clicked.connect(self.load_users)

        # Start with admin controls disabled (MainWindow will call set_admin_mode)
        self.set_admin_mode(False)

        self.load_users()

    def load_users(self):
        try:
            users = get_all_users(db_path=self.db_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load users:\n{e}")
            return

        self.table.setRowCount(0)
        for u in users:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(u.get("id"))))
            self.table.setItem(r, 1, QTableWidgetItem(u.get("username")))
            self.table.setItem(r, 2, QTableWidgetItem(u.get("role")))
            # Active column
            active_val = u.get("is_active")
            if active_val is None:
                active_text = "Unknown"
            else:
                active_text = "Yes" if int(active_val) == 1 else "No"
            self.table.setItem(r, 3, QTableWidgetItem(active_text))
            self.table.setItem(r, 4, QTableWidgetItem(
                u.get("created_by") or ""))
            self.table.setItem(r, 5, QTableWidgetItem(
                u.get("created_at") or ""))

    def selected_user(self):
        sel = self.table.currentRow()
        if sel == -1:
            return None
        try:
            user_id = int(self.table.item(sel, 0).text())
        except Exception:
            return None
        username = self.table.item(sel, 1).text()
        role = self.table.item(sel, 2).text()
        active_text = self.table.item(sel, 3).text()
        active = None
        if active_text == "Yes":
            active = True
        elif active_text == "No":
            active = False
        return {"id": user_id, "username": username, "role": role, "active": active}

    def on_create(self):
        dlg = CreateUserSimpleDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            username, password, role = dlg.get_values()
            try:
                create_user(username, password, role=role,
                            created_by="admin", db_path=self.db_path)
                QMessageBox.information(
                    self, "Created", f"User '{username}' created.")
                self.load_users()
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to create user:\n{e}")

    def on_change_role(self):
        sel = self.selected_user()
        if not sel:
            QMessageBox.warning(self, "Select", "Select a user first.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Change role for {sel['username']}")
        layout = QFormLayout(dlg)
        role_cb = QComboBox()
        role_cb.addItems(["user", "admin"])
        role_cb.setCurrentText(sel["role"])
        layout.addRow("Role:", role_cb)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            try:
                update_user_role(
                    sel["id"], role_cb.currentText(), db_path=self.db_path)
                QMessageBox.information(self, "Updated", "Role updated.")
                self.load_users()
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to update role:\n{e}")

    def on_toggle_active(self):
        sel = self.selected_user()
        if not sel:
            QMessageBox.warning(self, "Select", "Select a user first.")
            return
        # If active is None, database doesn't have is_active info
        if sel["active"] is None:
            QMessageBox.information(self, "Unavailable",
                                    "Active/Disabled information is not available for this database.\n"
                                    "Please ensure the users table has an 'is_active' column and that models.user_auth.set_user_active exists.")
            return
        new_state = not sel["active"]
        try:
            set_user_active(sel["id"], 1 if new_state else 0,
                            db_path=self.db_path)
            QMessageBox.information(
                self, "Updated", f"User {'enabled' if new_state else 'disabled'}.")
            self.load_users()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to change active state:\n{e}")

    def on_delete(self):
        sel = self.selected_user()
        if not sel:
            QMessageBox.warning(self, "Select", "Select a user first.")
            return
        if sel["username"].lower() == "admin":
            reply = QMessageBox.question(
                self, "Confirm", "Are you sure you want to delete this admin?", QMessageBox.Yes | QMessageBox.No)
        else:
            reply = QMessageBox.question(
                self, "Confirm", f"Delete user {sel['username']}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                delete_user(sel["id"], db_path=self.db_path)
                QMessageBox.information(self, "Deleted", "User deleted.")
                self.load_users()
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to delete user:\n{e}")

    def set_admin_mode(self, enabled: bool):
        """Enable/disable admin-only controls inside this widget."""
        self.btn_create.setDisabled(not enabled)
        self.btn_edit_role.setDisabled(not enabled)
        self.btn_toggle_active.setDisabled(not enabled)
        self.btn_delete.setDisabled(not enabled)
        # Optionally disable the table when not admin
        self.table.setDisabled(not enabled)
