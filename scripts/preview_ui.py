"""Capture every page/theme using temporary synthetic profiles and no providers."""

import argparse
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Sender
from cold_mailer.infrastructure.credentials import MemoryCredentials
from cold_mailer.settings import Settings
from cold_mailer.ui.window import Window


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/ui-preview"))
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=860)
    args = parser.parse_args()
    if args.width < 960 or args.height < 600:
        parser.error("Minimum logical preview size is 960 x 600.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    qt = QApplication([])
    results = []
    with (
        tempfile.TemporaryDirectory(prefix="cold-mailer-visual-") as directory,
        Application(Settings(Path(directory))) as app,
    ):
        app.credentials = MemoryCredentials()
        sender = Sender("preview", "jordan@example.com", "smtp.example.com", 587, "jordan")
        app.store.save_sender(sender)
        campaign = app.store.create_campaign(
            "Autumn partnerships",
            "Introduce our design workshop. Keep it personal and factual.",
            "Hi {{ first_name }},\n\n{{ AI_GENERATED_BODY }}\n\nBest,\nJordan",
        )
        names = ("Avery", "Morgan", "Taylor", "Riley", "Jamie", "Alex")
        app.store.add_contacts(
            campaign,
            sender.id,
            [
                {
                    "email": f"{names[index % 6].lower()}.{index + 1}@example.com",
                    "first_name": names[index % 6],
                }
                for index in range(24)
            ],
        )
        for index, message in enumerate(app.store.messages(campaign)):
            app.store.edit(
                message.id,
                f"A fresh perspective for {message.contact['first_name']}",
                f"Hi {message.contact['first_name']},\n\nI noticed your team's thoughtful approach to design. We run small, practical workshops that help teams turn early ideas into useful products.\n\nWould a brief introduction next week be useful?\n\nBest,\nJordan",
                message.revision,
            )
            if index % 3 == 0:
                current = app.store.message(message.id)
                app.store.approve(current.id, current.revision)
        window = Window(app)
        window.winId()
        window.resize(args.width, args.height)
        qt.processEvents()
        for mode in ("light", "dark"):
            window.set_theme(mode)
            for page in range(window.tabs.count()):
                window.tabs.setCurrentIndex(page)
                if page == 0:
                    window.table.setCurrentIndex(window.proxy.index(0, 0))
                    window.select_message()
                elif page == 1:
                    window.senders.setCurrentIndex(1)
                qt.processEvents()
                target = args.output_dir / f"{mode}-{page}-{args.width}x{args.height}.png"
                if not window.grab().save(str(target)):
                    raise RuntimeError("Preview could not be saved.")
                buttons = [
                    button
                    for button in window.findChildren(QPushButton)
                    if button.isVisibleTo(window)
                ]
                if any(button.height() < 38 for button in buttons):
                    raise RuntimeError("A visible button collapsed below its usable height.")
                results.append(
                    {
                        "theme": mode,
                        "page": window.tabs.tabText(page),
                        "size": [window.width(), window.height()],
                        "device_pixel_ratio": window.devicePixelRatioF(),
                        "buttons_fit": True,
                        "snapshot": target.name,
                    }
                )
        window.close()
        window.deleteLater()
        QTimer.singleShot(0, qt.quit)
        qt.exec()
    (args.output_dir / "results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Captured {len(results)} synthetic UI previews; no external providers were contacted.")


if __name__ == "__main__":
    main()
