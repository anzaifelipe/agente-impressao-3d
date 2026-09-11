"""JSON filesystem adapter for the persistent CLI configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agente_impressao_3d.domain.cli_configuration import CliConfiguration


def default_cli_configuration_path() -> Path:
    """Return the user-scoped configuration location at the infrastructure edge."""
    return Path.home() / ".config" / "agente-impressao-3d" / "config.json"


@dataclass(frozen=True, slots=True)
class JsonCliConfigurationStore:
    """Stores the small configuration in one deterministic JSON document."""

    path: Path

    def load(self) -> CliConfiguration | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return CliConfiguration(
                schema_version=payload["schema_version"],
                default_printer_profile=payload["default_printer_profile"],
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("CLI configuration file is invalid.") from error

    def initialize(self, configuration: CliConfiguration) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("x", encoding="utf-8") as handle:
                json.dump(configuration.to_dict(), handle, indent=2)
                handle.write("\n")
        except FileExistsError:
            return False
        return True

    def save(self, configuration: CliConfiguration) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(configuration.to_dict(), handle, indent=2)
            handle.write("\n")
