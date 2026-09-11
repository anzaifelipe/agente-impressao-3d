"""Pure application use case for resolving a reusable printer profile."""

from dataclasses import dataclass

from agente_impressao_3d.domain.ports import PrinterProfileReader
from agente_impressao_3d.domain.printer_profile import PrinterProfile


class UnknownPrinterProfileError(ValueError):
    """Raised when a requested stable printer-profile identifier is absent."""


@dataclass(frozen=True, slots=True)
class GetPrinterProfile:
    """Resolves a stable profile identifier through an injected reader."""

    printer_profile_reader: PrinterProfileReader

    def execute(self, profile_id: str) -> PrinterProfile:
        profile = self.printer_profile_reader.get_profile(profile_id)
        if profile is None:
            raise UnknownPrinterProfileError(f"unknown printer profile: {profile_id}")
        return profile
