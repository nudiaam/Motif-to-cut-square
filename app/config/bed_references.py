"""Per-machine empty-bed images, independent of the current job image."""
from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np

from .machines import EPILOG_FUSION_MAKER_36


class BedReferences:
    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, machine_id):
        return self.directory / (sha256(machine_id.encode()).hexdigest() + '.png')

    def source(self, machine_id):
        path = self.path(machine_id)
        if path.with_suffix('.disabled').exists():
            return None
        if path.exists():
            return "custom"
        bundled = Path(__file__).resolve().parents[2] / 'assets/references/epilog/empty_bed.png'
        if machine_id == EPILOG_FUSION_MAKER_36.id and bundled.exists():
            return "built-in"
        return None

    def load(self, machine_id):
        path = self.path(machine_id)
        if path.with_suffix('.disabled').exists():
            return None
        if not path.exists() and machine_id == EPILOG_FUSION_MAKER_36.id:
            path = Path(__file__).resolve().parents[2] / 'assets/references/epilog/empty_bed.png'
        try:
            return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        except (OSError, cv2.error):
            return None

    def save(self, machine_id, image):
        ok, encoded = cv2.imencode('.png', image)
        if not ok:
            raise ValueError('Cannot encode reference image')
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(machine_id)
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(encoded.tobytes())
        temporary.replace(path)
        path.with_suffix('.disabled').unlink(missing_ok=True)

    def disable(self, machine_id):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path(machine_id).with_suffix('.disabled').touch()
