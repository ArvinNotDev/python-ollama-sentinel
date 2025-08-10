import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QCheckBox, QTextEdit,
    QLineEdit, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from ui.modal import ModelSelectionDialog
from core.ollama.ollama_commands import OllamaUtils
from core.utils.prompt_utils import PromptUtils


class LoadingOverlay(QWidget):
    def __init__(self, parent=None, text="Loading..."):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        self.setGeometry(parent.rect())
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(text)
        label.setStyleSheet("color: #00FF00; font-size: 18px; font-weight: bold; font-family: Consolas;")
        layout.addWidget(label)
        self.setLayout(layout)
        self.show()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ollama Sentinel")
        self.setGeometry(100, 100, 1000, 600)

        self.sidebar = self.create_sidebar()
        self.main_panel = self.create_main_panel()
        self.selected_folder = ""

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.main_panel)
        splitter.setSizes([200, 800])

        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        titlebar = QWidget()
        titlebar.setFixedHeight(30)
        titlebar.setStyleSheet("background-color: #000000;")
        titlebar_layout = QHBoxLayout()
        titlebar_layout.setContentsMargins(10, 0, 0, 0)

        close_button = QPushButton()
        close_button.setFixedSize(12, 12)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ff1f0f;
            }
        """)
        close_button.clicked.connect(self.close)

        titlebar_layout.addWidget(close_button)
        titlebar_layout.addStretch()
        titlebar.setLayout(titlebar_layout)

        layout.addWidget(titlebar)
        layout.addWidget(splitter)
        container.setLayout(layout)

        self.setCentralWidget(container)
        self.setStyleSheet("QMainWindow { background-color: #1e1e1e; }")

    def create_sidebar(self):
        sidebar = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Dashboard", alignment=Qt.AlignCenter)
        layout.addWidget(title)

        btn_model = QPushButton("Select Model")
        btn_model.clicked.connect(self.select_model)
        layout.addWidget(btn_model)

        btn_download_model = QPushButton("Download Model")
        btn_download_model.clicked.connect(self.download_model)
        layout.addWidget(btn_download_model)

        btn_folder = QPushButton("Select Folder")
        btn_folder.clicked.connect(self.select_folder)
        layout.addWidget(btn_folder)

        layout.addWidget(QPushButton("Project Structure"))
        layout.addWidget(QPushButton("Settings"))

        layout.addStretch()
        sidebar.setLayout(layout)
        sidebar.setStyleSheet("""
            QPushButton {
                padding: 8px;
                background-color: #111;
                color: #00FF00;
                border: 1px solid #00FF00;
                border-radius: 3px;
                font-family: Consolas;
            }
            QPushButton:hover {
                background-color: #222;
            }
            QLabel {
                color: #00FF00;
                font-size: 16px;
                margin-bottom: 10px;
                font-family: Consolas;
            }
            QWidget {
                background-color: #000000;
            }
        """)
        return sidebar

    def create_main_panel(self):
        panel = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Workspace")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00FF00; font-family: Consolas;")
        layout.addWidget(title)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter your prompt here...")
        self.prompt_input.setStyleSheet("padding: 6px; background-color: #111; color: #00FF00; font-family: Consolas;")
        layout.addWidget(self.prompt_input)

        layout.addWidget(QLabel("Options:", styleSheet="color: #00FF00; font-family: Consolas;"))
        self.chk_structure = QCheckBox("Add structure to the prompt")
        self.chk_all_files = QCheckBox("Give all files")
        for chk in [self.chk_structure, self.chk_all_files]:
            chk.setStyleSheet("color: #00FF00; font-family: Consolas;")
        layout.addWidget(self.chk_structure)
        layout.addWidget(self.chk_all_files)

        layout.addWidget(QLabel("Response / Output:", styleSheet="color: #00FF00; font-family: Consolas;"))

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setStyleSheet("""
            background-color: black;
            color: #00FF00;
            font-family: Consolas, monospace;
            font-size: 13px;
            border-radius: 5px;
            padding: 10px;
        """)
        layout.addWidget(self.output_box)

        btn_generate = QPushButton("Generate")
        btn_generate.clicked.connect(self.generate_output)
        btn_generate.setStyleSheet("padding: 10px; font-weight: bold; font-family: Consolas; background-color: #222; color: #00FF00; border: 1px solid #00FF00;")
        layout.addWidget(btn_generate)

        panel.setStyleSheet("background-color: #1e1e1e;")
        panel.setLayout(layout)
        return panel

    def select_model(self):
        overlay = LoadingOverlay(self, "Loading models...")
        QTimer.singleShot(100, lambda: self._select_model(overlay))

    def _select_model(self, overlay):
        models = OllamaUtils.list_downloaded_models()
        model_data = {}

        for m in models:
            name = m.get("model", "<unknown>")
            details = m.get("details", None)
            size = getattr(details, "parameter_size", "unknown") if details else "unknown"
            model_data[name] = [size]

        dialog = ModelSelectionDialog(self, model_data)
        if dialog.exec_():
            sel = f"{dialog.selected_model} – {dialog.selected_variant}"
            self.output_box.append(f"\n> Model selected: {sel}")

        overlay.deleteLater()

    def download_model(self):
        overlay = LoadingOverlay(self, "Fetching available models...")
        QTimer.singleShot(100, lambda: self._download_model(overlay))

    def _download_model(self, overlay):
        models = OllamaUtils.list_all_models()
        if not models:
            self.output_box.append("\n> Ollama.com is not reachable.")
            overlay.deleteLater()
            return

        model_data = {}
        for m in models:
            name = m.get("name", "<unknown>")
            sizes = m.get("sizes", "unknown")
            summary = m.get("summary", "")
            model_data[name] = [sizes, summary]

        dialog = ModelSelectionDialog(self, model_data)
        if dialog.exec_():
            sel = f"{dialog.selected_model} – {dialog.selected_variant}"
            self.output_box.append(f"\n> Downloading model: {sel}")
            # TODO: Trigger actual download

        overlay.deleteLater()

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.selected_folder = folder_path
            self.output_box.append(f"\n> Folder selected: {folder_path}")

    def generate_output(self):
        prompt = self.prompt_input.text()
        structure = self.chk_structure.isChecked()
        all_files = self.chk_all_files.isChecked()

        if (structure or all_files) and not self.selected_folder:
            self.output_box.append("\n> Error: Please select a folder first!")
            return

        prompt_utils = PromptUtils(self.selected_folder)
        final_result = prompt_utils.final_prompt(prompt, structure, all_files)

        self.output_box.setPlainText(final_result)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
