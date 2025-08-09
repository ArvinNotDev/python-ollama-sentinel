import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QCheckBox, QTextEdit,
    QLineEdit, QSplitter, QListWidget, QSizePolicy
)
from PyQt5.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI master")
        self.setGeometry(100, 100, 1000, 600)

        self.sidebar = self.create_sidebar()
        self.main_panel = self.create_main_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.main_panel)
        splitter.setSizes([200, 800])

        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        container.setLayout(layout)

        self.setCentralWidget(container)

    def create_sidebar(self):
        sidebar = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Dashboard", alignment=Qt.AlignCenter))

        btn_model = QPushButton("Select Model")
        btn_model.clicked.connect(self.select_model)
        layout.addWidget(btn_model)

        btn_folder = QPushButton("Select Folder")
        btn_folder.clicked.connect(self.select_folder)
        layout.addWidget(btn_folder)

        layout.addWidget(QPushButton("Project Structure"))
        layout.addWidget(QPushButton("Settings"))

        layout.addStretch()
        sidebar.setLayout(layout)
        sidebar.setStyleSheet("background-color: #2c2c2c; color: white;")
        return sidebar

    def create_main_panel(self):
        panel = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Workspace")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter your prompt here...")
        layout.addWidget(self.prompt_input)

        layout.addWidget(QLabel("Options:"))
        self.chk_structure = QCheckBox("Add structure to the prompt")
        self.chk_all_files = QCheckBox("Give all files")
        layout.addWidget(self.chk_structure)
        layout.addWidget(self.chk_all_files)

        layout.addWidget(QLabel("Response / Output:"))
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        layout.addWidget(self.output_box)

        panel.setLayout(layout)
        return panel

    def select_model(self):
        model_path, _ = QFileDialog.getOpenFileName(self, "Select Model File")
        if model_path:
            self.output_box.append(f"Model selected: {model_path}")

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.output_box.append(f"Folder selected: {folder_path}")


