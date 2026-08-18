from __future__ import annotations

from pathlib import Path
import struct
import unittest

import cv2


ROOT = Path(__file__).resolve().parents[1]


class WindowsLauncherTests(unittest.TestCase):
    def test_hidden_launcher_uses_pythonw_and_validates_environment(self) -> None:
        launcher = (ROOT / "Lalikul Cut Prep.vbs").read_text(encoding="utf-8")
        self.assertIn(".venv\\Scripts\\pythonw.exe", launcher)
        self.assertIn("import PySide6, cv2, numpy, app.main", launcher)
        self.assertIn("shell.Run Quote(pythonwExe)", launcher)
        self.assertIn(", 0, False", launcher)

    def test_batch_launchers_have_separate_user_and_diagnostic_paths(self) -> None:
        normal = (ROOT / "run.bat").read_text(encoding="utf-8")
        diagnostic = (ROOT / "run_console.bat").read_text(encoding="utf-8")
        self.assertIn("wscript.exe", normal.lower())
        self.assertIn("Lalikul Cut Prep.vbs", normal)
        self.assertIn('.venv\\Scripts\\python.exe" -m app.main', diagnostic)
        self.assertIn("pause", diagnostic.lower())

    def test_brand_assets_are_transparent_and_multiresolution(self) -> None:
        png_path = ROOT / "app" / "assets" / "lalikul-cut-prep.png"
        ico_path = ROOT / "app" / "assets" / "lalikul-cut-prep.ico"
        self.assertTrue(png_path.exists())
        self.assertTrue(ico_path.exists())

        png = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
        self.assertIsNotNone(png)
        assert png is not None
        self.assertEqual(png.shape[2], 4)
        self.assertEqual(int(png[0, 0, 3]), 0)
        visible_pixels = png[png[:, :, 3] > 200]
        self.assertGreater(len(visible_pixels), 1000)
        self.assertFalse(
            bool(
                (
                    (visible_pixels[:, 2] > 200)
                    & (visible_pixels[:, 0] > 150)
                    & (visible_pixels[:, 1] < 80)
                ).any()
            )
        )

        ico_data = ico_path.read_bytes()
        reserved, icon_type, count = struct.unpack_from("<HHH", ico_data, 0)
        self.assertEqual((reserved, icon_type), (0, 1))
        sizes = set()
        for index in range(count):
            width_byte, height_byte = struct.unpack_from(
                "<BB", ico_data, 6 + index * 16
            )
            sizes.add((width_byte or 256, height_byte or 256))
        self.assertEqual(
            sizes,
            {
                (16, 16),
                (24, 24),
                (32, 32),
                (48, 48),
                (64, 64),
                (128, 128),
                (256, 256),
            },
        )

    def test_setup_creates_branded_shortcut(self) -> None:
        setup = (ROOT / "setup.bat").read_text(encoding="utf-8")
        shortcut_builder = (
            ROOT / "app" / "config" / "create_shortcut.vbs"
        ).read_text(encoding="utf-8")
        self.assertIn("create_shortcut.vbs", setup)
        self.assertIn("lalikul-cut-prep.ico", shortcut_builder)
        self.assertIn("Lalikul Cut Prep.lnk", shortcut_builder)


if __name__ == "__main__":
    unittest.main()
