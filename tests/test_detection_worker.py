import os
import time
import unittest
from unittest.mock import patch
import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.imaging.detector import DetectionResult, MotifCandidate
from app.ui.main_window import MainWindow


class DetectionWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.window=MainWindow()
        self.window._load_image(np.full((400,600,3),230,np.uint8),'worker test')
        self.addCleanup(self.window.close)

    def wait_finished(self):
        deadline=time.monotonic()+8
        while self.window._detection_worker is not None and time.monotonic()<deadline:
            QTest.qWait(10)
        self.assertIsNone(self.window._detection_worker)

    def test_ui_remains_live_and_cancellation_preserves_previous_job(self):
        def slow(detector,image,settings):
            for _ in range(200):
                detector._progress('working')
                time.sleep(.005)
            return DetectionResult(())
        old=self.window.detections
        ticks=[]
        timer=QTimer(self.window);timer.timeout.connect(lambda:ticks.append(1));timer.start(5)
        self.window.show()
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',slow):
            self.window.detect_motifs(background=True)
            QTest.qWait(50)
            self.assertTrue(ticks)
            self.assertIsNotNone(self.window._detection_worker)
            self.assertTrue(self.window.analysis_status.isVisible())
            self.assertIsNone(self.application.activeModalWidget())
            self.assertFalse(self.window.undo_shortcut.isEnabled())
            self.assertFalse(self.window.delete_key_shortcut.isEnabled())
            self.assertEqual(self.window.analysis_label.text(), 'working')
            QTest.mouseClick(self.window.analysis_cancel, Qt.MouseButton.LeftButton)
            self.assertEqual(self.window.analysis_label.text(), 'Cancelling analysis…')
            self.assertFalse(self.window.analysis_cancel.isEnabled())
            self.wait_finished()
        timer.stop()
        self.assertIs(self.window.detections,old)
        self.assertFalse(self.window._undo_stack)
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertTrue(self.window.analysis_status.isHidden())
        self.assertTrue(self.window.undo_shortcut.isEnabled())

    def test_completed_job_applies_on_gui_thread_and_can_be_undone(self):
        def result(detector,image,settings):
            detector.last_diagnostics={'detector_revision':'worker test'}
            return DetectionResult((MotifCandidate((200,200),(180,180,40,40),.9,1600),))
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',result):
            self.window.detect_motifs(background=True)
            self.wait_finished()
        self.assertEqual(len(self.window.detections),1)
        self.assertEqual(self.window.detection_diagnostics['detector_revision'],'worker test')
        self.assertNotIn('cancelled',self.window.statusBar().currentMessage().lower())
        self.assertTrue(self.window.analysis_status.isHidden())
        self.window.undo()
        self.assertEqual(self.window.detections,[])

    def test_worker_failure_keeps_previous_state_and_restores_controls(self):
        old=self.window.detections
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',side_effect=ValueError('controlled failure')), \
             patch('app.ui.main_window.QMessageBox.critical') as error:
            self.window.detect_motifs(background=True)
            self.wait_finished()
            self.assertIn('controlled failure',error.call_args.args[-1])
        self.assertIs(self.window.detections,old)
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertTrue(self.window.analysis_status.isHidden())

    def test_close_waits_for_worker_cancellation(self):
        def slow(detector,image,settings):
            for _ in range(200):
                time.sleep(.005)
                detector._progress('working')
            return DetectionResult(())
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',slow):
            self.window.show()
            self.window.detect_motifs(background=True)
            self.window.close()
            self.wait_finished()
            QTest.qWait(20)
        self.assertFalse(self.window.isVisible())


if __name__ == '__main__':
    unittest.main()
