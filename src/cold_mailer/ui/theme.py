"""Shared Fusion palettes and control styling, including dialogs and popup views."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

THEME_MODES = ("system", "light", "dark")


@dataclass(frozen=True)
class Colors:
    canvas: str
    surface: str
    raised: str
    border: str
    text: str
    muted: str
    accent: str
    hover: str
    tint: str
    danger: str
    selection: str


LIGHT = Colors(
    "#f3f5fa",
    "#ffffff",
    "#f8f9fd",
    "#dce2ed",
    "#1b2540",
    "#64718b",
    "#5754df",
    "#4642c6",
    "#eeedff",
    "#c23d59",
    "#e5e4ff",
)
DARK = Colors(
    "#11141f",
    "#1b2030",
    "#232a3d",
    "#343d55",
    "#edf0fa",
    "#a4b0ca",
    "#a59cff",
    "#b9b2ff",
    "#302d50",
    "#ff93a8",
    "#393557",
)


def resolve_theme(mode: str) -> str:
    if mode == "system":
        return (
            "dark" if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"
        )
    return mode if mode in ("light", "dark") else "light"


def apply_theme(application: QApplication, mode: str) -> Colors:
    colors = DARK if resolve_theme(mode) == "dark" else LIGHT
    # Fusion avoids mixing Windows native subcontrols with stylesheet geometry.
    if not application.property("coldMailerFusion"):
        application.setStyle("Fusion")
        application.setProperty("coldMailerFusion", True)
        # The offscreen Windows plugin does not discover installed fonts itself.
        # Load existing OS fonts for readable smoke tests; fonts are never bundled.
        if sys.platform == "win32" and "Segoe UI" not in QFontDatabase.families():
            font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
                path = font_dir / name
                if path.is_file():
                    QFontDatabase.addApplicationFont(str(path))
        application.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors.canvas,
        QPalette.ColorRole.WindowText: colors.text,
        QPalette.ColorRole.Base: colors.surface,
        QPalette.ColorRole.AlternateBase: colors.raised,
        QPalette.ColorRole.Text: colors.text,
        QPalette.ColorRole.Button: colors.surface,
        QPalette.ColorRole.ButtonText: colors.text,
        QPalette.ColorRole.Highlight: colors.selection,
        QPalette.ColorRole.HighlightedText: colors.text,
        QPalette.ColorRole.PlaceholderText: colors.muted,
        QPalette.ColorRole.ToolTipBase: colors.surface,
        QPalette.ColorRole.ToolTipText: colors.text,
        QPalette.ColorRole.Light: colors.surface,
        QPalette.ColorRole.Midlight: colors.raised,
        QPalette.ColorRole.Mid: colors.border,
        QPalette.ColorRole.Dark: colors.border,
        QPalette.ColorRole.Shadow: colors.border,
        QPalette.ColorRole.Link: colors.accent,
        QPalette.ColorRole.Accent: colors.accent,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.muted))
    application.setPalette(palette)
    c = colors
    variant = "dark" if colors == DARK else "light"
    assets = Path(__file__).with_name("assets")
    down = (assets / f"down-{variant}.svg").as_posix()
    up = (assets / f"up-{variant}.svg").as_posix()
    check = (assets / f"check-{variant}.svg").as_posix()
    primary_text = "#211b42" if colors == DARK else "#ffffff"
    application.setStyleSheet(f"""
        QWidget {{ color: {c.text}; font-family: 'Segoe UI'; font-size: 13px; }}
        QMainWindow, QWidget#appRoot, QWidget#page, QScrollArea#pageScroll,
        QScrollArea#pageScroll > QWidget > QWidget {{ background: {c.canvas}; }}
        QLabel {{ background: transparent; border: none; }}
        QLabel#brand {{ font-size: 23px; font-weight: 700; letter-spacing: -0.5px; }}
        QLabel#eyebrow {{ color: {c.accent}; font-size: 10px; font-weight: 700; letter-spacing: 1.6px; }}
        QLabel#cardTitle {{ font-size: 16px; font-weight: 650; }}
        QLabel#muted, QLabel#hint {{ color: {c.muted}; }}
        QLabel#hint {{ font-size: 12px; }}
        QLabel#fieldLabel {{ color: {c.text}; font-size: 12px; font-weight: 600; }}
        QLabel#badge {{ background: {c.tint}; color: {c.accent}; border-radius: 6px; padding: 6px 10px; font-weight: 600; }}
        QLabel#modeBadge {{ background: {c.raised}; color: {c.muted}; border: 1px solid {c.border}; border-radius: 6px; padding: 6px 10px; }}
        QLabel#modeBadge[live="true"] {{ background: {c.tint}; color: {c.danger}; }}
        QFrame#card {{ background: {c.surface}; border: 1px solid {c.border}; border-radius: 12px; }}
        QFrame#footer {{ border-top: 1px solid {c.border}; }}
        QWidget#cardBody, QWidget#field, QWidget#emptyState {{ background: transparent; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
            border-radius: 7px; padding: 0 11px; min-height: 38px;
            selection-background-color: {c.selection}; selection-color: {c.text};
        }}
        QPlainTextEdit {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
            border-radius: 8px; padding: 9px; selection-background-color: {c.selection}; selection-color: {c.text}; }}
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {c.muted}; }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{ border: 1px solid {c.accent}; }}
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
        QPlainTextEdit:disabled {{ background: {c.raised}; color: {c.muted}; }}
        QLineEdit:read-only, QPlainTextEdit:read-only {{ background: {c.raised}; }}
        QComboBox {{ padding-right: 38px; combobox-popup: 0; }}
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right;
            width: 30px; border: none; border-left: 1px solid {c.border}; }}
        QComboBox::down-arrow {{ image: url("{down}"); width: 13px; height: 13px; }}
        QComboBox QAbstractItemView {{ background: {c.surface}; color: {c.text};
            border: 1px solid {c.border}; padding: 5px; outline: 0;
            selection-background-color: {c.tint}; selection-color: {c.accent}; }}
        QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 4px 8px; }}
        QSpinBox, QDoubleSpinBox {{ padding-right: 32px; }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border;
            subcontrol-position: top right; width: 28px; border: none; border-left: 1px solid {c.border}; border-top-right-radius: 7px; }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border;
            subcontrol-position: bottom right; width: 28px; border: none; border-left: 1px solid {c.border}; border-bottom-right-radius: 7px; }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {c.tint}; }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{up}"); width: 12px; height: 12px; }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{down}"); width: 12px; height: 12px; }}
        QPushButton, QToolButton {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
            border-radius: 7px; padding: 0 13px; min-height: 38px; font-weight: 600; }}
        QPushButton:hover, QToolButton:hover {{ background: {c.tint}; border-color: {c.accent}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {c.selection}; }}
        QPushButton:focus, QToolButton:focus {{ border: 1px solid {c.accent}; }}
        QPushButton[kind="primary"] {{ background: {c.accent}; color: {primary_text}; border-color: {c.accent}; }}
        QPushButton[kind="primary"]:hover {{ background: {c.hover}; border-color: {c.hover}; }}
        QPushButton[kind="danger"] {{ color: {c.danger}; }}
        QPushButton[kind="quiet"] {{ background: transparent; border-color: transparent; color: {c.muted}; }}
        QPushButton[kind="quiet"]:hover {{ background: {c.raised}; color: {c.text}; border-color: {c.border}; }}
        QPushButton:disabled, QPushButton[kind="primary"]:disabled {{ background: {c.raised};
            color: {c.muted}; border-color: {c.border}; }}
        QCheckBox {{ spacing: 8px; background: transparent; }}
        QCheckBox::indicator {{ width: 17px; height: 17px; background: {c.surface}; border: 1px solid {c.border}; border-radius: 4px; }}
        QCheckBox::indicator:checked {{ image: url("{check}"); background: {c.accent}; border-color: {c.accent}; }}
        QCheckBox::indicator:hover, QCheckBox::indicator:focus {{ border-color: {c.accent}; }}
        QTabWidget::pane {{ border: none; background: transparent; }}
        QTabBar::tab {{ background: transparent; color: {c.muted}; border: none;
            padding: 11px 18px; margin: 0 5px 9px 0; border-radius: 7px; font-weight: 600; }}
        QTabBar::tab:selected {{ background: {c.surface}; color: {c.accent}; }}
        QTabBar::tab:hover:!selected {{ background: {c.raised}; color: {c.text}; }}
        QTabWidget#briefTabs QTabBar::tab {{ padding: 8px 12px; margin-bottom: 4px; }}
        QTableView {{ background: {c.surface}; alternate-background-color: {c.raised}; color: {c.text};
            border: none; gridline-color: {c.border}; selection-background-color: {c.selection}; selection-color: {c.text}; outline: 0; }}
        QTableView::item {{ border-bottom: 1px solid {c.border}; padding: 6px; }}
        QHeaderView::section {{ background: {c.raised}; color: {c.muted}; border: none;
            border-bottom: 1px solid {c.border}; padding: 10px 8px; font-size: 11px; font-weight: 600; }}
        QTableCornerButton::section {{ background: {c.raised}; border: none; }}
        QScrollArea {{ border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px 1px; }}
        QScrollBar::handle:vertical {{ background: {c.border}; border-radius: 4px; min-height: 32px; }}
        QScrollBar::handle:vertical:hover {{ background: {c.muted}; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 1px 3px; }}
        QScrollBar::handle:horizontal {{ background: {c.border}; border-radius: 4px; min-width: 32px; }}
        QScrollBar::handle:horizontal:hover {{ background: {c.muted}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QSplitter::handle {{ background: transparent; width: 12px; height: 12px; }}
        QSplitter::handle:hover {{ background: {c.tint}; border-radius: 5px; }}
        QMenu {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; padding: 5px; }}
        QMenu::item {{ padding: 7px 24px; border-radius: 5px; }}
        QMenu::item:selected {{ background: {c.tint}; color: {c.accent}; }}
        QToolTip {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; padding: 6px; }}
    """)
    return colors
