"""Domain contract for the small persistent CLI configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CliConfiguration:
    """Persistent CLI choices, independent from serialization and storage."""

    schema_version: str = "1.0"
    default_printer_profile: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str) or self.schema_version != "1.0":
            raise ValueError("unsupported CLI configuration schema_version.")
        if (
            self.default_printer_profile is not None
            and (
                not isinstance(self.default_printer_profile, str)
                or not self.default_printer_profile.strip()
            )
        ):
            raise ValueError("default_printer_profile must not be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "default_printer_profile": self.default_printer_profile,
        }
