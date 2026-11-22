APP_STYLESHEET = r"""
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; }
QWidget { color: #e7e9f0; background: #0d0f14; }
QMainWindow { background: #0d0f14; }
QFrame#Sidebar { background: #10131a; border-right: 1px solid #222733; }
QFrame#TopBar { background: #10131a; border-bottom: 1px solid #222733; }
QLabel#Brand { color: #f4f5fa; font-size: 16px; font-weight: 700; }
QLabel#BrandMark { color: #ffffff; background: #7457f5; border-radius: 12px; font-size: 17px; font-weight: 800; }
QLabel#PageTitle { color: #f5f6fb; font-size: 25px; font-weight: 700; }
QLabel#PageSubtitle { color: #9299aa; font-size: 13px; }
QLabel#Muted { color: #9299aa; }
QLabel#SectionTitle { color: #f1f2f7; font-size: 15px; font-weight: 650; }
QLabel#StatusDot { color: #45d69a; font-size: 11px; }
QPushButton { color: #dfe2eb; background: #1a1e28; border: 1px solid #2a3040; border-radius: 10px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #242a37; border-color: #3a4358; }
QPushButton:pressed { background: #161a22; }
QPushButton:disabled { color: #5f6675; background: #171a21; border-color: #252a34; }
QPushButton#PrimaryButton { color: white; background: #7057e8; border: 1px solid #806bf0; }
QPushButton#PrimaryButton:hover { background: #806bf0; }
QPushButton#NavButton { text-align: left; background: transparent; border: none; border-radius: 10px; padding: 11px 13px; color: #aab0bf; }
QPushButton#NavButton:hover { color: #f3f4f8; background: #1a1e29; }
QPushButton#NavButton:checked { color: #ffffff; background: #25213a; border: 1px solid #3b3266; }
QPushButton#GhostButton { background: transparent; border: 1px solid #303748; }
QPushButton#DangerButton { color: #ff929c; background: #291a21; border-color: #57303b; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox { color: #e8eaf1; background: #151923; border: 1px solid #2a3040; border-radius: 10px; padding: 10px 12px; selection-background-color: #6d56dc; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #7964e9; }
QTextEdit#Composer { background: #151923; border: 1px solid #33394a; border-radius: 15px; padding: 13px; font-size: 14px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: #191d27; color: #e8eaf1; selection-background-color: #40356f; border: 1px solid #303748; outline: none; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: #343b4a; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #4a5265; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QFrame#Surface, QFrame#ModelCard, QFrame#MessageCard, QFrame#SettingCard { background: #141821; border: 1px solid #272d3a; border-radius: 15px; }
QFrame#HeroCard { background: #19172a; border: 1px solid #39315d; border-radius: 18px; }
QFrame#UserMessage { background: #282342; border: 1px solid #44396f; border-radius: 14px; }
QFrame#AssistantMessage { background: #151a23; border: 1px solid #2a3140; border-radius: 14px; }
QLabel#CardTitle { color: #f0f1f7; font-size: 15px; font-weight: 650; }
QLabel#CardDescription { color: #9da4b3; }
QLabel#Tag { color: #bdb4ff; background: #26213f; border: 1px solid #403768; border-radius: 7px; padding: 4px 7px; font-size: 11px; }
QProgressBar { height: 8px; border: none; border-radius: 4px; background: #292f3c; text-align: center; }
QProgressBar::chunk { border-radius: 4px; background: #7962e9; }
QTabWidget::pane { border: 1px solid #282e3a; border-radius: 12px; top: -1px; background: #11151d; }
QTabBar::tab { color: #969dad; background: transparent; padding: 10px 16px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #f4f4f8; border-bottom: 2px solid #826cf0; }
QCheckBox { color: #b9bfcc; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #475064; border-radius: 5px; background: #171b25; }
QCheckBox::indicator:checked { background: #745ce8; border-color: #8875f0; }
QToolTip { color: #f4f4f8; background: #202532; border: 1px solid #3a4254; padding: 6px; }
"""
