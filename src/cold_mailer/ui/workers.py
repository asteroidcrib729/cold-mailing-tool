"""Qt-owned cancellable workers. All widget updates remain in the GUI thread."""

from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from cold_mailer.domain.models import ValidationError

Operation = Callable[[Event, Callable[[str], None]], object]


class Worker(QObject):
    progress = Signal(str)
    result = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, operation: Operation) -> None:
        super().__init__()
        self.operation = operation
        self.stop = Event()

    @Slot()
    def run(self) -> None:
        try:
            self.result.emit(self.operation(self.stop, self.progress.emit))
        except ValidationError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(
                "Operation failed. No further work was started; inspect persisted outcomes before retrying."
            )
        finally:
            self.finished.emit()
