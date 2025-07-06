import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from models.stock_model import initialize_db

if __name__ == "__main__":
    # Initialize DB
    initialize_db()

    # Start App
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
