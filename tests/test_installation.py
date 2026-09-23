import unittest
from unittest.mock import patch

from app.config.check_installation import verify_installation


class InstallationTests(unittest.TestCase):
    def test_complete_installation_imports_and_decodes_bundled_assets(self):
        self.assertIn('opencv',verify_installation())

    def test_incomplete_package_is_not_reported_as_successful(self):
        with patch('app.config.check_installation.Path.is_file',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'Extract the entire ZIP again'):
                verify_installation()
