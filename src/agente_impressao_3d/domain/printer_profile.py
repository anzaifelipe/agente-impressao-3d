"""Reusable domain model for a 3D printer profile."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .models import Vector3


@dataclass(frozen=True, slots=True)
class PrinterProfile:
    """Printer identity and its declared printable build volume."""

    manufacturer: str
    model: str
    build_volume: Vector3
    build_volume_unit: str = "mm"

    def __post_init__(self) -> None:
        if not self.manufacturer.strip():
            raise ValueError("manufacturer must not be empty.")
        if not self.model.strip():
            raise ValueError("model must not be empty.")
        if not self.build_volume_unit.strip():
            raise ValueError("build_volume_unit must not be empty.")

        for axis, value in (
            ("x", self.build_volume.x),
            ("y", self.build_volume.y),
            ("z", self.build_volume.z),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"build_volume.{axis} must be finite and greater than zero."
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "build_volume": self.build_volume.to_dict(),
            "build_volume_unit": self.build_volume_unit,
        }


@dataclass(frozen=True, slots=True)
class PrinterProfileEntry:
    """A stable external identifier paired with a domain printer profile."""

    profile_id: str
    profile: PrinterProfile

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be empty.")
