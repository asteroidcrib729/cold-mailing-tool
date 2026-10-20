"""Stable-ID Qt table model, independent of table sort/selection positions."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt

from cold_mailer.domain.models import Message

EMPTY_INDEX = QModelIndex()


class MessageModel(QAbstractTableModel):
    columns = ("Recipient", "State", "Revision", "Subject")

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[Message] = []

    def replace(self, messages: list[Message]) -> None:
        self.beginResetModel()
        self.messages = messages
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = EMPTY_INDEX) -> int:
        return 0 if parent.isValid() else len(self.messages)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = EMPTY_INDEX) -> int:
        return len(self.columns)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        message = self.messages[index.row()]
        return (message.recipient, message.status.value, str(message.revision), message.subject)[
            index.column()
        ]

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section]
        return None
