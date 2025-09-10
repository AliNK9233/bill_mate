# models/user_auth.py
"""
User authentication and management helpers.

Save as models/user_auth.py and import functions from other modules:
- init_user_db(db_path=...)
- create_user(username, password, role='user', created_by=None, db_path=...)
- authenticate_user(username, password, db_path=...) -> user dict or None
- get_all_users(db_path=...)
- update_user_role(user_id, new_role, db_path=...)
- delete_user(user_id, db_path=...)
- set_user_active(user_id, active_int, db_path=...)
- get_user_count(role=None, db_path=...)
- create_admin_if_missing(interactive_parent=None, db_path=...)

Notes:
- Dialogs use PyQt classes, so importing these dialogs brings PyQt into the importing module.
- This module intentionally does NOT import ui.main_window to avoid circular imports.
"""

import os
import sqlite3
import hashlib
import binascii
from datetime import datetime

# PyQt dialogs (safe to import; don't import ui modules here)
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox, QLabel
)
from PyQt5.QtCore import Qt

# Default DB path (use your app DB)
DB_PATH = os.path.join("data", "database.db")


# ----------------- Utilities -----------------

def _ensure_db_folder(db_path=DB_PATH):
    folder = os.path.dirname(db_path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


# ----------------- DB Init / Migration -----------------

def init_user_db(db_path=DB_PATH):
    """
    Initialize the users table if not exists and ensure is_active column exists.
    """
    _ensure_db_folder(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    # Future-safe: ensure column exists (no-op if created above)
    ensure_is_active_column(db_path=db_path)


def ensure_is_active_column(db_path=DB_PATH):
    """
    Ensure the users table has an is_active column. If missing, ALTER TABLE to add it.
    Safe to call repeatedly.
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if "is_active" not in cols:
            cur.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            conn.commit()


# ----------------- Password hashing -----------------

def _hash_password(password: str, salt: bytes = None):
    """
    Return (password_hash_hex, salt_hex). Uses PBKDF2-HMAC-SHA256.
    """
    if salt is None:
        salt = os.urandom(16)
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, 100_000)
    return binascii.hexlify(dk).decode("ascii"), binascii.hexlify(salt).decode("ascii")


# ----------------- Core CRUD -----------------

def create_user(username: str, password: str, role: str = "user", created_by: str = None, db_path=DB_PATH):
    """
    Create a user. Raises sqlite3.IntegrityError if username exists.
    Returns True on success.
    """
    if not username or not password:
        raise ValueError("username and password required")
    pw_hash, salt = _hash_password(password)
    created_at = datetime.utcnow().isoformat()
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, salt, role, is_active, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
            (username, pw_hash, salt, role, 1, created_by, created_at),
        )
        conn.commit()
    return True


def authenticate_user(username: str, password: str, db_path=DB_PATH):
    """
    Return user dict if username/password correct AND is_active==1, else None.
    user dict: {id, username, role, created_by, created_at, is_active}
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash, salt, role, is_active, created_by, created_at FROM users WHERE username=?",
                    (username,))
        row = cur.fetchone()
        if not row:
            return None
        _id, uname, stored_hash, stored_salt, role, is_active, created_by, created_at = row
        salt = binascii.unhexlify(stored_salt)
        candidate_hash, _ = _hash_password(password, salt)
        if candidate_hash == stored_hash:
            # check active flag
            try:
                active = int(is_active) == 1
            except Exception:
                active = True
            if not active:
                # account disabled
                return None
            return {
                "id": _id,
                "username": uname,
                "role": role,
                "created_by": created_by,
                "created_at": created_at,
                "is_active": active,
            }
    return None


def get_user_count(role: str = None, db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        if role:
            cur.execute("SELECT COUNT(1) FROM users WHERE role=?", (role,))
        else:
            cur.execute("SELECT COUNT(1) FROM users")
        return cur.fetchone()[0]


def get_all_users(db_path=DB_PATH):
    """
    Return list of user dicts with id, username, role, is_active, created_by, created_at
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, role, is_active, created_by, created_at FROM users ORDER BY id")
        rows = cur.fetchall()
        users = []
        for r in rows:
            users.append({
                "id": r[0],
                "username": r[1],
                "role": r[2],
                "is_active": r[3],
                "created_by": r[4],
                "created_at": r[5],
            })
        return users


def update_user_role(user_id: int, new_role: str, db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
        conn.commit()
        return cur.rowcount


def delete_user(user_id: int, db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        return cur.rowcount


def set_user_active(user_id: int, active: int, db_path=DB_PATH):
    """
    Set is_active to 1 or 0. active must be integer 0 or 1.
    Returns number of rows updated.
    """
    if active not in (0, 1):
        raise ValueError("active must be 0 or 1")
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_active=? WHERE id=?",
                    (active, user_id))
        conn.commit()
        return cur.rowcount


# ----------------- Dialogs / Interactive helpers -----------------

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(340, 120)

        self.layout = QFormLayout(self)
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        self.layout.addRow("Username:", self.username)
        self.layout.addRow("Password:", self.password)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def get_credentials(self):
        return self.username.text().strip(), self.password.text()


class CreateUserDialog(QDialog):
    """
    Simple dialog to create a user (used for initial admin creation).
    """

    def __init__(self, require_admin=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.resize(360, 160)
        self.layout = QFormLayout(self)

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)

        self.role_label = QLabel("Role: admin (initial setup)") if require_admin else QLabel(
            "Role: (will be chosen programmatically)")

        self.layout.addRow("Username:", self.username)
        self.layout.addRow("Password:", self.password)
        self.layout.addRow("Confirm:", self.confirm)
        self.layout.addRow(self.role_label)

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
        return self.username.text().strip(), self.password.text()


def create_admin_if_missing(interactive_parent=None, db_path=DB_PATH):
    """
    If no admin user exists, prompt (interactive) to create an initial admin.
    Returns True if admin exists or was created, False if creation cancelled/failed.
    """
    init_user_db(db_path=db_path)
    if get_user_count(role="admin", db_path=db_path) == 0:
        dlg = CreateUserDialog(require_admin=True, parent=interactive_parent)
        if dlg.exec_() == QDialog.Accepted:
            username, password = dlg.get_values()
            try:
                create_user(username, password, role="admin",
                            created_by=username, db_path=db_path)
                QMessageBox.information(
                    interactive_parent or dlg, "Admin Created", "✅ Initial admin account created.")
                return True
            except Exception as e:
                QMessageBox.critical(
                    interactive_parent or dlg, "Error Creating Admin", f"{e}")
                return False
        else:
            return False
    return True


# ----------------- end of file -----------------
