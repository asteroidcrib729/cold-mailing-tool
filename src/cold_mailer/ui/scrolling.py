"""Animate coarse mouse wheels while preserving native touchpad pixel events."""

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QWidget,
)


class SmoothScroll(QObject):
    def __init__(self, area: QAbstractScrollArea) -> None:
        super().__init__(area)
        self.area = area
        self.enabled = True
        self.animation = QPropertyAnimation(area.verticalScrollBar(), b"value", self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        area.verticalScrollBar().sliderPressed.connect(self.animation.stop)
        self.target = area.verticalScrollBar().value()
        area.viewport().installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Wheel or not isinstance(event, QWheelEvent):
            if event.type() in {QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress}:
                self.animation.stop()
            return False
        if (
            not self.enabled
            or not event.pixelDelta().isNull()
            or event.modifiers() != Qt.KeyboardModifier.NoModifier
        ):
            self.animation.stop()
            return False
        delta = event.angleDelta()
        if not delta.y() or delta.x():
            return False
        bar = self.area.verticalScrollBar()
        current = (
            self.target
            if self.animation.state() == QPropertyAnimation.State.Running
            else bar.value()
        )
        desired = max(bar.minimum(), min(bar.maximum(), current - round(delta.y() / 120 * 84)))
        if desired == current:
            self.animation.stop()
            event.ignore()  # Qt routes an exhausted inner view to its parent.
            return False
        self.animation.stop()
        self.target = desired
        self.animation.setStartValue(bar.value())
        self.animation.setEndValue(desired)
        self.animation.start()
        event.accept()
        return True


class WheelGuard(QObject):
    """Scrolling over an unfocused numeric or choice field must not change it."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(watched, QWidget)
            and not watched.hasFocus()
        ):
            event.ignore()
            return True
        return False


def install_scrolling(root: QWidget) -> list[SmoothScroll]:
    for view in root.findChildren(QAbstractItemView):
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    controllers = [SmoothScroll(area) for area in root.findChildren(QAbstractScrollArea)]
    for control in [*root.findChildren(QAbstractSpinBox), *root.findChildren(QComboBox)]:
        guard = WheelGuard(control)
        control.installEventFilter(guard)
        control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return controllers
