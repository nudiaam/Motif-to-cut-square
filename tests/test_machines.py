from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.config.machines import MachineRepository
from app.geometry.units import LengthUnit


class MachineRepositoryTests(unittest.TestCase):
    def test_custom_machine_is_named_converted_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "machines.json"
            repository = MachineRepository(path)
            profile = repository.add_custom_profile(
                "Workshop 900 × 600",
                900.0,
                600.0,
                LengthUnit.MILLIMETRES,
            )
            reloaded = MachineRepository(path).load_custom_profiles()

        self.assertEqual(profile.name, "Workshop 900 × 600")
        self.assertAlmostEqual(profile.bed_width_in, 900.0 / 25.4)
        self.assertAlmostEqual(profile.bed_height_in, 600.0 / 25.4)
        self.assertEqual(reloaded, [profile])


if __name__ == "__main__":
    unittest.main()
