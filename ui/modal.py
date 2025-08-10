from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QButtonGroup, QRadioButton, QPushButton, QFrame, QHBoxLayout
)
from PyQt5.QtCore import Qt


class ModelSelectionDialog(QDialog):
    def __init__(self, parent=None, model_data=None):
        super().__init__(parent)
        self.setWindowTitle("Select Model to Download")
        self.setModal(True)
        self.setMinimumSize(600, 600)

        self.selected_model = None
        self.selected_variant = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Titlebar with modern dark look
        titlebar = QWidget()
        titlebar.setFixedHeight(36)
        titlebar.setStyleSheet("background-color: #121212;")  # very dark gray
        titlebar_layout = QHBoxLayout()
        titlebar_layout.setContentsMargins(12, 0, 12, 0)
        titlebar_layout.setSpacing(8)

        close_button = QPushButton()
        close_button.setFixedSize(14, 14)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: none;
                border-radius: 7px;
                box-shadow: 0 0 4px #ff5f56aa;
            }
            QPushButton:hover {
                background-color: #ff1f0f;
                box-shadow: 0 0 8px #ff1f0faa;
            }
        """)
        close_button.clicked.connect(self.reject)

        title_label = QLabel("Select Model to Download")
        title_label.setStyleSheet("""
            color: #39ff14;
            font-family: 'Consolas', monospace;
            font-weight: 700;
            font-size: 16px;
            text-shadow: 0 0 5px #39ff14aa;
        """)
        title_label.setAlignment(Qt.AlignCenter)

        titlebar_layout.addWidget(close_button)
        titlebar_layout.addStretch()
        titlebar_layout.addWidget(title_label)
        titlebar_layout.addStretch()
        titlebar_layout.addSpacing(14)  # symmetry with close button size
        titlebar.setLayout(titlebar_layout)
        main_layout.addWidget(titlebar)

        # Scroll area for model list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(14, 14, 14, 14)
        scroll_layout.setSpacing(18)

        self.button_groups = {}

        if model_data is None:
            model_data = {}

        for model_name, (sizes, summary) in model_data.items():
            label = QLabel(model_name)
            label.setStyleSheet("""
                font-weight: 700;
                font-size: 18px;
                color: #39ff14;
                font-family: 'Consolas', monospace;
                text-shadow: 0 0 4px #39ff14cc;
            """)
            scroll_layout.addWidget(label)

            summary_label = QLabel(summary)
            summary_label.setWordWrap(True)
            summary_label.setStyleSheet("""
                color: #28a745;
                font-size: 13px;
                font-family: 'Consolas', monospace;
                margin-bottom: 10px;
                text-shadow: 0 0 3px #28a745bb;
            """)
            scroll_layout.addWidget(summary_label)

            radio_layout = QHBoxLayout()
            radio_layout.setSpacing(20)
            group = QButtonGroup(self)
            group.setExclusive(True)

            for size in sizes.split(","):
                size = size.strip()
                radio = QRadioButton(size)
                radio.model_name = model_name
                radio.variant = size
                radio.setStyleSheet("""
                    QRadioButton {
                        color: #39ff14;
                        font-family: 'Consolas', monospace;
                        font-size: 14px;
                        spacing: 8px;
                    }
                    QRadioButton::indicator {
                        width: 16px;
                        height: 16px;
                        border-radius: 8px;
                        border: 2px solid #39ff14;
                        background: transparent;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #39ff14;
                    }
                    QRadioButton:hover {
                        color: #7fff7f;
                    }
                """)
                group.addButton(radio)
                radio_layout.addWidget(radio)

            scroll_layout.addLayout(radio_layout)
            self.button_groups[model_name] = group

            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("color: #222222; background-color: #222222; max-height: 1px;")
            scroll_layout.addWidget(line)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        confirm_btn = QPushButton("Confirm Selection")
        confirm_btn.clicked.connect(self.confirm_selection)
        confirm_btn.setStyleSheet("""
            QPushButton {
                padding: 12px;
                font-weight: 700;
                font-family: 'Consolas', monospace;
                background-color: #1e1e1e;
                color: #39ff14;
                border: 2px solid #39ff14;
                border-radius: 6px;
                text-shadow: 0 0 5px #39ff14cc;
            }
            QPushButton:hover {
                background-color: #39ff14;
                color: #121212;
                border-color: #7fff7f;
                text-shadow: none;
            }
            QPushButton:pressed {
                background-color: #2ecc40;
                color: #0b0b0b;
                border-color: #2ecc40;
            }
        """)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setMinimumHeight(44)
        main_layout.addWidget(confirm_btn)

        self.setStyleSheet("background-color: #121212;")

    def confirm_selection(self):
        for model_name, group in self.button_groups.items():
            for btn in group.buttons():
                if btn.isChecked():
                    self.selected_model = btn.model_name
                    self.selected_variant = btn.variant
                    self.accept()
                    return
        self.reject()
