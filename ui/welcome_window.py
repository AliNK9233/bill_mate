# ui/welcome_window.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QSpacerItem,
    QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QPixmap, QFont, QColor
from PyQt5.QtCore import Qt
import os
import sqlite3
from contextlib import closing
from models import invoice_model as invoice_model


class WelcomeWindow(QWidget):
    """
    Improved customer-facing welcome splash:
     - centered card with shadow that blends with pale background
     - larger fonts and better spacing for good screen ratio
     - company data (logo/name/address) loaded from company_profile (id=1)
     - footer bottom-right with developer & version info
    """

    def __init__(self, parent=None, default_logo_path="data/logos/c_logo.png"):
        super().__init__(parent)
        self.default_logo_path = default_logo_path
        self.cp = self._get_company_profile()

        # derive displayed values (safe defaults)
        self.company_name = (self.cp.get("company_name")
                             or "Bill Mate").strip()
        # address assembly
        addr_parts = []
        if (self.cp.get("address_line1") or "").strip():
            addr_parts.append(self.cp.get("address_line1").strip())
        if (self.cp.get("address_line2") or "").strip():
            addr_parts.append(self.cp.get("address_line2").strip())
        city = (self.cp.get("city") or "").strip()
        state = (self.cp.get("state") or "").strip()
        country = (self.cp.get("country") or "").strip()
        loc = " ".join(p for p in (city, state, country) if p)
        if loc:
            addr_parts.append(loc)
        contact_parts = []
        if (self.cp.get("email") or "").strip():
            contact_parts.append(self.cp.get("email").strip())
        if (self.cp.get("phone1") or "").strip():
            contact_parts.append(self.cp.get("phone1").strip())
        if contact_parts:
            addr_parts.append(" | ".join(contact_parts))
        self.company_address = "\n".join(addr_parts)

        # logo path from DB if present
        self.logo_path = (self.cp.get("logo_path") or self.default_logo_path)

        # quote (use DB field if present; else use user-specified quote)
        self.quote = (self.cp.get("quote")
                      or "Trading Trust, Nourishing the Emirates").strip()

        # footer info
        self.app_name = "Bill Mate"
        self.app_version = "0"
        self.powered_by = "Averra"
        self.catch_line = "Your digital partner."

        # window tuning
        self.setWindowTitle(self.company_name)
        # don't fix to too small - keep resizable but a reasonable minimum
        self.setMinimumSize(1100, 700)

        self._setup_ui()

    def _get_company_profile(self):
        """Return single-row company_profile as a dict or empty dict on failure."""
        try:
            conn = invoice_model._connect()
            conn.row_factory = sqlite3.Row
            with closing(conn):
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM company_profile WHERE id = 1 LIMIT 1")
                r = cur.fetchone()
                if not r:
                    return {}
                return {k: (r[k] if k in r.keys() else None) for k in r.keys()}
        except Exception:
            return {}

    def _setup_ui(self):
        # overall root layout (this stretches to the entire window)
        root = QVBoxLayout()
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)
        self.setLayout(root)

        # set soft page background to blend with white card
        self.setStyleSheet("""
            QWidget#wrapper { background: #f4f7fb; }
        """)
        self.setObjectName("wrapper")

        # center container (vertical) - we use spacers to center the card
        center_vbox = QVBoxLayout()
        center_vbox.setContentsMargins(0, 0, 0, 0)
        center_vbox.setSpacing(0)

        # top spacer (push card to vertical center)
        center_vbox.addSpacerItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Card frame - white rounded with shadow
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background: #ffffff;
                border-radius: 12px;
            }
        """)
        # add drop shadow effect
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(22)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 30))
        card.setGraphicsEffect(shadow)
        card.setContentsMargins(18, 18, 18, 18)

        # card layout
        card_layout = QHBoxLayout()
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(30)
        card.setLayout(card_layout)

        # Left: Logo (larger)
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(220, 220)
        logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        logo_lbl.setStyleSheet("background:transparent;")
        if os.path.exists(self.logo_path):
            try:
                pix = QPixmap(self.logo_path).scaled(
                    220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_lbl.setPixmap(pix)
                logo_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            except Exception:
                logo_lbl.setText("")
        else:
            logo_lbl.setStyleSheet(
                "background:#ffffff;border:1px solid #eee;border-radius:12px;color:#666;")
            logo_lbl.setAlignment(Qt.AlignCenter)
            initials = "".join([p[0]
                               for p in self.company_name.split()[:2]]).upper()
            logo_lbl.setText(initials)
            logo_lbl.setFont(QFont("Segoe UI", 48, QFont.Bold))

        card_layout.addWidget(logo_lbl, alignment=Qt.AlignLeft | Qt.AlignTop)

        # Middle: Company details
        middle = QVBoxLayout()
        middle.setSpacing(10)

        # Company name - big
        name_lbl = QLabel(self.company_name.upper())
        name_lbl.setWordWrap(True)
        name_font = QFont("Segoe UI", 48, QFont.Bold)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet("color: #111;")
        middle.addWidget(name_lbl, alignment=Qt.AlignLeft)

        # Address - comfortable size
        if self.company_address:
            addr_lbl = QLabel(self.company_address)
            addr_lbl.setWordWrap(True)
            addr_lbl.setFont(QFont("Segoe UI", 14))
            addr_lbl.setStyleSheet("color:#444;")
            middle.addWidget(addr_lbl, alignment=Qt.AlignLeft)

        # Quote - prominent and colored
        quote_lbl = QLabel(f"“{self.quote}”")
        quote_lbl.setWordWrap(True)
        quote_lbl.setFont(QFont("Segoe UI", 20, QFont.StyleItalic))
        quote_lbl.setStyleSheet("color: #1f7a74;")
        middle.addWidget(quote_lbl, alignment=Qt.AlignLeft)

        # small spacer to push content up inside card if card is large
        middle.addSpacerItem(QSpacerItem(
            20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
        card_layout.addLayout(middle, stretch=2)

        # Right: empty area or future content (keeps card balanced)
        right_spacer = QVBoxLayout()
        right_spacer.addSpacerItem(QSpacerItem(
            40, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        card_layout.addLayout(right_spacer, stretch=1)

        # Add card to center layout (constrain width for better reading)
        # We'll put the card inside a small wrapper to limit max width (so the card doesn't stretch full width)
        card_wrapper = QHBoxLayout()
        card_wrapper.addSpacerItem(QSpacerItem(
            40, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        card_wrapper.addWidget(card, stretch=0)
        card_wrapper.addSpacerItem(QSpacerItem(
            40, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        center_vbox.addLayout(card_wrapper)

        # bottom spacer to keep centered
        center_vbox.addSpacerItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # add center_vbox into root
        root.addLayout(center_vbox)

        # Footer area anchored to bottom-right (developer & version info)
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(20, 8, 20, 12)

        left_footer = QLabel(f"© {self.company_name} {self._year()}")
        left_footer.setFont(QFont("Segoe UI", 11))
        left_footer.setStyleSheet("color:#8a8a8a;")
        footer_layout.addWidget(left_footer, alignment=Qt.AlignLeft)

        footer_layout.addSpacerItem(QSpacerItem(
            20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Right block
        right_block = QVBoxLayout()
        right_block.setSpacing(2)

        app_lbl = QLabel(f"{self.app_name} — App version {self.app_version}")
        app_lbl.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
        app_lbl.setStyleSheet("color:#333;")
        right_block.addWidget(app_lbl, alignment=Qt.AlignRight)

        powered_lbl = QLabel(f"Powered by {self.powered_by}")
        powered_lbl.setFont(QFont("Segoe UI", 11))
        powered_lbl.setStyleSheet("color:#666;")
        right_block.addWidget(powered_lbl, alignment=Qt.AlignRight)

        catch_lbl = QLabel(self.catch_line)
        catch_lbl.setFont(QFont("Segoe UI", 12, QFont.StyleItalic))
        catch_lbl.setStyleSheet("color:#1f7a74;")
        right_block.addWidget(catch_lbl, alignment=Qt.AlignRight)

        footer_layout.addLayout(right_block)

        # attach footer to root (keeps at bottom)
        root.addLayout(footer_layout)

        # final stylesheet to ensure page blends cleanly
        self.setStyleSheet(self.styleSheet() + """
            QWidget#wrapper { background: #f4f7fb; }
            QFrame#card { background: #ffffff; border: 1px solid rgba(0,0,0,0.04); }
        """)

    def _year(self):
        import datetime
        return datetime.date.today().year


# debug-run
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = WelcomeWindow()
    w.show()
    sys.exit(app.exec_())
