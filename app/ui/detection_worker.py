"""A job owns its pixels and detector; only the GUI thread applies its result."""
from threading import Event
from PySide6.QtCore import QThread, Signal
from app.diagnostics_log import get_logger
from app.imaging.detector import MotifDetector


class DetectionCancelled(Exception):
    pass


class DetectionWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, image, reference, settings, guides=None, parent=None):
        super().__init__(parent)
        self.image = image.copy()
        self.reference = reference.copy() if reference is not None else None
        self.settings = settings
        self.guides = guides
        self.cancelled = Event()

    def cancel(self):
        self.cancelled.set()

    def checkpoint(self, message):
        if self.cancelled.is_set():
            raise DetectionCancelled()
        self.progress.emit(message)

    def run(self):
        detector = MotifDetector()
        detector.bed_reference = self.reference
        detector.progress_callback = self.checkpoint
        try:
            self.checkpoint('Starting detection')
            result = (detector.detect_with_guides(self.image, self.settings, self.guides)
                      if self.guides else detector.detect_with_layout(self.image, self.settings))
            self.checkpoint('Detection finished')
            self.completed.emit((result, detector.last_diagnostics))
        except DetectionCancelled:
            pass
        except Exception as exc:
            if not self.cancelled.is_set():
                # The UI shows a short message; the full traceback goes to the
                # rotating log so a field failure leaves evidence to attach.
                get_logger().exception('Detection failed: %s', exc)
                self.failed.emit(str(exc))
