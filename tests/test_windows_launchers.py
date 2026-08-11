from __future__ import annotations

from pathlib import Path
import unittest

from PIL import Image


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
        self.assertIn("python -m app.main", diagnostic)
        self.assertIn("pause", diagnostic.lower())

    def test_brand_assets_are_transparent_and_multiresolution(self) -> None:
        png_path = ROOT / "app" / "assets" / "lalikul-cut-prep.png"
        ico_path = ROOT / "app" / "assets" / "lalikul-cut-prep.ico"
        self.assertTrue(png_path.exists())
        self.assertTrue(ico_path.exists())

        with Image.open(png_path) as source:
            png = source.convert("RGBA")
        self.assertEqual(png.getpixel((0, 0))[3], 0)
        raw_pixels = png.tobytes()
        visible_pixels = [
            tuple(raw_pixels[index : index + 4])
            for index in range(0, len(raw_pixels), 4)
            if raw_pixels[index + 3] > 200
        ]
        self.assertGreater(len(visible_pixels), 1000)
        self.assertFalse(
            any(red > 200 and blue > 150 and green < 80 for red, green, blue, _ in visible_pixels)
        )

        with Image.open(ico_path) as ico:
            self.assertEqual(
                ico.ico.sizes(),
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
