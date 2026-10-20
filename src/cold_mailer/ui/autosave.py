"""One bounded background draft write; Qt polls acknowledgments on its own thread."""

from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from cold_mailer.infrastructure.storage import Store


class DraftSaver(QObject):
    completed = Signal(str, object)
    campaign_completed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, store: Store, parent: QObject) -> None:
        super().__init__(parent)
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="draft-writer")
        self.future: Future[None] | None = None
        self.message_id = ""
        self.kind = "message"
        self.campaign_snapshot: tuple[str, str] = ("", "")
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.poll)

    def save(
        self, message_id: str, revision: int, subject: str, body: str, instructions: str
    ) -> bool:
        if self.future is not None:
            return False
        self.message_id = message_id
        self.kind = "message"
        self.future = self.executor.submit(
            self.store.save_draft,
            message_id,
            subject,
            body,
            revision,
            instructions=instructions,
            origin="autosave",
        )
        self.timer.start()
        return True

    def save_campaign(self, campaign_id: str, prompt: str, wrapper: str) -> bool:
        if self.future is not None:
            return False
        self.kind = "campaign"
        self.message_id = campaign_id
        self.campaign_snapshot = (prompt, wrapper)
        self.future = self.executor.submit(self.store.save_campaign, campaign_id, prompt, wrapper)
        self.timer.start()
        return True

    @Slot()
    def poll(self) -> None:
        future = self.future
        if future is None or not future.done():
            return
        self.future = None
        self.timer.stop()
        try:
            future.result()
            if self.kind == "campaign":
                self.campaign_completed.emit(self.message_id, self.campaign_snapshot)
            else:
                self.completed.emit(self.message_id, self.store.message(self.message_id))
        except Exception:
            self.failed.emit(
                self.message_id,
                ("Campaign changes" if self.kind == "campaign" else "Draft")
                + " could not be saved. Your edits remain in the editor; retry or copy them before closing.",
            )

    def shutdown(self) -> None:
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=False)
