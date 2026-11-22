import sys

from PySide6.QtWidgets import QApplication

from core.settings import SettingsStore
from ui.main_window import MainWindow
from ui.theme import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Ollama Sentinel")
    app.setOrganizationName("ArvinNotDev")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow(SettingsStore())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
