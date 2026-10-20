"""Small, consistently sized presentation building blocks."""

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QLabel,
    QLayout,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def icon(name: str, color: str) -> QIcon:
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(
            QColor(color),
            1.6,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    if name == "mail":
        painter.drawRoundedRect(QRectF(2, 4, 16, 12), 2, 2)
        path = QPainterPath()
        path.moveTo(3, 5)
        path.lineTo(10, 11)
        path.lineTo(17, 5)
        painter.drawPath(path)
    elif name == "plus":
        painter.drawLine(QLineF(10, 4, 10, 16))
        painter.drawLine(QLineF(4, 10, 16, 10))
    elif name == "import":
        painter.drawLine(QLineF(10, 2, 10, 12))
        painter.drawLine(QLineF(6, 8, 10, 12))
        painter.drawLine(QLineF(14, 8, 10, 12))
        path = QPainterPath()
        path.moveTo(3, 12)
        path.lineTo(3, 17)
        path.lineTo(17, 17)
        path.lineTo(17, 12)
        painter.drawPath(path)
    elif name == "send":
        path = QPainterPath()
        path.moveTo(2, 3)
        path.lineTo(18, 10)
        path.lineTo(2, 17)
        path.lineTo(5, 10)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QLineF(5, 10, 13, 10))
    elif name == "spark":
        path = QPainterPath()
        for x, y in ((10, 2), (12, 8), (18, 10), (12, 12), (10, 18), (8, 12), (2, 10), (8, 8)):
            if path.isEmpty():
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "check":
        painter.drawLine(QLineF(4, 10, 8, 14))
        painter.drawLine(QLineF(8, 14, 16, 5))
    elif name == "save":
        painter.drawRoundedRect(QRectF(3, 3, 14, 14), 2, 2)
        painter.drawRect(QRectF(6, 3, 8, 5))
        painter.drawRect(QRectF(6, 12, 8, 5))
    elif name == "stop":
        painter.drawRoundedRect(QRectF(5, 5, 10, 10), 2, 2)
    painter.end()
    return QIcon(pixmap)


def label(text: str, role: str = "muted", *, wrap: bool = True) -> QLabel:
    result = QLabel(text)
    result.setObjectName(role)
    result.setWordWrap(wrap)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return result


class Card(QFrame):
    def __init__(self, title: str = "", description: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(18, 16, 18, 16)
        self.content.setSpacing(10)
        if title:
            self.content.addWidget(label(title, "cardTitle"))
        if description:
            self.content.addWidget(label(description, "muted"))


def field(title: str, control: QWidget, hint: str = "") -> QWidget:
    container = QWidget()
    container.setObjectName("field")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    if isinstance(control, (QLineEdit, QComboBox, QAbstractSpinBox)):
        control.setFixedHeight(40)
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    if isinstance(control, QAbstractSpinBox):
        control.lineEdit().setTextMargins(11, 0, 0, 0)
    title_label = label(title, "fieldLabel")
    title_label.setBuddy(control)
    control.setAccessibleName(control.accessibleName() or title)
    layout.addWidget(title_label)
    layout.addWidget(control)
    if hint:
        layout.addWidget(label(hint, "hint"))
    return container


def scroll_content() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setObjectName("pageScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    body = QWidget()
    body.setObjectName("page")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(0, 0, 8, 0)
    layout.setSpacing(16)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    scroll.setWidget(body)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return scroll, body, layout
