"""PySide6 campaign workbench. Network operations are explicit and cancellable."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path

from PySide6.QtCore import QSize, QSortFilterProxyModel, Qt, QThread, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cold_mailer.application.campaigns import CampaignService
from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Message, Sender, Status, ValidationError, identifier
from cold_mailer.infrastructure.ai import AIGenerator
from cold_mailer.infrastructure.contacts import load_contacts
from cold_mailer.infrastructure.dns import domain_health
from cold_mailer.infrastructure.legacy import read_legacy_accounts
from cold_mailer.infrastructure.smtp import SMTPTransport
from cold_mailer.settings import VERSION, Settings
from cold_mailer.ui.components import Card, field, icon, label, scroll_content
from cold_mailer.ui.models import MessageModel
from cold_mailer.ui.theme import DARK, THEME_MODES, apply_theme
from cold_mailer.ui.workers import Operation, Worker


class Window(QMainWindow):
    def __init__(self, application: Application) -> None:
        super().__init__()
        self.application = application
        self.store = application.store
        self.operation_thread: QThread | None = None
        self.worker: Worker | None = None
        self.current_message: Message | None = None
        self.dirty = False
        self.closing = False
        self.brief_timer = QTimer(self)
        self.brief_timer.setSingleShot(True)
        self.brief_timer.timeout.connect(self.scroll_to_brief)
        self.completion_timer = QTimer(self)
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self.finished)
        mode = self.store.preference("appearance.theme", "system")
        self.theme_mode = mode if mode in THEME_MODES else "system"
        self.setWindowTitle(f"Cold Mailer {VERSION}")
        self.setMinimumSize(960, 600)
        screen = self.screen().availableGeometry()
        self.resize(min(1320, screen.width() - 48), min(920, screen.height() - 72))
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 14)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.brand_icon = QLabel()
        self.brand_icon.setFixedSize(38, 38)
        header.addWidget(self.brand_icon)
        identity = QVBoxLayout()
        identity.setSpacing(2)
        identity.addWidget(label("OUTREACH WORKSPACE", "eyebrow", wrap=False))
        identity.addWidget(label("Cold Mailer", "brand"))
        header.addLayout(identity)
        header.addStretch()
        header.addWidget(label("Theme", "fieldLabel", wrap=False))
        self.theme_selector = self.theme_combo()
        self.theme_selector.setFixedWidth(126)
        header.addWidget(self.theme_selector)
        self.mode_badge = label("Offline workspace", "modeBadge", wrap=False)
        self.mode_badge.setFixedHeight(34)
        header.addWidget(self.mode_badge)
        self.live = QCheckBox("Live access")
        self.live.setToolTip(
            "Allow AI, SMTP, and DNS only for operations you explicitly request. Sending still requires confirmation."
        )
        self.live.setAccessibleName("Enable live AI, SMTP, and DNS access")
        self.live.setChecked(application.settings.network)
        self.live.toggled.connect(self.update_live_badge)
        header.addWidget(self.live)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("primaryTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        layout.addWidget(self.tabs, 1)
        self._campaign_tab()
        self._sender_tab()
        self._settings_tab()

        footer = QFrame()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 10, 0, 0)
        self.state = label("Ready \u00b7 offline authoring available", "muted")
        self.state.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer_layout.addWidget(self.state, 1)
        self.stop_button = self.button(
            "Stop operation", self.stop, footer_layout, kind="danger", glyph="stop"
        )
        self.stop_button.setEnabled(False)
        layout.addWidget(footer)
        self.refresh()
        self.select_campaign()
        self.apply_appearance()
        self.update_live_badge()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self.system_theme_changed)
        if application.recovered:
            self.state.setText(
                f"Recovered {application.recovered} uncertain attempt(s). Review outcomes before retrying."
            )

    def combo(self) -> QComboBox:
        result = QComboBox()
        result.setView(QListView())
        result.setMaxVisibleItems(8)
        result.setMinimumContentsLength(12)
        result.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        result.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        result.setMinimumHeight(40)
        return result

    def theme_combo(self) -> QComboBox:
        result = self.combo()
        result.setAccessibleName("Theme preference")
        for mode in THEME_MODES:
            result.addItem(mode.title(), mode)
        result.setCurrentIndex(result.findData(self.theme_mode))
        result.currentIndexChanged.connect(self.choose_theme)
        return result

    @Slot(int)
    def choose_theme(self, index: int) -> None:
        control = self.sender()
        if isinstance(control, QComboBox):
            self.set_theme(str(control.itemData(index)))

    def set_theme(self, mode: str) -> None:
        def save() -> None:
            if mode not in THEME_MODES:
                raise ValidationError("Choose System, Light, or Dark appearance.")
            self.store.save_preference("appearance.theme", mode)
            self.theme_mode = mode

        self.guard(save)
        self.apply_appearance()

    def apply_appearance(self) -> None:
        qt = QApplication.instance()
        if not isinstance(qt, QApplication):
            return
        self.colors = apply_theme(qt, self.theme_mode)
        for combo in (self.theme_selector, self.settings_theme):
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(self.theme_mode))
            combo.blockSignals(False)
        self.setProperty("resolvedTheme", "dark" if self.colors == DARK else "light")
        self.setWindowIcon(icon("mail", self.colors.accent))
        self.brand_icon.setPixmap(icon("mail", self.colors.accent).pixmap(36, 36))
        for button in self.findChildren(QAbstractButton):
            name = button.property("glyph")
            if name:
                color = (
                    self.colors.danger if button.property("kind") == "danger" else self.colors.text
                )
                if button.property("kind") == "primary":
                    color = "#211b42" if self.colors == DARK else "#ffffff"
                button.setIcon(icon(str(name), color))

    @Slot()
    def system_theme_changed(self) -> None:
        if self.theme_mode == "system":
            self.apply_appearance()

    def update_live_badge(self) -> None:
        self.mode_badge.setText(
            "Live access enabled" if self.live.isChecked() else "Offline workspace"
        )
        self.mode_badge.setProperty("live", self.live.isChecked())
        self.mode_badge.style().unpolish(self.mode_badge)
        self.mode_badge.style().polish(self.mode_badge)

    def button(
        self,
        text: str,
        callback: Callable[[], object],
        layout: QHBoxLayout | QVBoxLayout,
        *,
        kind: str = "secondary",
        glyph: str = "",
    ) -> QPushButton:
        result = QPushButton(text)
        result.setProperty("kind", kind)
        result.setProperty("glyph", glyph)
        result.setMinimumHeight(40)
        result.setIconSize(QSize(17, 17))
        result.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        result.clicked.connect(callback)
        layout.addWidget(result)
        return result

    def _campaign_tab(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.campaign = self.combo()
        self.campaign.setAccessibleName("Campaign")
        self.campaign.setPlaceholderText("Choose a campaign")
        self.campaign.currentIndexChanged.connect(self.select_campaign)
        toolbar.addWidget(self.campaign, 1)
        self.button("New campaign", self.new_campaign, toolbar, glyph="plus")
        self.button(
            "Import contacts", self.import_contacts, toolbar, kind="primary", glyph="import"
        )
        layout.addLayout(toolbar)

        scroll, _, content = scroll_content()
        self.campaign_scroll = scroll
        self.workspace = QSplitter(Qt.Orientation.Horizontal)
        self.workspace.setChildrenCollapsible(False)
        self.workspace.setMinimumHeight(390)
        left = Card("Recipients", "Every contact. Every revision. One clear delivery state.")
        left.setMinimumWidth(310)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search recipients, subjects, or states...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Filter messages")
        left.content.addWidget(self.search)
        self.model = MessageModel()
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.table = QTableView()
        self.table.setAccessibleName("Campaign recipients")
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(70)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.selectionModel().currentRowChanged.connect(self.select_message)
        self.message_stack = QStackedWidget()
        self.message_stack.addWidget(self.table)
        empty = QWidget()
        empty.setObjectName("emptyState")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(20, 22, 20, 22)
        empty_layout.addStretch()
        self.empty_title = label("Your next conversation starts here", "cardTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint = label("Create a campaign, then import a CSV or Excel contact list.")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_hint)
        empty_layout.addStretch()
        self.message_stack.addWidget(empty)
        left.content.addWidget(self.message_stack, 1)
        summary = QHBoxLayout()
        self.counts = label("0 contacts", "muted")
        summary.addWidget(self.counts, 1)
        self.approved_badge = label("0 approved", "badge", wrap=False)
        summary.addWidget(self.approved_badge)
        left.content.addLayout(summary)
        self.workspace.addWidget(left)

        self.editor = Card(
            "Message studio", "Review the exact message before approving a revision."
        )
        self.editor.setMinimumWidth(342)
        self.recipient = label("Choose a recipient from the list", "hint")
        self.editor.content.addWidget(self.recipient)
        self.subject = QLineEdit()
        self.subject.setAccessibleName("Message subject")
        self.subject.setPlaceholderText("A clear, personal subject line")
        self.editor.content.addWidget(field("Subject", self.subject))
        self.body = QPlainTextEdit()
        self.body.setAccessibleName("Final message body")
        self.body.setPlaceholderText("Your final message, including greeting and sign-off.")
        self.body.setMinimumHeight(126)
        self.editor.content.addWidget(field("Final message", self.body), 1)
        self.subject.textEdited.connect(self.mark_dirty)
        self.body.textChanged.connect(self.mark_dirty)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.save_draft_button = self.button("Save draft", self.save_draft, actions, glyph="save")
        self.approve_button = self.button(
            "Approve revision", self.approve, actions, kind="primary", glyph="check"
        )
        self.editor.content.addLayout(actions)
        self.button("Resolve uncertain outcome", self.reconcile, self.editor.content, kind="quiet")
        self.workspace.addWidget(self.editor)
        self.workspace.setStretchFactor(0, 3)
        self.workspace.setStretchFactor(1, 2)
        self.workspace.setSizes([700, 460])
        content.addWidget(self.workspace, 1)
        self.brief_tabs = QTabWidget()
        self.brief_tabs.setObjectName("briefTabs")
        self.brief_tabs.setMinimumHeight(200)
        brief = QWidget()
        brief_layout = QHBoxLayout(brief)
        brief_layout.setContentsMargins(0, 0, 0, 0)
        brief_layout.setSpacing(14)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Describe your offer and the facts the AI may use.")
        self.prompt.setAccessibleName("Campaign prompt")
        self.wrapper = QPlainTextEdit(
            "Hi {{ first_name }},\n\n{{ AI_GENERATED_BODY }}\n\nBest,\nYour Name"
        )
        self.wrapper.setAccessibleName("Email wrapper")
        brief_layout.addWidget(field("AI brief", self.prompt))
        brief_layout.addWidget(field("Message template", self.wrapper))
        self.brief_tabs.addTab(brief, "Brief and template")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setAccessibleName("Operation log")
        self.brief_tabs.addTab(self.log, "Activity log")
        self.brief_tabs.hide()
        content.addWidget(self.brief_tabs)
        layout.addWidget(scroll, 1)
        runbar = QHBoxLayout()
        runbar.setSpacing(8)
        self.button("Save campaign", self.save_campaign, runbar, glyph="save")
        self.button("Generate drafts", self.generate, runbar, glyph="spark")
        self.button("Dry run", self.dry_run, runbar)
        self.brief_toggle = self.button(
            "Brief and activity", self.toggle_brief, runbar, kind="quiet"
        )
        self.brief_toggle.setCheckable(True)
        self.brief_toggle.setToolTip("Expand the AI brief, message template, and operation log.")
        runbar.addStretch()
        self.button("Send approved", self.send, runbar, kind="primary", glyph="send")
        layout.addLayout(runbar)
        self.proxy.rowsInserted.connect(self.update_empty_state)
        self.proxy.rowsRemoved.connect(self.update_empty_state)
        self.proxy.modelReset.connect(self.update_empty_state)
        self.search.textChanged.connect(self.update_empty_state)
        self.tabs.addTab(page, "Campaigns")

    @Slot()
    def update_empty_state(self) -> None:
        populated = self.proxy.rowCount() > 0
        self.message_stack.setCurrentIndex(0 if populated else 1)
        if self.search.text():
            self.empty_title.setText("No matching recipients")
            self.empty_hint.setText("Try a different name, subject, or delivery state.")
        elif self.model.rowCount():
            self.empty_title.setText("No matching recipients")
            self.empty_hint.setText("Clear your search to see every contact.")
        else:
            self.empty_title.setText("Your next conversation starts here")
            self.empty_hint.setText("Create a campaign, then import a CSV or Excel contact list.")

    def toggle_brief(self) -> None:
        self.brief_tabs.setVisible(self.brief_toggle.isChecked())
        if self.brief_toggle.isChecked():
            self.brief_timer.start(0)

    @Slot()
    def scroll_to_brief(self) -> None:
        self.campaign_scroll.ensureWidgetVisible(self.brief_tabs)

    def _sender_tab(self) -> None:
        scroll, _, layout = scroll_content()
        intro = QHBoxLayout()
        intro.addWidget(label("Sender accounts", "cardTitle"))
        intro.addStretch()
        self.senders = self.combo()
        self.senders.setAccessibleName("Sender account")
        self.senders.setMinimumWidth(260)
        self.senders.currentIndexChanged.connect(self.select_sender)
        intro.addWidget(self.senders, 1)
        layout.addLayout(intro)
        grid = QGridLayout()
        grid.setSpacing(16)
        account = Card(
            "Account details", "Your password stays in your operating system's credential store."
        )
        self.sender_fields = {
            name: QLineEdit() for name in ("Email", "SMTP host", "Username", "Password")
        }
        placeholders = {
            "Email": "you@company.com",
            "SMTP host": "smtp.your-provider.com",
            "Username": "Usually your email address",
        }
        for name, control in self.sender_fields.items():
            control.setPlaceholderText(
                placeholders.get(name, "Leave blank to keep the saved password")
            )
            account.content.addWidget(field(name, control))
        self.sender_fields["Password"].setEchoMode(QLineEdit.EchoMode.Password)
        account_actions = QHBoxLayout()
        self.button("Save sender", self.save_sender, account_actions, kind="primary", glyph="save")
        self.button("New", self.new_sender, account_actions, glyph="plus")
        self.button("Delete", self.delete_sender, account_actions, kind="danger")
        account.content.addLayout(account_actions)
        controls = Card(
            "Delivery controls", "Keep your sending pace deliberate and your connection secure."
        )
        connection = QGridLayout()
        connection.setSpacing(14)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(587)
        self.tls = self.combo()
        self.tls.addItems(["starttls", "tls"])
        connection.addWidget(field("Port", self.port), 0, 0)
        connection.addWidget(field("Connection security", self.tls), 0, 1)
        controls.content.addLayout(connection)
        controls.content.addWidget(
            label("STARTTLS usually uses port 587. Implicit TLS (tls) usually uses 465.", "hint")
        )
        self.limit = QSpinBox()
        self.limit.setRange(1, 10000)
        self.limit.setValue(50)
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0, 86400)
        self.interval.setValue(30)
        controls.content.addWidget(field("Attempts per rolling 24 hours", self.limit))
        controls.content.addWidget(field("Seconds between attempts", self.interval))
        controls.content.addWidget(
            label(
                "Changing sender details clears pending approvals. Accepted and uncertain messages stay immutable.",
                "hint",
            )
        )
        controls.content.addStretch()
        self.button(
            "Import legacy accounts",
            self.import_legacy,
            controls.content,
            kind="quiet",
            glyph="import",
        )
        grid.addWidget(account, 0, 0)
        grid.addWidget(controls, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch()
        self.tabs.addTab(scroll, "Sender accounts")

    def _settings_tab(self) -> None:
        scroll, _, layout = scroll_content()
        layout.addWidget(label("Make this workspace yours", "cardTitle"))
        columns = QHBoxLayout()
        columns.setSpacing(16)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(16)
        right.setSpacing(16)
        appearance = Card(
            "Appearance",
            "Choose a comfortable workspace. Your preference is saved for this profile.",
        )
        self.settings_theme = self.theme_combo()
        appearance.content.addWidget(
            field(
                "Theme preference",
                self.settings_theme,
                "System follows your operating system's light or dark appearance.",
            )
        )
        left.addWidget(appearance)
        ai = Card(
            "AI configuration",
            "Use the model you choose. Generation always needs explicit live access.",
        )
        self.model_name = QLineEdit(self.store.preference("model", self.application.settings.model))
        self.model_name.setPlaceholderText("Enter your Gemini model ID")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Leave blank to keep the saved key")
        ai.content.addWidget(field("Gemini model", self.model_name))
        ai.content.addWidget(
            field(
                "Google API key",
                self.api_key,
                "Stored securely in your operating system's credential store.",
            )
        )
        ai_actions = QHBoxLayout()
        self.button("Save AI settings", self.save_ai, ai_actions, kind="primary", glyph="save")
        ai_actions.addStretch()
        ai.content.addLayout(ai_actions)
        left.addWidget(ai)
        left.addStretch()
        safety = Card("Recipient safeguards", "Keep addresses out of future campaign sends.")
        self.suppression = QLineEdit()
        self.suppression.setPlaceholderText("person@example.com")
        self.suppression.setAccessibleName("Suppression email address")
        safety.content.addWidget(field("Address to suppress", self.suppression))
        safety_actions = QHBoxLayout()
        self.button("Suppress address", self.suppress, safety_actions)
        safety_actions.addStretch()
        safety.content.addLayout(safety_actions)
        right.addWidget(safety)
        diagnostics = Card(
            "Domain health",
            "Check for SPF and DMARC records. Presence alone does not prove validity or delivery.",
        )
        self.domain = QLineEdit()
        self.domain.setPlaceholderText("company.com")
        self.domain.setAccessibleName("Domain to diagnose")
        diagnostics.content.addWidget(field("Domain", self.domain))
        dns_actions = QHBoxLayout()
        self.button("Check domain", self.check_domain, dns_actions)
        dns_actions.addStretch()
        diagnostics.content.addLayout(dns_actions)
        right.addWidget(diagnostics)
        backup = Card(
            "Your data, under your control",
            "Backups include campaigns and outcomes, but never passwords.",
        )
        self.button("Back up database", self.backup, backup.content, glyph="save")
        backup.content.addWidget(label(f"Version {VERSION} \u00b7 Local profile", "hint"))
        profile = label(str(self.application.settings.data_dir), "hint")
        profile.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        backup.content.addWidget(profile)
        right.addWidget(backup)
        right.addStretch()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        layout.addLayout(columns)
        layout.addStretch()
        self.tabs.addTab(scroll, "Settings")

    def guard(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except ValidationError as exc:
            QMessageBox.warning(self, "Check input", str(exc))
        except Exception:
            QMessageBox.warning(
                self,
                "Operation failed",
                "Storage or credentials could not be updated. Check your profile and permissions.",
            )

    def campaign_id(self) -> str:
        value = self.campaign.currentData()
        if not value:
            raise ValidationError("Create or select a campaign first.")
        return str(value)

    def refresh(self) -> None:
        current = self.campaign.currentData()
        self.campaign.blockSignals(True)
        self.campaign.clear()
        for row in self.store.campaigns():
            self.campaign.addItem(row["name"], row["id"])
        index = self.campaign.findData(current)
        self.campaign.setCurrentIndex(index if index >= 0 else (0 if self.campaign.count() else -1))
        self.campaign.blockSignals(False)
        self.senders.blockSignals(True)
        self.senders.clear()
        self.senders.addItem("New sender", None)
        for sender in self.store.senders():
            self.senders.addItem(sender.email, sender.id)
        self.senders.blockSignals(False)
        self.reload_messages()

    def reload_messages(self) -> None:
        campaign_id = self.campaign.currentData()
        messages = self.store.messages(str(campaign_id)) if campaign_id else []
        self.model.replace(messages)
        counts: dict[str, int] = {}
        for message in messages:
            counts[message.status.value] = counts.get(message.status.value, 0) + 1
        self.counts.setText(f"{len(messages)} contacts · {counts.get('accepted', 0)} accepted")
        self.approved_badge.setText(f"{counts.get('approved', 0)} approved")
        self.update_empty_state()
        self.current_message = None
        self.recipient.setText("Choose a recipient from the list")
        self.subject.clear()
        self.body.clear()
        self.subject.setReadOnly(True)
        self.body.setReadOnly(True)
        self.dirty = False

    def select_campaign(self) -> None:
        if (
            self.dirty
            and QMessageBox.question(self, "Unsaved edits", "Discard unsaved message edits?")
            != QMessageBox.StandardButton.Yes
        ):
            self.campaign.blockSignals(True)
            if self.current_message:
                self.campaign.setCurrentIndex(
                    self.campaign.findData(self.current_message.campaign_id)
                )
            self.campaign.blockSignals(False)
            return
        campaign_id = self.campaign.currentData()
        row = next((row for row in self.store.campaigns() if row["id"] == campaign_id), None)
        if row:
            self.prompt.setPlainText(row["prompt"])
            self.wrapper.setPlainText(row["wrapper"])
        self.reload_messages()

    def select_message(self) -> None:
        index = self.proxy.mapToSource(self.table.currentIndex())
        if not index.isValid():
            return
        if (
            self.dirty
            and QMessageBox.question(self, "Unsaved edits", "Discard unsaved message edits?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        message = self.model.messages[index.row()]
        self.current_message = message
        self.recipient.setText(
            f"{message.recipient} · {message.status.value} · revision {message.revision}"
        )
        self.subject.blockSignals(True)
        self.body.blockSignals(True)
        self.subject.setText(message.subject)
        self.body.setPlainText(message.body)
        self.subject.blockSignals(False)
        self.body.blockSignals(False)
        locked = message.status in {
            Status.ACCEPTED,
            Status.UNCERTAIN,
            Status.SENDING,
            Status.SUPPRESSED,
        }
        self.subject.setReadOnly(locked)
        self.body.setReadOnly(locked)
        self.dirty = False

    def mark_dirty(self) -> None:
        if self.current_message:
            self.dirty = (
                self.subject.text() != self.current_message.subject
                or self.body.toPlainText() != self.current_message.body
            )
            if self.dirty:
                self.state.setText("Unsaved message edits · save before approval")

    def new_campaign(self) -> None:
        name, accepted = QInputDialog.getText(self, "New campaign", "Campaign name")
        if accepted:

            def create() -> None:
                campaign_id = self.store.create_campaign(name, "", self.wrapper.toPlainText())
                self.refresh()
                self.campaign.setCurrentIndex(self.campaign.findData(campaign_id))
                self.select_campaign()

            self.guard(create)

    def save_campaign(self) -> None:
        self.guard(
            lambda: self.store.save_campaign(
                self.campaign_id(), self.prompt.toPlainText(), self.wrapper.toPlainText()
            )
        )

    def import_contacts(self) -> None:
        def prepare() -> None:
            campaign_id = self.campaign_id()
            senders = self.store.senders()
            if not senders:
                raise ValidationError("Add a sender account first.")
            selected, ok = QInputDialog.getItem(
                self,
                "Import contacts",
                "Sender for these messages",
                [f"{sender.email} · {sender.id}" for sender in senders]
                + (["Rotate across all sender accounts"] if len(senders) > 1 else []),
                0,
                False,
            )
            if not ok:
                return
            rotation = (
                [sender.id for sender in senders]
                if selected == "Rotate across all sender accounts"
                else None
            )
            sender_id = senders[0].id if rotation else selected.rsplit(" · ", 1)[1]
            path, _ = QFileDialog.getOpenFileName(
                self, "Import contacts", "", "Contacts (*.csv *.xlsx)"
            )
            if not path:
                return

            def operation(stop: object, emit: object) -> object:
                report = load_contacts(Path(path), self.store.suppressed())
                count = self.store.add_contacts(
                    campaign_id, sender_id, report.contacts, rotate=rotation
                )
                return {
                    "added": count,
                    "existing": len(report.contacts) - count,
                    "invalid_rows": [asdict(issue) for issue in report.issues],
                    "duplicates": report.duplicates,
                    "suppressed": report.suppressed,
                }

            self.start(operation)

        self.guard(prepare)

    def save_draft(self) -> None:
        def save() -> None:
            message = self.current_message
            if message is None:
                raise ValidationError("Select a message first.")
            self.store.edit(
                message.id, self.subject.text(), self.body.toPlainText(), message.revision
            )
            self.dirty = False
            self.reload_messages()

        self.guard(save)

    def approve(self) -> None:
        def approve() -> None:
            if self.dirty:
                raise ValidationError("Save message edits before approving this revision.")
            if self.current_message is None:
                raise ValidationError("Select a message first.")
            self.store.approve(self.current_message.id, self.current_message.revision)
            self.reload_messages()

        self.guard(approve)

    def dry_run(self) -> None:
        self.guard(
            lambda: self.log.appendPlainText(
                str(self.application.service.dry_run(self.campaign_id()))
            )
        )

    def network_settings(self) -> Settings:
        if not self.live.isChecked():
            raise ValidationError("Enable live mode explicitly to contact a provider.")
        return replace(
            self.application.settings,
            network=True,
            model=self.model_name.text().strip(),
            api_key=self.application.credentials.get("google-api-key")
            or self.application.settings.api_key,
        )

    def generate(self) -> None:
        def prepare() -> None:
            settings = self.network_settings()
            campaign_id = self.campaign_id()
            self.store.save_campaign(
                campaign_id, self.prompt.toPlainText(), self.wrapper.toPlainText()
            )
            self.start(
                lambda stop, emit: self.application.service.generate(
                    campaign_id, AIGenerator(settings), stop, emit
                )
            )

        self.guard(prepare)

    def send(self) -> None:
        def prepare() -> None:
            settings = self.network_settings()
            if self.dirty:
                raise ValidationError("Save or discard current edits before sending.")
            campaign_id = self.campaign_id()
            counts = self.application.service.dry_run(campaign_id)
            if (
                QMessageBox.question(
                    self,
                    "Confirm live campaign",
                    f"Submit only approved/eligible messages through SMTP?\n{counts}",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            service = CampaignService(
                self.store, self.application.credentials, SMTPTransport(settings)
            )
            self.start(lambda stop, emit: service.run(campaign_id, stop, emit))

        self.guard(prepare)

    def reconcile(self) -> None:
        def perform() -> None:
            if self.current_message is None or self.current_message.status != Status.UNCERTAIN:
                raise ValidationError("Select an uncertain message first.")
            outcome, ok = QInputDialog.getItem(
                self,
                "Reconcile provider evidence",
                "Only change this after checking provider acceptance",
                ["Confirmed accepted", "Confirmed not sent (return to draft)"],
                0,
                False,
            )
            if ok:
                self.store.reconcile(self.current_message.id, outcome == "Confirmed accepted")
                self.reload_messages()

        self.guard(perform)

    def select_sender(self) -> None:
        sender_id = self.senders.currentData()
        self.sender_fields["Password"].clear()
        if not sender_id:
            return
        sender = self.store.sender(str(sender_id))
        for name, value in {
            "Email": sender.email,
            "SMTP host": sender.host,
            "Username": sender.username,
        }.items():
            self.sender_fields[name].setText(value)
        self.port.setValue(sender.port)
        self.tls.setCurrentText(sender.tls)
        self.limit.setValue(sender.daily_limit)
        self.interval.setValue(sender.interval)

    def new_sender(self) -> None:
        self.senders.setCurrentIndex(0)
        for control in self.sender_fields.values():
            control.clear()

    def save_sender(self) -> None:
        def save() -> None:
            sender = Sender(
                str(self.senders.currentData() or identifier()),
                self.sender_fields["Email"].text().strip(),
                self.sender_fields["SMTP host"].text().strip(),
                self.port.value(),
                self.sender_fields["Username"].text().strip(),
                self.tls.currentText(),
                self.limit.value(),
                self.interval.value(),
            )
            sender.validate()
            password = self.sender_fields["Password"].text()
            if password:
                self.application.credentials.set(sender.id, password)
            elif not self.application.credentials.get(sender.id):
                raise ValidationError("Enter a password for this account.")
            self.store.save_sender(sender)
            self.sender_fields["Password"].clear()
            self.refresh()
            self.senders.setCurrentIndex(self.senders.findData(sender.id))

        self.guard(save)

    def delete_sender(self) -> None:
        def delete() -> None:
            sender_id = self.senders.currentData()
            if sender_id:
                self.store.delete_sender(str(sender_id))
                self.application.credentials.delete(str(sender_id))
                self.refresh()

        self.guard(delete)

    def import_legacy(self) -> None:
        def perform() -> None:
            database, _ = QFileDialog.getOpenFileName(
                self, "Choose legacy config.db", "", "SQLite (*.db)"
            )
            if not database:
                return
            key, _ = QFileDialog.getOpenFileName(
                self, "Choose existing secret.key", "", "Key (*.key)"
            )
            if not key:
                return
            accounts = read_legacy_accounts(Path(database), Path(key))
            for account in accounts:
                sender = Sender(
                    identifier(),
                    account.email,
                    account.smtp_server,
                    account.port,
                    account.username,
                    "tls" if account.port == 465 else "starttls",
                )
                sender.validate()
                self.application.credentials.set(sender.id, account.password)
                self.store.save_sender(sender)
            self.refresh()
            self.state.setText(
                f"Imported {len(accounts)} sender(s); legacy files were not modified. Rotate exposed credentials."
            )

        self.guard(perform)

    def save_ai(self) -> None:
        def save() -> None:
            if self.api_key.text():
                self.application.credentials.set("google-api-key", self.api_key.text())
            self.store.save_preference("model", self.model_name.text().strip())
            self.api_key.clear()
            self.state.setText("AI settings saved. Model selection remains explicit.")

        self.guard(save)

    def suppress(self) -> None:
        def perform() -> None:
            self.store.suppress(self.suppression.text())
            self.suppression.clear()
            self.reload_messages()

        self.guard(perform)

    def check_domain(self) -> None:
        def prepare() -> None:
            if not self.live.isChecked():
                raise ValidationError("Enable live mode to perform DNS lookups.")
            domain = self.domain.text().strip()
            if not domain or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
                for char in domain
            ):
                raise ValidationError("Enter a plain domain name.")
            self.start(lambda stop, emit: domain_health(domain))

        self.guard(prepare)

    def backup(self) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self, "New backup file (passwords excluded)", "", "SQLite (*.sqlite3)"
        )
        if destination:
            self.guard(lambda: self.start(lambda stop, emit: self.store.backup(Path(destination))))

    def start(self, operation: Operation) -> None:
        if self.operation_thread is not None:
            raise ValidationError("Wait for the current operation to finish.")
        self.brief_toggle.setChecked(True)
        self.brief_tabs.show()
        self.brief_tabs.setCurrentIndex(1)
        self.operation_thread = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.operation_thread)
        self.operation_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.log.appendPlainText)
        self.worker.failed.connect(self.log.appendPlainText)
        self.worker.result.connect(self.result)
        self.worker.finished.connect(self.operation_thread.quit)
        self.operation_thread.finished.connect(self.worker.deleteLater)
        self.operation_thread.finished.connect(self.finished)
        self.tabs.setEnabled(False)
        self.live.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.state.setText("Operation running · stop is available")
        self.operation_thread.start()

    @Slot(object)
    def result(self, value: object) -> None:
        self.log.appendPlainText(
            str(asdict(value) if is_dataclass(value) and not isinstance(value, type) else value)
        )

    @Slot()
    def finished(self) -> None:
        thread = self.operation_thread
        if thread is None:
            return
        # finished() can precede native/thread-local cleanup. Poll a zero-timeout
        # join before releasing wrappers or allowing the next operation/close.
        if not thread.wait(0):
            self.completion_timer.start(10)
            return
        self.worker = None
        self.operation_thread = None
        thread.deleteLater()
        self.tabs.setEnabled(True)
        self.live.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.state.setText("Operation finished · inspect per-message outcomes")
        self.reload_messages()
        if self.closing:
            self.close()

    def stop(self) -> None:
        if self.worker is not None:
            self.worker.stop.set()
            self.state.setText("Stopping · waiting for bounded in-flight work")
            self.stop_button.setEnabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.operation_thread is not None:
            self.closing = True
            self.stop()
            event.ignore()
        elif (
            self.dirty
            and QMessageBox.question(
                self, "Unsaved edits", "Discard unsaved message edits and close?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            event.ignore()
        else:
            event.accept()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cold Mailer desktop")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--development", action="store_true")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Open an isolated profile and exit without provider calls",
    )
    parser.add_argument(
        "--snapshot", type=Path, help="Save a UI snapshot during an explicit smoke test"
    )
    args = parser.parse_args(argv)
    if args.smoke_test and args.data_dir is None:
        parser.error("--smoke-test requires an explicit --data-dir")
    if args.snapshot and not args.smoke_test:
        parser.error("--snapshot requires --smoke-test")
    qt = QApplication.instance() or QApplication([])
    try:
        with Application(Settings.load(args.data_dir, development=args.development)) as application:
            window = Window(application)
            if not args.smoke_test:
                window.show()
            if args.smoke_test:
                if args.snapshot:
                    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
                    window.grab().save(str(args.snapshot))
                QTimer.singleShot(100, qt.quit)
            return qt.exec()
    except ValidationError as exc:
        if not args.smoke_test:
            QMessageBox.critical(None, "Cannot open profile", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
