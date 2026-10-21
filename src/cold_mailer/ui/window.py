"""PySide6 campaign workbench. Network operations are explicit and cancellable."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from PySide6.QtCore import QSize, QSortFilterProxyModel, Qt, QThread, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
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

from cold_mailer.application.campaigns import CampaignService, GenerationCandidate
from cold_mailer.application.review import quality_hints, reading_preview
from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Message, Sender, Status, ValidationError
from cold_mailer.infrastructure.ai import AIGenerator
from cold_mailer.infrastructure.backup import encrypted_backup
from cold_mailer.infrastructure.contacts import read_document
from cold_mailer.infrastructure.demo import DemoGenerator
from cold_mailer.infrastructure.dns import domain_health
from cold_mailer.infrastructure.doctor import diagnostics
from cold_mailer.infrastructure.feedback import PreparedFeedback
from cold_mailer.infrastructure.oauth_accounts import OAuthAccounts
from cold_mailer.infrastructure.oauth_mail import OAuthMailTransport
from cold_mailer.infrastructure.organization import Organization
from cold_mailer.infrastructure.support import support_preview, write_support_bundle
from cold_mailer.settings import VERSION, Settings
from cold_mailer.ui.autosave import DraftSaver
from cold_mailer.ui.components import Card, field, icon, label, scroll_content
from cold_mailer.ui.history import HistoryExported, HistoryPage
from cold_mailer.ui.imports import ContactImportDialog, PreparedImport
from cold_mailer.ui.models import MessageModel
from cold_mailer.ui.scrolling import install_scrolling
from cold_mailer.ui.theme import CONTRAST, DARK, THEME_MODES, apply_theme
from cold_mailer.ui.tools import CampaignTools
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
        self.campaign_dirty = False
        self.loaded_campaign: str | None = None
        self.campaign_snapshot: tuple[str, str] = ("", "")
        self.closing = False
        self.pending_close = False
        self.pending_operation: Operation | None = None
        self.pending_navigation: tuple[str, str] | None = None
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(800)
        self.autosave_timer.timeout.connect(self.autosave)
        self.max_save_timer = QTimer(self)
        self.max_save_timer.setSingleShot(True)
        self.max_save_timer.setInterval(5000)
        self.max_save_timer.timeout.connect(self.autosave)
        self.saver = DraftSaver(self.store, self)
        self.saver.completed.connect(self.draft_saved)
        self.saver.failed.connect(self.draft_failed)
        self.saver.campaign_completed.connect(self.campaign_saved)
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
        self.button("Commands", self.command_palette, header, kind="quiet")
        header.addWidget(label("Theme", "fieldLabel", wrap=False))
        self.theme_selector = self.theme_combo()
        self.theme_selector.setFixedWidth(150)
        header.addWidget(self.theme_selector)
        self.mode_badge = label("Offline workspace", "modeBadge", wrap=False)
        self.mode_badge.setFixedHeight(34)
        header.addWidget(self.mode_badge)
        self.live = QCheckBox("Live access")
        self.live.setToolTip(
            "Allow AI, account sign-in, email sending, and DNS only for operations you explicitly request. Sending still requires confirmation."
        )
        self.live.setAccessibleName(
            "Enable live AI, account sign-in, email sending, and DNS access"
        )
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
        self.history_page = HistoryPage(self.store, self.start)
        self.tabs.addTab(self.history_page, "History")
        self.tools_page = CampaignTools(
            self.store,
            self.campaign_id,
            self.selected_message,
            self.start,
            self.reload_messages,
            self.editor_ready,
        )
        self.tabs.addTab(self.tools_page, "Campaign tools")
        self.tabs.currentChanged.connect(self.tab_changed)
        self.scrollers = install_scrolling(self)
        self.update_scrolling()
        self.shortcuts = []
        for key, callback in (
            ("Ctrl+K", self.command_palette),
            ("Ctrl+S", self.save_draft),
            ("Ctrl+F", self.focus_search),
            ("F1", self.keyboard_help),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

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
                raise ValidationError("Choose System, Light, Dark, or Contrast appearance.")
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
        self.setProperty(
            "resolvedTheme",
            "contrast" if self.colors == CONTRAST else "dark" if self.colors == DARK else "light",
        )
        self.setWindowIcon(icon("mail", self.colors.accent))
        self.brand_icon.setPixmap(icon("mail", self.colors.accent).pixmap(36, 36))
        for button in self.findChildren(QAbstractButton):
            name = button.property("glyph")
            if name:
                color = (
                    self.colors.danger if button.property("kind") == "danger" else self.colors.text
                )
                if button.property("kind") == "primary":
                    color = "#211b42" if self.colors in (DARK, CONTRAST) else "#ffffff"
                button.setIcon(icon(str(name), color))

    @Slot()
    def system_theme_changed(self) -> None:
        if self.theme_mode == "system":
            self.apply_appearance()

    def update_live_badge(self) -> None:
        if self.application.demo:
            self.live.blockSignals(True)
            self.live.setChecked(False)
            self.live.blockSignals(False)
            self.live.setEnabled(False)
            self.mode_badge.setText("DEMO · no email transmission")
            return
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
        body_field = field("Final message", self.body)
        body_field.setMinimumHeight(172)
        self.editor.content.addWidget(body_field, 1)
        self.subject.textEdited.connect(self.mark_dirty)
        self.body.textChanged.connect(self.mark_dirty)
        self.instructions = QLineEdit()
        self.instructions.setPlaceholderText("Tone, focus, or recipient-specific preferences")
        self.instructions.textEdited.connect(self.mark_dirty)
        self.editor.content.addWidget(field("Recipient instructions", self.instructions))
        tools = QHBoxLayout()
        self.button("Preview", self.preview_message, tools, kind="quiet")
        self.button("Revisions", self.show_revisions, tools, kind="quiet")
        self.button("New candidate", self.regenerate, tools, kind="quiet")
        self.editor.content.addLayout(tools)
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
        self.prompt.textChanged.connect(self.mark_campaign_dirty)
        self.wrapper.textChanged.connect(self.mark_campaign_dirty)
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
            "Personal email account", "Sign in through your browser and approve sending access."
        )
        self.sender_email = QLineEdit()
        self.sender_email.setReadOnly(True)
        self.sender_email.setPlaceholderText("Sign in to select your email account")
        account.content.addWidget(field("Signed-in email", self.sender_email))
        self.sender_status = label("Choose Google Gmail or Microsoft Outlook to connect.", "hint")
        account.content.addWidget(self.sender_status)
        self.google_sign_in = self.button(
            "Sign in with Google",
            self.sign_in_google,
            account.content,
            kind="primary",
        )
        self.microsoft_sign_in = self.button(
            "Sign in with Microsoft",
            self.sign_in_microsoft,
            account.content,
            kind="primary",
        )
        self.google_sign_in.setEnabled(not self.application.demo)
        self.microsoft_sign_in.setEnabled(not self.application.demo)
        account_actions = QHBoxLayout()
        self.button("Add another", self.new_sender, account_actions, glyph="plus")
        self.button("Disconnect", self.disconnect_account, account_actions, kind="quiet")
        self.button("Delete", self.delete_sender, account_actions, kind="danger")
        account.content.addLayout(account_actions)
        controls = Card(
            "Sending controls", "Provider limits still apply to your connected personal account."
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
            "Save sending controls",
            self.save_sender,
            controls.content,
            kind="primary",
            glyph="save",
        )
        controls.content.addWidget(
            label(
                "Personal Gmail and Microsoft accounts only. Company, work and school accounts are not supported.",
                "hint",
            )
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
        behavior = Card(
            "Editing and motion",
            "Autosave stores messages and instructions, never passwords or API keys.",
        )
        self.autosave_toggle = QCheckBox("Automatically save message edits")
        self.autosave_toggle.setChecked(self.store.preference("editor.autosave", "true") == "true")
        self.smooth_toggle = QCheckBox("Smooth mouse-wheel scrolling")
        self.smooth_toggle.setChecked(self.store.preference("appearance.smooth", "true") == "true")
        self.motion_toggle = QCheckBox("Reduce motion (disable scroll animation)")
        self.motion_toggle.setChecked(
            self.store.preference("appearance.reduce_motion", "false") == "true"
        )
        self.jitter_toggle = QCheckBox("Add a random 0–1 second delay after each send")
        self.jitter_toggle.setChecked(self.store.preference("pacing.jitter", "true") == "true")
        for toggle in (
            self.autosave_toggle,
            self.smooth_toggle,
            self.motion_toggle,
            self.jitter_toggle,
        ):
            toggle.toggled.connect(self.save_behavior)
            behavior.content.addWidget(toggle)
        behavior.content.addWidget(
            label(
                "Pacing preserves your account interval. Random timing does not guarantee acceptance or prevent blocking.",
                "hint",
            )
        )
        left.addWidget(behavior)
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
        self.button("Create encrypted backup", self.backup_encrypted, backup.content)
        self.button("Local runtime doctor", self.show_doctor, backup.content)
        self.button("Preview support bundle", self.support_bundle, backup.content)
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
        if self.dirty or self.saver.future is not None:
            return
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
        self.instructions.clear()
        self.instructions.setReadOnly(True)
        self.subject.setReadOnly(True)
        self.body.setReadOnly(True)
        self.dirty = False

    def select_campaign(self) -> None:
        if self.saver.future is not None or (
            (self.dirty or self.campaign_dirty) and self.autosave_toggle.isChecked()
        ):
            target = self.campaign.currentData()
            if target and self.loaded_campaign and target != self.loaded_campaign:
                self.pending_navigation = ("campaign", str(target))
            self.autosave()
            if self.loaded_campaign:
                self.campaign.blockSignals(True)
                self.campaign.setCurrentIndex(self.campaign.findData(self.loaded_campaign))
                self.campaign.blockSignals(False)
            return
        if (self.dirty or self.campaign_dirty) and not self.confirm_unsaved():
            self.campaign.blockSignals(True)
            if self.loaded_campaign:
                self.campaign.setCurrentIndex(self.campaign.findData(self.loaded_campaign))
            self.campaign.blockSignals(False)
            return
        if self.current_message:
            self.store.release_edit(self.current_message.id)
        self.dirty = False
        self.autosave_timer.stop()
        self.max_save_timer.stop()
        campaign_id = self.campaign.currentData()
        row = next((row for row in self.store.campaigns() if row["id"] == campaign_id), None)
        if row:
            self.prompt.blockSignals(True)
            self.wrapper.blockSignals(True)
            self.prompt.setPlainText(row["prompt"])
            self.wrapper.setPlainText(row["wrapper"])
            self.prompt.blockSignals(False)
            self.wrapper.blockSignals(False)
            self.loaded_campaign = str(campaign_id)
            self.campaign_snapshot = (row["prompt"], row["wrapper"])
            self.campaign_dirty = False
        self.reload_messages()

    def select_message(self) -> None:
        index = self.proxy.mapToSource(self.table.currentIndex())
        if not index.isValid():
            return
        target_id = self.model.messages[index.row()].id
        if self.saver.future is not None or (self.dirty and self.autosave_toggle.isChecked()):
            if self.current_message is None or target_id != self.current_message.id:
                self.pending_navigation = ("message", target_id)
            self.autosave()
            self.restore_editor_selection()
            return
        if self.dirty and not self.confirm_unsaved():
            self.restore_editor_selection()
            return
        if self.current_message:
            self.store.release_edit(self.current_message.id)
        message = self.store.message(target_id)
        self.current_message = message
        self.recipient.setText(
            f"{message.recipient} · {message.status.value} · revision {message.revision}"
        )
        self.subject.blockSignals(True)
        self.body.blockSignals(True)
        self.subject.setText(message.subject)
        self.body.setPlainText(message.body)
        self.instructions.setText(message.instructions)
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
        self.instructions.setReadOnly(locked)
        self.dirty = False

    def mark_dirty(self) -> None:
        if self.current_message:
            self.dirty = (
                self.subject.text() != self.current_message.subject
                or self.body.toPlainText() != self.current_message.body
                or self.instructions.text() != self.current_message.instructions
            )
            if self.dirty:
                try:
                    held = self.store.hold_edit(self.current_message.id)
                except Exception:
                    self.state.setText(
                        "Unable to register this edit. Copy your changes and check storage before continuing."
                    )
                    return
                if not held:
                    self.subject.setReadOnly(True)
                    self.body.setReadOnly(True)
                    self.instructions.setReadOnly(True)
                    self.state.setText(
                        "This revision was claimed before editing. Copy your changes and reload; the sent snapshot cannot be changed."
                    )
                    return
                self.state.setText("Unsaved message edits · save before approval")
                if self.autosave_toggle.isChecked():
                    self.autosave_timer.start()
                    if not self.max_save_timer.isActive():
                        self.max_save_timer.start()
            else:
                self.store.release_edit(self.current_message.id)

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
        def save() -> None:
            if self.saver.future is not None:
                raise ValidationError("Wait for the current save to finish.")
            self.store.save_campaign(
                self.loaded_campaign or self.campaign_id(),
                self.prompt.toPlainText(),
                self.wrapper.toPlainText(),
            )
            self.campaign_snapshot = (self.prompt.toPlainText(), self.wrapper.toPlainText())
            self.campaign_dirty = False

        self.guard(save)

    @Slot()
    def mark_campaign_dirty(self) -> None:
        if self.loaded_campaign is None:
            return
        self.campaign_dirty = (
            self.prompt.toPlainText(),
            self.wrapper.toPlainText(),
        ) != self.campaign_snapshot
        if self.campaign_dirty:
            self.state.setText("Unsaved campaign brief / template changes")
            if self.autosave_toggle.isChecked():
                self.autosave_timer.start()
                if not self.max_save_timer.isActive():
                    self.max_save_timer.start()

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

            self.start(
                lambda stop, emit: PreparedImport(
                    Path(path), read_document(Path(path)), campaign_id, sender_id, rotation
                )
            )

        self.guard(prepare)

    def save_draft(self) -> None:
        def save() -> None:
            message = self.current_message
            if message is None:
                raise ValidationError("Select a message first.")
            if self.saver.future is not None:
                raise ValidationError("A draft save is already in progress.")
            self.store.save_draft(
                message.id,
                self.subject.text(),
                self.body.toPlainText(),
                message.revision,
                instructions=self.instructions.text(),
            )
            self.autosave_timer.stop()
            self.max_save_timer.stop()
            self.store.release_edit(message.id)
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
            if self.saver.future is not None:
                raise ValidationError("Wait for the pending save before generating drafts.")
            settings = None if self.application.demo else self.network_settings()
            campaign_id = self.campaign_id()
            self.store.save_campaign(
                campaign_id, self.prompt.toPlainText(), self.wrapper.toPlainText()
            )
            self.campaign_snapshot = (self.prompt.toPlainText(), self.wrapper.toPlainText())
            self.campaign_dirty = False
            self.start(
                lambda stop, emit: self.application.service.generate(
                    campaign_id,
                    DemoGenerator() if settings is None else AIGenerator(settings),
                    stop,
                    emit,
                )
            )

        self.guard(prepare)

    def send(self) -> None:
        def prepare() -> None:
            settings = None if self.application.demo else self.mail_settings()
            if self.dirty:
                raise ValidationError("Save or discard current edits before sending.")
            campaign_id = self.campaign_id()
            counts = self.application.service.dry_run(campaign_id)
            selected_ids = [
                self.model.messages[self.proxy.mapToSource(self.proxy.index(row, 0)).row()].id
                for row in range(self.proxy.rowCount())
            ]
            scope = f"Frozen audience: {len(selected_ids)} visible recipients. Later filter, approval or revision changes cannot expand this run."
            if (
                QMessageBox.question(
                    self,
                    "Confirm demo rehearsal" if settings is None else "Confirm live campaign",
                    f"Simulate approved messages with NO transmission?\n{scope}\nCampaign totals: {counts}"
                    if settings is None
                    else f"Submit only approved/eligible messages through your signed-in Google or Microsoft account?\n{scope}\nCampaign totals: {counts}",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            service = (
                self.application.service
                if settings is None
                else CampaignService(
                    self.store,
                    self.application.credentials,
                    OAuthMailTransport(
                        settings, OAuthAccounts(settings, self.store, self.application.credentials)
                    ),
                )
            )
            run_id = Organization(self.store).freeze(campaign_id, selected_ids)
            self.start(lambda stop, emit: service.run(campaign_id, stop, emit, run_id=run_id))

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
        if not sender_id:
            self.sender_email.clear()
            self.sender_status.setText("Choose Google Gmail or Microsoft Outlook to connect.")
            return
        sender = self.store.sender(str(sender_id))
        self.sender_email.setText(sender.email)
        self.sender_status.setText(
            OAuthAccounts(
                self.application.settings, self.store, self.application.credentials
            ).status(sender)
        )
        self.limit.setValue(sender.daily_limit)
        self.interval.setValue(sender.interval)

    def new_sender(self) -> None:
        self.senders.setCurrentIndex(0)
        self.select_sender()

    def mail_settings(self) -> Settings:
        if not self.live.isChecked() or self.application.demo:
            raise ValidationError("Enable live mode explicitly to sign in or send email.")
        return replace(self.application.settings, network=True)

    def connect_account(self, provider: str) -> None:
        def prepare() -> None:
            settings = self.mail_settings()
            sender_id = self.senders.currentData()
            accounts = OAuthAccounts(settings, self.store, self.application.credentials)
            self.start(
                lambda stop, emit: accounts.connect(
                    provider, stop, str(sender_id) if sender_id else None
                )
            )

        self.guard(prepare)

    @Slot()
    def sign_in_google(self) -> None:
        self.connect_account("google")

    @Slot()
    def sign_in_microsoft(self) -> None:
        self.connect_account("microsoft")

    def disconnect_account(self) -> None:
        def disconnect() -> None:
            sender_id = self.senders.currentData()
            if not sender_id:
                raise ValidationError("Select a connected account first.")
            OAuthAccounts(
                self.application.settings, self.store, self.application.credentials
            ).disconnect(str(sender_id))
            self.select_sender()
            self.reload_messages()
            self.state.setText(
                "Account disconnected locally. Sign in again before sending; provider consent can also be removed in your account settings."
            )

        self.guard(disconnect)

    def save_sender(self) -> None:
        def save() -> None:
            sender_id = self.senders.currentData()
            if not sender_id:
                raise ValidationError("Sign in with Google or Microsoft to add a sender.")
            sender = self.store.sender(str(sender_id))
            if not sender.provider and not self.application.demo:
                raise ValidationError(
                    "Sign in to reconnect this legacy sender before changing its controls."
                )
            sender = replace(sender, daily_limit=self.limit.value(), interval=self.interval.value())
            self.store.save_sender(sender)
            self.refresh()
            self.senders.setCurrentIndex(self.senders.findData(sender.id))

        self.guard(save)

    def delete_sender(self) -> None:
        def delete() -> None:
            sender_id = self.senders.currentData()
            if sender_id:
                self.store.delete_sender(str(sender_id))
                OAuthAccounts(
                    self.application.settings, self.store, self.application.credentials
                ).secrets.delete(str(sender_id))
                self.application.credentials.delete(str(sender_id))
                self.refresh()

        self.guard(delete)

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
        for index in (0, 1):
            page = self.tabs.widget(index)
            if page is not None:
                page.setEnabled(False)
        self.live.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.state.setText("Operation running · stop is available")
        self.operation_thread.start()

    @Slot(object)
    def result(self, value: object) -> None:
        if isinstance(value, Sender):
            self.refresh()
            self.senders.setCurrentIndex(self.senders.findData(value.id))
            self.select_sender()
            self.log.appendPlainText(
                "Personal account connected. Review and approve each message before sending."
            )
            return
        if isinstance(value, HistoryExported):
            self.history_page.count.setText(
                f"Exported {value.count} attempts. Treat this file as private."
            )
            return
        if isinstance(value, PreparedFeedback):
            if not self.closing and not (self.worker is not None and self.worker.stop.is_set()):
                self.tools_page.receive(value)
            return
        if isinstance(value, PreparedImport):
            if self.closing or (self.worker is not None and self.worker.stop.is_set()):
                return
            dialog = ContactImportDialog(value, self.store, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                mapping, source = dialog.mapping(), dialog.source()

                def perform(stop: object, emit: object) -> object:
                    document = read_document(value.path, expected_sha256=value.document.sha256)
                    report = document.parse(mapping, self.store.suppressed())
                    if isinstance(stop, Event) and stop.is_set():
                        return {"cancelled": True}
                    count = self.store.add_contacts(
                        value.campaign_id,
                        value.sender_id,
                        report.contacts,
                        rotate=value.rotation,
                        source=source,
                    )
                    return {
                        "added": count,
                        "existing": len(report.contacts) - count,
                        "invalid_rows": [asdict(issue) for issue in report.issues],
                        "duplicates": report.duplicates,
                        "suppressed": report.suppressed,
                    }

                if self.operation_thread is None:
                    self.start(perform)
                else:
                    self.pending_operation = perform
            dialog.deleteLater()
            return
        if isinstance(value, GenerationCandidate):
            dialog = QDialog(self)
            dialog.setWindowTitle("Generated candidate · current draft is preserved until accepted")
            dialog.resize(700, 500)
            layout = QVBoxLayout(dialog)
            preview = QPlainTextEdit(value.subject + "\n\n" + value.body)
            preview.setReadOnly(True)
            layout.addWidget(preview)
            self.button(
                "Use this candidate as an unapproved draft", dialog.accept, layout, kind="primary"
            )
            self.button("Keep my current draft", dialog.reject, layout)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.guard(
                    lambda: self.store.edit(
                        value.message_id, value.subject, value.body, value.revision
                    )
                )
            return
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
        for index in (0, 1):
            page = self.tabs.widget(index)
            if page is not None:
                page.setEnabled(True)
        self.live.setEnabled(not self.application.demo)
        self.stop_button.setEnabled(False)
        self.state.setText("Operation finished · inspect per-message outcomes")
        self.reload_messages()
        if self.closing:
            self.close()
        elif self.pending_operation is not None:
            operation, self.pending_operation = self.pending_operation, None
            self.start(operation)

    def stop(self) -> None:
        if self.worker is not None:
            self.worker.stop.set()
            self.state.setText("Stopping · waiting for bounded in-flight work")
            self.stop_button.setEnabled(False)

    def restore_editor_selection(self) -> None:
        if self.current_message:
            for row, message in enumerate(self.model.messages):
                if message.id == self.current_message.id:
                    selection = self.table.selectionModel()
                    selection.blockSignals(True)
                    self.table.setCurrentIndex(self.proxy.mapFromSource(self.model.index(row, 0)))
                    selection.blockSignals(False)
                    break

    @Slot()
    def autosave(self) -> None:
        message = self.current_message
        if self.saver.future is None and not self.dirty and self.campaign_dirty:
            self.queue_campaign_save()
            return
        if not self.dirty or message is None or self.saver.future is not None:
            return
        self.autosave_timer.stop()
        self.max_save_timer.stop()
        if self.saver.save(
            message.id,
            message.revision,
            self.subject.text(),
            self.body.toPlainText(),
            self.instructions.text(),
        ):
            self.state.setText("Saving draft…")

    @Slot(str, object)
    def draft_saved(self, message_id: str, message: Message) -> None:
        if self.current_message is not None and self.current_message.id == message_id:
            self.current_message = message
            self.dirty = (
                self.subject.text(),
                self.body.toPlainText(),
                self.instructions.text(),
            ) != (message.subject, message.body, message.instructions)
            self.state.setText(
                "Unsaved edits · another save queued"
                if self.dirty
                else "Draft saved · approval required"
            )
            if self.dirty:
                self.store.hold_edit(message_id)
                if self.autosave_toggle.isChecked():
                    self.autosave_timer.start()
            else:
                self.store.release_edit(message_id)
                self.max_save_timer.stop()
                self.autosave_timer.stop()
        if self.pending_close:
            self.close()
        elif self.campaign_dirty and self.autosave_toggle.isChecked():
            self.queue_campaign_save()
        elif not self.dirty and not self.campaign_dirty:
            self.apply_pending_navigation()

    def queue_campaign_save(self) -> None:
        if self.loaded_campaign and self.saver.save_campaign(
            self.loaded_campaign, self.prompt.toPlainText(), self.wrapper.toPlainText()
        ):
            self.autosave_timer.stop()
            self.max_save_timer.stop()
            self.state.setText("Saving campaign changes…")

    @Slot(str, object)
    def campaign_saved(self, campaign_id: str, snapshot: tuple[str, str]) -> None:
        if campaign_id == self.loaded_campaign:
            self.campaign_snapshot = snapshot
            self.campaign_dirty = (
                self.prompt.toPlainText(),
                self.wrapper.toPlainText(),
            ) != snapshot
            self.state.setText(
                "Campaign changes saved"
                if not self.campaign_dirty
                else "More campaign edits are waiting to save"
            )
        if self.pending_close:
            self.close()
        elif (self.dirty or self.campaign_dirty) and self.autosave_toggle.isChecked():
            self.autosave_timer.start()
            self.max_save_timer.start()
        elif not self.dirty and not self.campaign_dirty:
            self.apply_pending_navigation()

    @Slot(str, str)
    def draft_failed(self, message_id: str, error: str) -> None:
        self.pending_close = False
        self.pending_navigation = None
        self.state.setText(error)
        self.autosave_timer.stop()
        self.max_save_timer.stop()

    def apply_pending_navigation(self) -> None:
        pending, self.pending_navigation = self.pending_navigation, None
        if pending is None:
            return
        kind, target = pending
        if kind == "campaign":
            index = self.campaign.findData(target)
            if index >= 0:
                self.campaign.setCurrentIndex(index)
        else:
            for row, message in enumerate(self.model.messages):
                if message.id == target:
                    index = self.proxy.mapFromSource(self.model.index(row, 0))
                    if index.isValid():
                        self.table.setCurrentIndex(index)
                        if self.current_message is None or self.current_message.id != target:
                            self.select_message()
                    return

    def confirm_unsaved(self) -> bool:
        decision = QMessageBox.question(
            self,
            "Unsaved draft",
            "Save this draft before leaving?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if decision == QMessageBox.StandardButton.Save:
            if self.dirty:
                self.save_draft()
            if self.campaign_dirty:
                self.save_campaign()
            return not self.dirty and not self.campaign_dirty
        if decision == QMessageBox.StandardButton.Discard:
            if self.current_message:
                self.store.release_edit(self.current_message.id)
            self.dirty = False
            self.campaign_dirty = False
            self.prompt.blockSignals(True)
            self.wrapper.blockSignals(True)
            self.prompt.setPlainText(self.campaign_snapshot[0])
            self.wrapper.setPlainText(self.campaign_snapshot[1])
            self.prompt.blockSignals(False)
            self.wrapper.blockSignals(False)
            self.autosave_timer.stop()
            self.max_save_timer.stop()
            return True
        return False

    @Slot()
    def save_behavior(self) -> None:
        def save() -> None:
            for key, toggle in (
                ("editor.autosave", self.autosave_toggle),
                ("appearance.smooth", self.smooth_toggle),
                ("appearance.reduce_motion", self.motion_toggle),
                ("pacing.jitter", self.jitter_toggle),
            ):
                self.store.save_preference(key, "true" if toggle.isChecked() else "false")

        self.guard(save)
        self.update_scrolling()
        if self.autosave_toggle.isChecked() and (self.dirty or self.campaign_dirty):
            self.autosave_timer.start()
        elif not self.autosave_toggle.isChecked():
            self.autosave_timer.stop()
            self.max_save_timer.stop()

    def update_scrolling(self) -> None:
        for scroller in getattr(self, "scrollers", []):
            scroller.enabled = self.smooth_toggle.isChecked() and not self.motion_toggle.isChecked()
            if not scroller.enabled:
                scroller.animation.stop()

    @Slot(int)
    def tab_changed(self, index: int) -> None:
        if hasattr(self, "history_page") and self.tabs.widget(index) is self.history_page:
            self.history_page.refresh()

    def focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.search.setFocus()

    def keyboard_help(self) -> None:
        QMessageBox.information(
            self,
            "Keyboard shortcuts",
            "Ctrl+K  Command palette\nCtrl+S  Save draft\nCtrl+F  Find recipients\nF1  Keyboard help\nTab / Shift+Tab  Move between controls",
        )

    def command_palette(self) -> None:
        choices = [
            "Find recipients",
            "Open sender accounts",
            "Open settings",
            "Open history",
            "Preview current message",
            "Review saved revisions",
            "Keyboard help",
            "Save campaign blueprint",
            "Create campaign from blueprint",
            "Save current recipient filter",
            "Open saved recipient filter",
            "Insert template variable",
            "Setup checklist",
            "Local runtime doctor",
            "Preview support bundle",
            "Open campaign tools",
        ]
        choice, ok = QInputDialog.getItem(
            self, "Command palette", "Choose a safe workspace action", choices, 0, True
        )
        if not ok:
            return
        actions = {
            choices[0]: self.focus_search,
            choices[1]: lambda: self.tabs.setCurrentIndex(1),
            choices[2]: lambda: self.tabs.setCurrentIndex(2),
            choices[3]: lambda: self.tabs.setCurrentWidget(self.history_page),
            choices[4]: self.preview_message,
            choices[5]: self.show_revisions,
            choices[6]: self.keyboard_help,
            choices[7]: self.save_blueprint,
            choices[8]: self.use_blueprint,
            choices[9]: self.save_view,
            choices[10]: self.open_view,
            choices[11]: self.insert_variable,
            choices[12]: self.setup_checklist,
            choices[13]: self.show_doctor,
            choices[14]: self.support_bundle,
            choices[15]: lambda: self.tabs.setCurrentWidget(self.tools_page),
        }
        if choice in actions:
            actions[choice]()

    def text_dialog(self, title: str, text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(720, 500)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        layout.addWidget(view)
        dialog.exec()

    def show_doctor(self) -> None:
        self.text_dialog("Local runtime doctor · read-only", json.dumps(diagnostics(), indent=2))

    def setup_checklist(self) -> None:
        senders = self.store.senders()
        rows = (
            self.store.messages(str(self.campaign.currentData()))
            if self.campaign.currentData()
            else []
        )
        self.text_dialog(
            "Setup checklist",
            "\n".join(
                (
                    f"{'✓' if senders else '○'} Sender account: configure under Sender accounts.",
                    f"{'✓' if self.model_name.text().strip() else '○'} AI model: choose under Settings.",
                    f"{'✓' if rows else '○'} Recipients: import a CSV or XLSX into a campaign.",
                    f"{'✓' if any(row.body for row in rows) else '○'} Drafts: generate or write individual messages.",
                    f"{'✓' if any(row.approval for row in rows) else '○'} Review: save and explicitly approve each revision.",
                    "Rehearse without accounts using cold-mailer-desktop --demo.",
                    "Credentials are checked when you request a provider operation. This checklist does not test them or guarantee delivery.",
                )
            ),
        )

    def support_bundle(self) -> None:
        preview = json.dumps(support_preview(), indent=2)
        self.text_dialog("Review exact support-bundle contents", preview)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save reviewed diagnostics locally", "", "ZIP (*.zip)"
        )
        if path:
            self.guard(lambda: write_support_bundle(Path(path)))

    def backup_encrypted(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "New encrypted backup · keep the passphrase separately",
            "",
            "Encrypted backup (*.cmbak)",
        )
        if not path:
            return
        passphrase, ok = QInputDialog.getText(
            self,
            "Encrypt backup",
            "Passphrase (12+ characters). Lost passphrases cannot be recovered.",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        confirmation, ok = QInputDialog.getText(
            self,
            "Confirm backup passphrase",
            "Re-enter the passphrase",
            QLineEdit.EchoMode.Password,
        )
        if not ok or confirmation != passphrase:
            self.state.setText("Backup cancelled: passphrases did not match.")
            return
        self.guard(
            lambda: self.start(
                lambda stop, emit: encrypted_backup(self.store, Path(path), passphrase)
            )
        )

    def save_blueprint(self) -> None:
        name, ok = QInputDialog.getText(self, "Save a new blueprint version", "Blueprint name")
        if ok:
            self.guard(
                lambda: self.store.save_blueprint(
                    name, self.prompt.toPlainText(), self.wrapper.toPlainText()
                )
            )

    def use_blueprint(self) -> None:
        rows = self.store.blueprints()
        if not rows:
            self.state.setText("Save a campaign blueprint first using Ctrl+K.")
            return
        names = [f"{row['name']} · version {row['version']}" for row in rows]
        selected, ok = QInputDialog.getItem(
            self,
            "Choose blueprint",
            "Review the recipe before generating any messages",
            names,
            0,
            False,
        )
        if not ok or selected not in names:
            return
        row = rows[names.index(selected)]
        self.text_dialog(
            "Blueprint recipe · review supplied facts",
            str(row["prompt"]) + "\n\n" + str(row["wrapper"]),
        )
        name, ok = QInputDialog.getText(self, "New campaign from blueprint", "Campaign name")
        if ok:

            def create() -> None:
                key = self.store.create_campaign(name, str(row["prompt"]), str(row["wrapper"]))
                self.refresh()
                self.campaign.setCurrentIndex(self.campaign.findData(key))

            self.guard(create)

    def save_view(self) -> None:
        name, ok = QInputDialog.getText(self, "Save recipient view", "View name")
        if ok and name.strip():

            def save() -> None:
                views = json.loads(self.store.preference("views", "{}"))
                views[name.strip()] = self.search.text()
                self.store.save_preference("views", json.dumps(views))

            self.guard(save)

    def open_view(self) -> None:
        def load() -> None:
            views = json.loads(self.store.preference("views", "{}"))
            if not views:
                self.state.setText("Save a recipient filter using Ctrl+K first.")
                return
            name, ok = QInputDialog.getItem(
                self,
                "Saved recipient filters",
                "Filter the visible list. Sending freezes this view's approved revisions.",
                sorted(views),
                0,
                False,
            )
            if ok and name in views:
                self.focus_search()
                self.search.setText(views[name])

        self.guard(load)

    def insert_variable(self) -> None:
        fields = set(self.current_message.contact if self.current_message else ())
        fields.add("AI_GENERATED_BODY")
        chosen, ok = QInputDialog.getItem(
            self,
            "Template variable dictionary",
            "Insert a field into the campaign template. Missing values prevent generation.",
            sorted(fields),
            0,
            False,
        )
        if ok and chosen in fields:
            self.brief_toggle.setChecked(True)
            self.brief_tabs.show()
            self.brief_tabs.setCurrentIndex(0)
            self.wrapper.insertPlainText("{{ " + chosen + " }}")
            self.wrapper.setFocus()

    def selected_message(self) -> Message | None:
        return self.current_message

    def editor_ready(self) -> bool:
        return not self.dirty and self.saver.future is None and self.operation_thread is None

    def preview_message(self) -> None:
        if self.current_message is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Reading preview · approximate plain-text wrapping")
        dialog.resize(850, 540)
        layout = QVBoxLayout(dialog)
        hints = quality_hints(self.subject.text(), self.body.toPlainText())
        layout.addWidget(
            label(
                "\n".join(hints)
                if hints
                else "No length or placeholder warnings. Review facts and permission yourself."
            )
        )
        columns = QHBoxLayout()
        for width in (40, 72):
            view = QPlainTextEdit(
                reading_preview(self.subject.text(), self.body.toPlainText(), width)
            )
            view.setReadOnly(True)
            view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            columns.addWidget(view)
        layout.addLayout(columns)
        dialog.exec()

    def regenerate(self) -> None:
        def prepare() -> None:
            if self.current_message is None or self.dirty or self.saver.future is not None:
                raise ValidationError(
                    "Select a recipient and save edits before generating a candidate."
                )
            generator = (
                DemoGenerator() if self.application.demo else AIGenerator(self.network_settings())
            )
            message_id = self.current_message.id
            self.start(
                lambda stop, emit: self.application.service.candidate(message_id, generator, stop)
            )

        self.guard(prepare)

    def show_revisions(self) -> None:
        if self.current_message is None:
            return
        revisions = self.store.revisions(self.current_message.id)
        dialog = QDialog(self)
        dialog.setWindowTitle("Saved revisions · read-only")
        dialog.resize(720, 500)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(
            "\n\n──────────\n\n".join(
                f"Revision {row['revision']} · {row['origin']}\n{row['subject']}\n\n{row['body']}\n\nInstructions: {row['instructions']}"
                for row in revisions
            )
            or "No saved revisions yet."
        )
        layout.addWidget(view)
        dialog.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.pending_navigation = None
        if self.saver.future is not None or (
            (self.dirty or self.campaign_dirty) and self.autosave_toggle.isChecked()
        ):
            self.pending_close = True
            self.autosave()
            event.ignore()
            return
        if self.operation_thread is not None:
            self.closing = True
            self.stop()
            event.ignore()
        elif (self.dirty or self.campaign_dirty) and not self.confirm_unsaved():
            event.ignore()
        else:
            if self.current_message:
                self.store.release_edit(self.current_message.id)
            self.autosave_timer.stop()
            self.max_save_timer.stop()
            self.saver.shutdown()
            self.history_page.shutdown()
            event.accept()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cold Mailer desktop")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--development", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use a temporary synthetic workspace with fake providers and no transmission",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Open an isolated profile and exit without provider calls",
    )
    parser.add_argument(
        "--snapshot", type=Path, help="Save a UI snapshot during an explicit smoke test"
    )
    args = parser.parse_args(argv)
    if args.demo and (args.data_dir or args.development):
        parser.error("--demo uses its own temporary profile; omit --data-dir and --development")
    if args.smoke_test and args.data_dir is None:
        parser.error("--smoke-test requires an explicit --data-dir")
    if args.snapshot and not args.smoke_test:
        parser.error("--snapshot requires --smoke-test")
    qt = QApplication.instance() or QApplication([])
    temporary = TemporaryDirectory(prefix="cold-mailer-demo-") if args.demo else None
    if temporary:
        args.data_dir = Path(temporary.name)
    try:
        with Application(
            Settings.load(args.data_dir, development=args.development), demo=args.demo
        ) as application:
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
    finally:
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
