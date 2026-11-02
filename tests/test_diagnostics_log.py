import logging
import shutil
import tempfile
import unittest
import zipfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import numpy as np

import app.diagnostics_log as diagnostics_log
from app.diagnostics_log import LOGGER_NAME, configure_logging, log_file_path
from app.export.debug_exporter import export_detection_bundle
from app.geometry.coordinate_mapper import CoordinateMapper
from app.imaging.detector import DetectorSettings
from app.imaging.run_diagnostics import run_identity
from app.ui.detection_worker import DetectionWorker


class DiagnosticsLogTests(unittest.TestCase):
    def setUp(self):
        # Each test owns a fresh destination and restores global logging state.
        # On Windows the rotating handler keeps the file open, so handlers are
        # closed in tearDown *before* the directory is removed.
        self.directory = tempfile.mkdtemp()
        self._logger = logging.getLogger(LOGGER_NAME)
        self._saved_handlers = self._logger.handlers[:]
        self._saved_path = diagnostics_log._log_path
        self._logger.handlers = []
        diagnostics_log._log_path = None

    def tearDown(self):
        for handler in self._logger.handlers:
            handler.close()
        self._logger.handlers = self._saved_handlers
        diagnostics_log._log_path = self._saved_path
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_configure_is_idempotent_and_writes_a_rotating_file(self):
        path = configure_logging(self.directory)
        self.assertEqual(path, Path(self.directory) / 'detection.log')
        self.assertEqual(log_file_path(), path)
        handlers = self._logger.handlers[:]
        # A second call for the same destination must not stack handlers.
        self.assertEqual(configure_logging(self.directory), path)
        self.assertEqual(self._logger.handlers, handlers)
        self._logger.error('a recorded line')
        self.assertIn('a recorded line', path.read_text(encoding='utf-8'))

    def test_configure_returns_none_when_the_directory_is_unwritable(self):
        with patch('app.diagnostics_log.Path.mkdir', side_effect=OSError('denied')):
            self.assertIsNone(configure_logging(self.directory))
        self.assertIsNone(log_file_path())

    def test_worker_writes_full_traceback_on_failure(self):
        path = configure_logging(self.directory)
        image = np.full((40, 60, 3), 210, np.uint8)
        worker = DetectionWorker(image, None, DetectorSettings())
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',
                   side_effect=ValueError('controlled worker failure')):
            worker.run()  # run inline; no event loop needed for the log
        logged = path.read_text(encoding='utf-8')
        self.assertIn('controlled worker failure', logged)
        self.assertIn('Traceback (most recent call last)', logged)
        self.assertIn('ValueError', logged)

    def test_cancelled_worker_does_not_log_a_failure(self):
        path = configure_logging(self.directory)
        image = np.full((40, 60, 3), 210, np.uint8)
        worker = DetectionWorker(image, None, DetectorSettings())
        worker.cancel()
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',
                   side_effect=ValueError('must not be logged')):
            worker.run()
        self.assertNotIn('must not be logged', path.read_text(encoding='utf-8'))

    def test_diagnostic_bundle_carries_the_log_when_configured(self):
        configure_logging(self.directory)
        self._logger.error('line that must travel with the package')
        image = np.full((80, 100, 3), (190, 200, 210), np.uint8)
        run = {'identity': run_identity(image, None, asdict(DetectorSettings()))}
        mapper = CoordinateMapper(100, 80)
        path = Path(self.directory) / 'case.zip'
        export_detection_bundle(path, image, None, mapper, [], detection_run=run)
        with zipfile.ZipFile(path) as bundle:
            self.assertIn('detection.log', bundle.namelist())
            self.assertIn(b'line that must travel with the package',
                          bundle.read('detection.log'))
            self.assertIn(b'text only, no images', bundle.read('README.txt'))

    def test_bundle_notes_absence_of_log_when_not_configured(self):
        self.assertIsNone(log_file_path())
        image = np.full((80, 100, 3), (190, 200, 210), np.uint8)
        run = {'identity': run_identity(image, None, asdict(DetectorSettings()))}
        mapper = CoordinateMapper(100, 80)
        path = Path(self.directory) / 'case.zip'
        export_detection_bundle(path, image, None, mapper, [], detection_run=run)
        with zipfile.ZipFile(path) as bundle:
            self.assertNotIn('detection.log', bundle.namelist())
            self.assertIn(b'No application log', bundle.read('README.txt'))


if __name__ == '__main__':
    unittest.main()
