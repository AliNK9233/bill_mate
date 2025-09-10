# ui/welcome_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QFrame, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal
import os


class WelcomeWindow(QWidget):
    """
    Simple welcome/splash window for the app.
    Emits signals when user chooses to continue or selects a quick action.
    """
    # emitted when user presses Start. Payload: chosen starting_tab (str)
    startRequested = pyqtSignal(str)
    # emitted when user clicks a quick action from the list. Payload: action_key (str)
    quickActionRequested = pyqtSignal(str)

    def __init__(self, parent=None, app_name="BillMate", version="v1.0.0", logo_path="data/logos/billmate_logo.png", tagline="Simple invoicing & stock"):
        super().__init__(parent)
        self.app_name = app_name
        self.version = version
        self.logo_path = logo_path
        self.tagline = tagline

        self.setWindowTitle(f"{self.app_name} — Welcome")
        # small default geometry — caller can resize or use in a main window layout
        self.setFixedSize(720, 420)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        self.setLayout(root)

        # Top area: logo + name
        top = QHBoxLayout()
        top.setSpacing(12)

        logo_lbl = QLabel()
        logo_lbl.setFixedSize(120, 120)
        logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if os.path.exists(self.logo_path):
            try:
                pix = QPixmap(self.logo_path).scaled(
                    120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_lbl.setPixmap(pix)
            except Exception:
                logo_lbl.setText("")  # fallback: leave blank
        else:
            # placeholder box with app initials
            logo_lbl.setStyleSheet(
                "background:#efefef;border:1px solid #ddd;border-radius:10px;color:#444;")
            logo_lbl.setAlignment(Qt.AlignCenter)
            initials = "".join([p[0]
                               for p in self.app_name.split()[:2]]).upper()
            logo_lbl.setText(initials)
            logo_lbl.setFont(QFont("Segoe UI", 32, QFont.Bold))

        top.addWidget(logo_lbl, alignment=Qt.AlignLeft | Qt.AlignVCenter)

        meta = QVBoxLayout()
        name_lbl = QLabel(self.app_name)
        name_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        meta.addWidget(name_lbl)

        ver_lbl = QLabel(self.version)
        ver_lbl.setFont(QFont("Segoe UI", 9))
        ver_lbl.setStyleSheet("color: #666;")
        meta.addWidget(ver_lbl)

        desc_lbl = QLabel(self.tagline)
        desc_lbl.setFont(QFont("Segoe UI", 10))
        desc_lbl.setStyleSheet("color: #333;")
        desc_lbl.setWordWrap(True)
        meta.addWidget(desc_lbl)

        meta.addStretch()

        top.addLayout(meta)
        top.addStretch()
        root.addLayout(top)

        # horizontal separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # Middle area: Starting tab selector + quick actions
        mid = QHBoxLayout()
        mid.setSpacing(18)

        # left: starting tab selector
        left = QVBoxLayout()
        left.addWidget(QLabel("Start with:"))
        self.start_combo = QComboBox()
        self.start_combo.addItems(
            ["Invoices", "New Invoice", "Delivery Note", "Sales Report", "Stock"])
        left.addWidget(self.start_combo)

        # helpful short explanation
        left_hint = QLabel(
            "Choose where to start. You can change this later from Settings.")
        left_hint.setWordWrap(True)
        left_hint.setStyleSheet("color: #666; font-size: 11px;")
        left.addWidget(left_hint)
        left.addStretch()

        mid.addLayout(left, stretch=1)

        # right: quick actions list
        right = QVBoxLayout()
        right.addWidget(QLabel("Quick actions:"))

        self.quick_list = QListWidget()
        # action key in item.data(Qt.UserRole) — main app can decide what to do with them
        self._add_quick_action("new_invoice", "Create New Invoice")
        self._add_quick_action("search_invoice", "Search / Open Invoice")
        self._add_quick_action("view_sales", "View Sales Report")
        self._add_quick_action("stock_mgmt", "Open Stock Manager")
        self._add_quick_action("settings", "Open Settings")
        self.quick_list.itemClicked.connect(self._on_quick_click)
        right.addWidget(self.quick_list)
        mid.addLayout(right, stretch=1)

        root.addLayout(mid)

        # bottom area: footer + start button
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        copyright_lbl = QLabel(
            f"© {self.app_name} {(str(self._year()))} — Version {self.version}")
        copyright_lbl.setStyleSheet("color:#888;")
        bottom.addWidget(copyright_lbl)
        bottom.addStretch()

        self.btn_start = QPushButton("Start")
        self.btn_start.setFixedWidth(140)
        self.btn_start.setToolTip("Open the application")
        self.btn_start.clicked.connect(self._on_start)
        bottom.addWidget(self.btn_start)

        self.btn_quit = QPushButton("Quit")
        self.btn_quit.setFixedWidth(90)
        self.btn_quit.clicked.connect(self.close)
        bottom.addWidget(self.btn_quit)

        root.addLayout(bottom)

        # small style polish
        self.setStyleSheet("""
            QWidget { background: #ffffff; }
            QListWidget { border: 1px solid #ddd; }
            QPushButton { padding: 8px 10px; }
        """)

    def _add_quick_action(self, key: str, label: str):
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, key)
        self.quick_list.addItem(item)

    def _on_quick_click(self, item: QListWidgetItem):
        key = item.data(Qt.UserRole)
        # emit the action so caller can open the correct window
        self.quickActionRequested.emit(key)

    def _on_start(self):
        tab = str(self.start_combo.currentText() or "Invoices")
        self.startRequested.emit(tab)

    def _year(self):
        import datetime
        return datetime.date.today().year


# Quick run/debug UI
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = WelcomeWindow(app_name="BillMate", version="v1.3.2",
                      tagline="Invoices • Stock • Sales")
    # connect signals for demonstration
    w.startRequested.connect(lambda t: print("Start requested ->", t))
    w.quickActionRequested.connect(lambda a: print("Quick action ->", a))
    w.show()
    sys.exit(app.exec_())
