"""Named laser-bed profiles with lightweight JSON persistence on Windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from app.geometry.units import LengthUnit, to_inches


@dataclass(frozen=True, slots=True)
class MachineProfile:
    id: str
    name: str
    bed_width_in: float
    bed_height_in: float
    builtin: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Machine id and name are required")
        if self.bed_width_in <= 0 or self.bed_height_in <= 0:
            raise ValueError("Machine bed dimensions must be positive")


EPILOG_FUSION_MAKER_36 = MachineProfile(
    id="epilog-fusion-maker-36",
    name="Epilog Fusion Maker 36",
    bed_width_in=36.0,
    bed_height_in=24.0,
    builtin=True,
)


class MachineRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else self._default_path()

    @staticmethod
    def _default_path() -> Path:
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Lalikul" / "CutPrep" / "machines.json"
        return Path.home() / ".lalikul-cut-prep" / "machines.json"

    def all_profiles(self) -> list[MachineProfile]:
        return [EPILOG_FUSION_MAKER_36, *self.load_custom_profiles()]

    def load_custom_profiles(self) -> list[MachineProfile]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        result: list[MachineProfile] = []
        for item in payload.get("machines", []):
            try:
                result.append(
                    MachineProfile(
                        id=str(item["id"]),
                        name=str(item["name"]),
                        bed_width_in=float(item["bed_width_in"]),
                        bed_height_in=float(item["bed_height_in"]),
                        builtin=False,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return result

    def add_custom_profile(
        self,
        name: str,
        bed_width: float,
        bed_height: float,
        unit: LengthUnit,
    ) -> MachineProfile:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Machine name is required")
        profiles = self.load_custom_profiles()
        all_names = {profile.name.casefold() for profile in self.all_profiles()}
        if clean_name.casefold() in all_names:
            raise ValueError("A machine with this name already exists")
        slug = re.sub(r"[^a-z0-9]+", "-", clean_name.casefold()).strip("-")
        profile = MachineProfile(
            id=f"{slug or 'machine'}-{uuid4().hex[:8]}",
            name=clean_name,
            bed_width_in=to_inches(bed_width, unit),
            bed_height_in=to_inches(bed_height, unit),
            builtin=False,
        )
        profiles.append(profile)
        self._save_custom_profiles(profiles)
        return profile

    def _save_custom_profiles(self, profiles: list[MachineProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "machines": [
                {**asdict(profile), "builtin": False}
                for profile in profiles
                if not profile.builtin
            ],
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
