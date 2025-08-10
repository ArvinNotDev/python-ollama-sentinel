from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QButtonGroup, QRadioButton, QPushButton, QFrame
)


class ModelSelectionDialog(QDialog):
    def __init__(self, parent=None, model_data=None):
        super().__init__(parent)
        self.setWindowTitle("Select Model")
        self.setModal(True)
        self.setFixedSize(400, 500)

        self.selected_model = None
        self.selected_variant = None

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        if model_data is None:
            model_data = {}

        for model_name, variants in model_data.items():
            label = QLabel(model_name)
            label.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 10px;")
            scroll_layout.addWidget(label)

            for var in variants:
                radio = QRadioButton(var)
                radio.model_name = model_name
                radio.variant = var
                self.group.addButton(radio)
                scroll_layout.addWidget(radio)

            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            scroll_layout.addWidget(line)

        scroll_content.setLayout(scroll_layout)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        confirm_btn = QPushButton("Confirm Selection")
        confirm_btn.clicked.connect(self.confirm_selection)
        layout.addWidget(confirm_btn)

    def confirm_selection(self):
        checked = self.group.checkedButton()
        if checked:
            self.selected_model = checked.model_name
            self.selected_variant = checked.variant
        self.accept()
