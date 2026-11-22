from PySide6.QtGui import QIcon

APP_STYLESHEET = r"""
* {
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QWidget { color: #E8EAF0; background: transparent; outline: none; }
QMainWindow, QWidget#AppRoot, QWidget#ContentArea, QStackedWidget { background: #191B20; }
QFrame#Sidebar { background: #15171C; border-right: 1px solid #2B2F37; }
QFrame#TopBar { background: #191B20; border-bottom: 1px solid #2A2E36; }
QLabel { background: transparent; border: none; }
QLabel#Brand { color: #F4F5F8; font-size: 15px; font-weight: 700; letter-spacing: 0.1px; }
QLabel#BrandMark { color: #FFFFFF; background: #6555A8; border: 1px solid #8171C8; border-radius: 11px; }
QLabel#PageTitle { color: #F2F3F6; font-size: 24px; font-weight: 700; }
QLabel#PageSubtitle { color: #9DA3AF; font-size: 12px; }
QLabel#Muted { color: #9CA3AF; }
QLabel#SectionTitle { color: #ECEEF3; font-size: 14px; font-weight: 650; }
QLabel#StatusDot { color: #68D6A0; font-size: 12px; font-weight: 600; }
QLabel#CardTitle { color: #F0F1F4; font-size: 14px; font-weight: 650; }
QLabel#CardDescription { color: #A7ADB8; }
QLabel#Tag { color: #CEC5FF; background: #302B40; border: 1px solid #48405E; border-radius: 7px; padding: 4px 8px; font-size: 11px; font-weight: 600; }
QPushButton {
    color: #E7E9EF; background: #252930; border: 1px solid #363B45;
    border-radius: 10px; padding: 8px 13px; font-weight: 600; min-height: 18px;
}
QPushButton:hover { background: #2D323B; border-color: #4A505D; }
QPushButton:pressed { background: #20242A; }
QPushButton:disabled { color: #727987; background: #202329; border-color: #2C3038; }
QPushButton#PrimaryButton { color: #FFFFFF; background: #7564C7; border: 1px solid #8575D6; }
QPushButton#PrimaryButton:hover { background: #8373D8; border-color: #9485E6; }
QPushButton#PrimaryButton:pressed { background: #6656B4; }
QPushButton#NavButton {
    color: #A9AFBB; background: transparent; border: 1px solid transparent;
    border-radius: 10px; text-align: left; padding: 10px 12px; min-height: 20px; font-weight: 550;
}
QPushButton#NavButton:hover { color: #F0F1F4; background: #22252C; }
QPushButton#NavButton:checked { color: #F7F5FF; background: #292538; border: 1px solid #403958; }
QPushButton#NavTab {
    color: #A9AFBB; background: transparent; border: 1px solid transparent;
    border-radius: 18px; padding: 6px 13px; min-height: 16px; font-weight: 600;
}
QPushButton#NavTab:hover { color: #F0F1F4; background: #252932; }
QPushButton#NavTab:checked { color: #F7F5FF; background: #302B40; border-color: #49415F; }
QPushButton#NewChatButton {
    color: #FFFFFF; background: #6555A8; border: 1px solid #7A6BC0;
    border-radius: 11px; padding: 8px 13px; text-align: left; font-weight: 650;
}
QPushButton#NewChatButton:hover { background: #7565BD; border-color: #9182D4; }
QPushButton#GhostButton { color: #C8CBD4; background: transparent; border: 1px solid #383D47; }
QPushButton#GhostButton:hover { color: #FFFFFF; background: #252932; border-color: #505663; }
QPushButton#DangerButton { color: #F09BA4; background: #302126; border: 1px solid #55333D; }
QPushButton#DangerButton:hover { background: #3B252D; border-color: #70404C; }
QComboBox#ModelPicker {
    color: #E8EAF0; background: #252A33; border: 1px solid #414855;
    border-radius: 18px; padding: 5px 11px; font-size: 12px; font-weight: 600;
}
QComboBox#ModelPicker:hover { background: #2B303A; border-color: #5B6372; }
QComboBox#ModelPicker:focus { border-color: #8373D8; }
QComboBox#ModelPicker::drop-down { width: 21px; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    color: #E8EAF0; background: #20242B; border: 1px solid #343A45;
    border-radius: 10px; padding: 9px 11px; selection-background-color: #6455A9; selection-color: #FFFFFF;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover { border-color: #4A505D; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #8373D8; background: #22262E; }
QTextEdit#Composer, QPlainTextEdit#Composer {
    color: #F0F1F4; background: transparent; border: none; border-radius: 8px;
    padding: 7px 9px; font-size: 14px;
}
QComboBox::drop-down { border: none; width: 27px; }
QComboBox QAbstractItemView {
    color: #E9EBF1; background: #242830; border: 1px solid #3B414D;
    selection-background-color: #39334E; selection-color: #FFFFFF; outline: none; padding: 5px;
}
QScrollArea { background: transparent; border: none; }
QScrollArea QWidget { background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 3px 1px; }
QScrollBar::handle:vertical { background: #414752; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #596170; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QFrame#Surface, QFrame#ModelCard, QFrame#MessageCard, QFrame#SettingCard, QFrame#ServerCard {
    background: #20242B; border: 1px solid #2F343E; border-radius: 15px;
}
QFrame#HeroCard { background: #22232B; border: 1px solid #343741; border-radius: 16px; }
QFrame#UserMessage { background: #173e76; border: 1px solid #28558F; border-radius: 14px; }
QFrame#AssistantMessage { background: transparent; border: 1px solid transparent; border-radius: 12px; }
QProgressBar { height: 8px; border: none; border-radius: 4px; background: #343A44; text-align: center; color: transparent; }
QProgressBar::chunk { border-radius: 4px; background: #8876D9; }
QTabWidget::pane { background: #1D2026; border: 1px solid #30353E; border-radius: 12px; top: -1px; }
QTabBar::tab { color: #A0A6B2; background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 9px 14px; margin: 3px 3px 5px 0; }
QTabBar::tab:hover { color: #F1F2F5; background: #272B33; }
QTabBar::tab:selected { color: #F2EEFF; background: #302B40; border-color: #49415F; }
QCheckBox { color: #C7CBD4; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #4B5361; border-radius: 5px; background: #20242B; }
QCheckBox::indicator:checked { background: #7664C8; border-color: #9484E5; }
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: #3A404B; }
QSlider::sub-page:horizontal { background: #8170D2; border-radius: 2px; }
QSlider::handle:horizontal { width: 15px; margin: -5px 0; border-radius: 7px; background: #E8E4FF; border: 2px solid #8170D2; }
QToolTip { color: #F4F5F8; background: #292D35; border: 1px solid #4A505D; padding: 6px 8px; border-radius: 6px; }
QStatusBar { color: #AEB4C0; background: #17191E; border-top: 1px solid #2B3038; }
QStatusBar::item { border: none; }
QFrame#DownloadSidebar {
    background: #20242B;
    border: 1px solid #343A45;
    border-radius: 16px;
}
QListWidget#ModelCatalogList {
    color: #DDE0E7;
    background: #20242B;
    border: 1px solid #343A45;
    border-radius: 12px;
    padding: 5px;
    outline: none;
}
QListWidget#ModelCatalogList::item {
    color: #DDE0E7;
    background: transparent;
    padding: 10px 8px;
    border-bottom: 1px solid #2C313A;
    border-radius: 7px;
}
QListWidget#ModelCatalogList::item:hover {
    background: #292E37;
}
QListWidget#ModelCatalogList::item:selected {
    color: #F6F3FF;
    background: #343049;
    border: 1px solid #4A4263;
}
QScrollArea#AttachmentStrip { background: transparent; border: none; }
QPushButton#AddAttachmentButton {
    color: #E4E8F0; background: #2A303A; border: 1px solid #414957;
    border-radius: 18px; padding: 4px; min-width: 28px; min-height: 28px;
}
QPushButton#AddAttachmentButton:hover { color: #FFFFFF; background: #363D49; border-color: #596374; }
QFrame#AttachmentChip {
    color: #DDE0E7; background: #292E37; border: 1px solid #3C424E; border-radius: 10px;
}
QLabel#AttachmentChipName { color: #DDE0E7; background: transparent; }
QLabel#AttachmentMessageChip {
    color: #C7C0E9; background: #2E2A3D; border: 1px solid #423B58;
    border-radius: 8px; padding: 5px 9px;
}
QPushButton#AttachmentRemoveButton {
    color: #AAB1BE; background: transparent; border: none; border-radius: 8px;
    padding: 2px; min-height: 16px;
}
QPushButton#AttachmentRemoveButton:hover { color: #FFFFFF; background: #414754; }
QPushButton#ThinkingHeader {
    color: #C8BFF0; background: transparent; border: none; text-align: left;
    padding: 4px 2px; min-height: 16px;
}
QPushButton#ThinkingHeader:hover { color: #F0EBFF; background: transparent; }
QLabel#ThinkingDot { color: #C4B8F0; font-size: 8px; background: transparent; }
QTextBrowser#ThinkingBody {
    color: #ADB4C1; background: #20242B; border: 1px solid #343A45;
    border-radius: 10px; padding: 8px 10px;
}
QListWidget#ChatHistoryList {
    color: #DDE0E7; background: transparent; border: none; outline: none;
    padding: 3px 0;
}
QListWidget#ChatHistoryList::item {
    color: #AEB5C2; background: transparent; border: 1px solid transparent;
    border-radius: 9px; padding: 10px 11px; margin: 1px 0; min-height: 20px;
}
QListWidget#ChatHistoryList::item:hover { color: #F1F2F5; background: #22262E; }
QListWidget#ChatHistoryList::item:selected {
    color: #F5F2FF; background: #2B2939; border-color: #403A55;
}
"""


def app_icon(name: str, color: str = "#A8AFBC") -> QIcon:
    """Create a Material Design icon via QtAwesome."""
    try:
        import qtawesome as qta
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


def apply_app_theme(app) -> None:
    """Use Qt-Material as the native control foundation, then apply Sentinel styling."""
    from qt_material import apply_stylesheet

    apply_stylesheet(app, theme="dark_purple.xml", extra={"density_scale": "-1"})
    app.setStyleSheet(app.styleSheet() + "\n" + APP_STYLESHEET)
