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
from app.imaging.panel_grid import PanelGrid
from app.models import Detection
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

    def seed_detections(self):
        """Populate real cuts and return a content fingerprint to compare later.

        Identity of the list object is not enough: clearing it in place would
        still pass. The fingerprint captures each cut's data so a preserved
        result is proven, not merely a surviving container.
        """
        mapper = self.window.mapper
        self.window.detections = [
            Detection.from_pixel_center(1, (120, 110), mapper, (100, 90, 40, 40), .9),
            Detection.from_pixel_center(2, (320, 240), mapper, (300, 220, 40, 40), .8),
        ]
        return self.fingerprint()

    def fingerprint(self):
        return [(d.id, d.center_px, d.center_inches, d.bounding_box_px, d.enabled)
                for d in self.window.detections]

    def test_ui_remains_live_and_cancellation_preserves_previous_job(self):
        def slow(detector,image,settings):
            for _ in range(200):
                detector._progress('working')
                time.sleep(.005)
            return DetectionResult(())
        before=self.seed_detections()
        old=self.window.detections
        ticks=[]
        timer=QTimer(self.window);timer.timeout.connect(lambda:ticks.append(1));timer.start(5)
        self.window.show()
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',slow):
            self.window.detect_motifs(replace_confirmed=True,background=True)
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
        self.assertEqual(self.fingerprint(),before)
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
        before=self.seed_detections()
        old=self.window.detections
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout',side_effect=ValueError('controlled failure')), \
             patch('app.ui.main_window.QMessageBox.critical') as error:
            self.window.detect_motifs(replace_confirmed=True,background=True)
            self.wait_finished()
            self.assertIn('controlled failure',error.call_args.args[-1])
        self.assertIs(self.window.detections,old)
        self.assertEqual(self.fingerprint(),before)
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertTrue(self.window.analysis_status.isHidden())

    def test_confirm_grid_button_uses_worker_with_guides_and_applies_result(self):
        grid = PanelGrid.regular(600, 400, 3, 2)
        self.window.panel_grid = grid
        self.window._grid_review_complete = True
        captured = {}
        def guided(detector, image, settings, guides):
            captured['guides'] = guides
            detector.last_diagnostics = {'detector_revision': 'guided worker test'}
            return DetectionResult((MotifCandidate((200, 200), (180, 180, 40, 40), .9, 1600),))
        with patch('app.ui.detection_worker.MotifDetector.detect_with_guides', guided), \
             patch('app.ui.detection_worker.MotifDetector.detect_with_layout',
                   side_effect=AssertionError('guided re-detection must use the guides path')):
            self.window.panel.confirm_grid_button.setEnabled(True)
            self.window.panel.confirm_grid_button.click()
            self.assertEqual(self.window._workflow_phase, 'detect')
            self.assertIsNotNone(self.window._detection_worker)
            self.wait_finished()
        self.assertIs(captured.get('guides'), grid)
        self.assertEqual(len(self.window.detections), 1)
        self.assertEqual(self.window.detection_diagnostics['detector_revision'], 'guided worker test')
        self.assertTrue(self.window.centralWidget().isEnabled())

    def test_confirm_grid_cancellation_keeps_previous_cuts_and_live_ui(self):
        grid = PanelGrid.regular(600, 400, 3, 2)
        self.window.panel_grid = grid
        self.window._grid_review_complete = True
        before = self.seed_detections()
        old = self.window.detections
        def slow(detector, image, settings, guides):
            for _ in range(200):
                detector._progress('working')
                time.sleep(.005)
            return DetectionResult(())
        with patch('app.ui.detection_worker.MotifDetector.detect_with_guides', slow):
            self.window.show()
            self.window.confirm_grid(background=True)
            QTest.qWait(50)
            self.assertIsNotNone(self.window._detection_worker)
            QTest.mouseClick(self.window.analysis_cancel, Qt.MouseButton.LeftButton)
            self.wait_finished()
        self.assertIs(self.window.detections, old)
        self.assertEqual(self.fingerprint(), before)
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertTrue(self.window.analysis_status.isHidden())

    def test_confirm_grid_failure_keeps_previous_cuts_and_restores_controls(self):
        grid = PanelGrid.regular(600, 400, 3, 2)
        self.window.panel_grid = grid
        self.window._grid_review_complete = True
        before = self.seed_detections()
        old = self.window.detections
        with patch('app.ui.detection_worker.MotifDetector.detect_with_guides',
                   side_effect=ValueError('guided failure')), \
             patch('app.ui.main_window.QMessageBox.critical') as error:
            self.window.confirm_grid(background=True)
            self.wait_finished()
            self.assertIn('guided failure', error.call_args.args[-1])
        self.assertIs(self.window.detections, old)
        self.assertEqual(self.fingerprint(), before)
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertTrue(self.window.analysis_status.isHidden())

    def test_confirm_grid_ignored_while_a_detection_is_running(self):
        self.window.panel_grid = PanelGrid.regular(600, 400, 3, 2)
        self.window._grid_review_complete = False
        def slow(detector, image, settings):
            for _ in range(200):
                detector._progress('working')
                time.sleep(.005)
            return DetectionResult(())
        with patch('app.ui.detection_worker.MotifDetector.detect_with_layout', slow):
            self.window.detect_motifs(background=True)
            QTest.qWait(30)
            running = self.window._detection_worker
            self.assertIsNotNone(running)
            # A second trigger must not start a concurrent worker.
            self.window._grid_review_complete = True
            self.window.confirm_grid(background=True)
            self.assertIs(self.window._detection_worker, running)
            self.window._cancel_detection()
            self.wait_finished()

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
