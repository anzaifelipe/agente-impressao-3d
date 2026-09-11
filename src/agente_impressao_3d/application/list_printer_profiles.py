"""Pure application use case for listing reusable printer profiles."""

from dataclasses import dataclass

from agente_impressao_3d.domain.ports import PrinterProfileReader
from agente_impressao_3d.domain.printer_profile import PrinterProfileEntry


@dataclass(frozen=True, slots=True)
class ListPrinterProfiles:
    """Lists reader-provided profiles in the reader's deterministic order."""

    printer_profile_reader: PrinterProfileReader

    def execute(self) -> tuple[PrinterProfileEntry, ...]:
        return self.printer_profile_reader.list_profiles()
