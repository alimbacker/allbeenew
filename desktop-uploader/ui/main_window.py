"""ALLBEE Instant Uploader — main window.

Two screens: sign in, then the run screen that watches a folder and uploads.
The run screen is deliberately sparse. It is glanced at across a room during a
reception, so it answers one question at a time: is it connected, and is it
keeping up.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.theme import ALERT, CHALK_SOFT, GO, STYLESHEET
from uploader.client import AllbeeClient, ApiError
from uploader.state import UploaderState
from uploader.watcher import Progress, UploadWorker

DEFAULT_SERVER = "http://localhost:8000"


def panel() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    return frame


class SignInPage(QWidget):
    signed_in = Signal(object, list)  # client, events

    def __init__(self, state: UploaderState) -> None:
        super().__init__()
        self.state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(14)

        title = QLabel("ALLBEE Instant Uploader")
        title.setObjectName("Title")
        subtitle = QLabel("Sign in with your photographer account.")
        subtitle.setObjectName("Caption")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        self.server = QLineEdit(state.get("server", DEFAULT_SERVER))
        self.email = QLineEdit(state.get("email", ""))
        self.email.setPlaceholderText("you@example.com")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Password")
        self.password.returnPressed.connect(self.submit)

        for label, widget in [
            ("Server", self.server),
            ("Email", self.email),
            ("Password", self.password),
        ]:
            caption = QLabel(label)
            caption.setObjectName("Caption")
            layout.addWidget(caption)
            layout.addWidget(widget)

        self.error = QLabel("")
        self.error.setStyleSheet(f"color: {ALERT};")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)

        self.button = QPushButton("Sign in")
        self.button.setObjectName("Primary")
        self.button.clicked.connect(self.submit)
        layout.addWidget(self.button)
        layout.addStretch(1)

    def submit(self) -> None:
        self.error.setText("")
        self.button.setEnabled(False)
        self.button.setText("Signing in...")
        QApplication.processEvents()

        client = AllbeeClient(self.server.text().strip() or DEFAULT_SERVER)
        try:
            client.login(self.email.text().strip(), self.password.text())
            events = client.events()
        except ApiError as exc:
            self.error.setText(str(exc))
            return
        finally:
            self.button.setEnabled(True)
            self.button.setText("Sign in")

        self.state.set("server", client.base_url)
        self.state.set("email", self.email.text().strip())
        self.signed_in.emit(client, events)


class RunPage(QWidget):
    def __init__(self, state: UploaderState) -> None:
        super().__init__()
        self.state = state
        self.client: AllbeeClient | None = None
        self.events: list[dict] = []
        self.thread: QThread | None = None
        self.worker: UploadWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        header = QLabel("ALLBEE Instant Uploader")
        header.setObjectName("Title")
        root.addWidget(header)

        # -- setup panel ---------------------------------------------------
        setup = panel()
        setup_layout = QGridLayout(setup)
        setup_layout.setContentsMargins(18, 16, 18, 16)
        setup_layout.setHorizontalSpacing(12)
        setup_layout.setVerticalSpacing(10)

        event_label = QLabel("Event")
        event_label.setObjectName("Caption")
        self.event_picker = QComboBox()
        setup_layout.addWidget(event_label, 0, 0)
        setup_layout.addWidget(self.event_picker, 0, 1, 1, 2)

        folder_label = QLabel("Folder")
        folder_label.setObjectName("Caption")
        self.folder_value = QLabel(state.get("folder", "No folder chosen"))
        self.folder_value.setWordWrap(True)
        self.browse = QPushButton("Choose...")
        self.browse.clicked.connect(self.choose_folder)
        setup_layout.addWidget(folder_label, 1, 0)
        setup_layout.addWidget(self.folder_value, 1, 1)
        setup_layout.addWidget(self.browse, 1, 2)
        setup_layout.setColumnStretch(1, 1)
        root.addWidget(setup)

        # -- counters ------------------------------------------------------
        counters = panel()
        grid = QGridLayout(counters)
        grid.setContentsMargins(18, 16, 18, 16)
        self.values: dict[str, QLabel] = {}
        for column, (key, caption, style) in enumerate(
            [
                ("detected", "Detected", "Value"),
                ("uploaded", "Uploaded", "ValueHoney"),
                ("queued", "Queued", "Value"),
                ("failed", "Failed", "Value"),
            ]
        ):
            value = QLabel("0")
            value.setObjectName(style)
            caption_label = QLabel(caption)
            caption_label.setObjectName("Caption")
            grid.addWidget(value, 0, column)
            grid.addWidget(caption_label, 1, column)
            grid.setColumnStretch(column, 1)
            self.values[key] = value
        root.addWidget(counters)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.current = QLabel("")
        self.current.setObjectName("Caption")
        root.addWidget(self.current)

        # -- status + controls ---------------------------------------------
        controls = QHBoxLayout()
        self.status = QLabel("● Not running")
        self.status.setStyleSheet(f"color: {CHALK_SOFT};")
        controls.addWidget(self.status)
        controls.addStretch(1)

        self.retry_button = QPushButton("Retry failed")
        self.retry_button.clicked.connect(self.retry_failed)
        self.retry_button.setEnabled(False)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        self.start_button = QPushButton("Start watching")
        self.start_button.setObjectName("Primary")
        self.start_button.clicked.connect(self.toggle_watch)

        controls.addWidget(self.retry_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.start_button)
        root.addLayout(controls)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setFixedHeight(140)
        root.addWidget(self.log)

    # -- wiring ------------------------------------------------------------
    def configure(self, client: AllbeeClient, events: list[dict]) -> None:
        self.client = client
        self.events = events
        self.event_picker.clear()
        for event in events:
            label = f"{event['name']}  ({event['event_code']})"
            self.event_picker.addItem(label, event["id"])
        remembered = self.state.get("event_id")
        if remembered:
            index = self.event_picker.findData(remembered)
            if index >= 0:
                self.event_picker.setCurrentIndex(index)
        if not events:
            self.append_log("No events yet. Create one in the web dashboard first.")

    def choose_folder(self) -> None:
        start = self.state.get("folder") or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose the photo folder", start)
        if chosen:
            self.folder_value.setText(chosen)
            self.state.set("folder", chosen)

    def append_log(self, message: str) -> None:
        self.log.appendPlainText(message)

    # -- run control -------------------------------------------------------
    def toggle_watch(self) -> None:
        if self.thread is not None:
            self.stop_watching()
        else:
            self.start_watching()

    def start_watching(self) -> None:
        folder = Path(self.folder_value.text())
        if not folder.is_dir():
            QMessageBox.warning(self, "Choose a folder", "Pick the folder your camera writes to.")
            return
        event_id = self.event_picker.currentData()
        if not event_id or self.client is None:
            QMessageBox.warning(self, "Choose an event", "Select the event to upload into.")
            return
        self.state.set("event_id", event_id)

        self.worker = UploadWorker(self.client, self.state, event_id, folder)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.render)
        self.worker.log.connect(self.append_log)
        self.thread.start()

        self.start_button.setText("Stop")
        self.pause_button.setEnabled(True)
        self.retry_button.setEnabled(True)
        self.event_picker.setEnabled(False)
        self.browse.setEnabled(False)
        self.status.setText("● Connected")
        self.status.setStyleSheet(f"color: {GO};")

    def stop_watching(self) -> None:
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait(4000)
        self.thread = None
        self.worker = None

        self.start_button.setText("Start watching")
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.retry_button.setEnabled(False)
        self.event_picker.setEnabled(True)
        self.browse.setEnabled(True)
        self.status.setText("● Not running")
        self.status.setStyleSheet(f"color: {CHALK_SOFT};")

    def toggle_pause(self) -> None:
        if not self.worker:
            return
        paused = self.pause_button.text() == "Pause"
        self.worker.set_paused(paused)
        self.pause_button.setText("Resume" if paused else "Pause")

    def retry_failed(self) -> None:
        if self.worker:
            self.worker.retry_failed()

    def render(self, stats: Progress) -> None:
        self.values["detected"].setText(f"{stats.detected:,}")
        self.values["uploaded"].setText(f"{stats.uploaded:,}")
        self.values["queued"].setText(f"{stats.queued:,}")
        self.values["failed"].setText(f"{stats.failed:,}")
        self.values["failed"].setObjectName("ValueAlert" if stats.failed else "Value")
        self.values["failed"].style().polish(self.values["failed"])

        handled = stats.uploaded + stats.duplicates + stats.failed
        total = max(handled + stats.queued, 1)
        self.progress.setValue(int(handled / total * 100))

        if stats.current:
            self.current.setText(f"Uploading {stats.current}")
        elif stats.queued:
            self.current.setText(f"{stats.queued:,} waiting")
        else:
            self.current.setText("Up to date" if stats.detected else "Waiting for photos")

        if stats.message:
            self.status.setText(f"● {stats.message}")
            self.status.setStyleSheet(f"color: {ALERT if not stats.connected else CHALK_SOFT};")
        elif stats.connected:
            self.status.setText("● Connected")
            self.status.setStyleSheet(f"color: {GO};")
        else:
            self.status.setText("● Reconnecting")
            self.status.setStyleSheet(f"color: {ALERT};")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ALLBEE Instant Uploader")
        self.resize(620, 720)
        self.setStyleSheet(STYLESHEET)

        self.state = UploaderState()
        self.stack = QStackedWidget()
        self.sign_in = SignInPage(self.state)
        self.run = RunPage(self.state)
        self.stack.addWidget(self.sign_in)
        self.stack.addWidget(self.run)
        self.setCentralWidget(self.stack)

        self.sign_in.signed_in.connect(self.on_signed_in)

        # Keep the session warm so a long reception does not expire the token
        # while the app sits idle between sets.
        self.keepalive = QTimer(self)
        self.keepalive.setInterval(5 * 60 * 1000)
        self.keepalive.timeout.connect(self.ping)
        self.keepalive.start()

    def on_signed_in(self, client: AllbeeClient, events: list) -> None:
        self.run.configure(client, events)
        self.stack.setCurrentWidget(self.run)

    def ping(self) -> None:
        if self.run.client is not None:
            try:
                self.run.client.ping()
            except ApiError:
                pass

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.run.thread is not None:
            answer = QMessageBox.question(
                self,
                "Still uploading",
                "The uploader is running. Stop it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.run.stop_watching()
        event.accept()
