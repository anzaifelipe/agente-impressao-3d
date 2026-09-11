"""Deterministic, in-process catalog of reusable printer profiles."""

from dataclasses import dataclass, field

from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.printer_profile import (
    PrinterProfile,
    PrinterProfileEntry,
)


_BUILT_IN_PROFILES: tuple[PrinterProfileEntry, ...] = (
    PrinterProfileEntry(
        profile_id="bambu-lab-a1-mini",
        profile=PrinterProfile(
            manufacturer="Bambu Lab",
            model="A1 Mini",
            build_volume=Vector3(180.0, 180.0, 180.0),
            build_volume_unit="mm",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class BuiltInPrinterProfileReader:
    """Reads the fixed built-in catalog without files, network, or mutation."""

    profiles: tuple[PrinterProfileEntry, ...] = field(
        default_factory=lambda: _BUILT_IN_PROFILES
    )

    def get_profile(self, profile_id: str) -> PrinterProfile | None:
        for entry in self.profiles:
            if entry.profile_id == profile_id:
                return entry.profile
        return None

    def list_profiles(self) -> tuple[PrinterProfileEntry, ...]:
        return self.profiles
