"""Use cases for deterministic persistent CLI configuration."""

from dataclasses import dataclass, replace

from agente_impressao_3d.domain.cli_configuration import CliConfiguration
from agente_impressao_3d.domain.ports import CliConfigurationStore, PrinterProfileReader


class CliConfigurationNotFoundError(ValueError):
    """Raised when an operation requires an initialized configuration."""


class CliConfigurationAlreadyExistsError(ValueError):
    """Raised when initialization would overwrite existing configuration."""


class UnknownDefaultPrinterProfileError(ValueError):
    """Raised when a default printer identifier is not in the profile reader."""


@dataclass(frozen=True, slots=True)
class GetCliConfiguration:
    store: CliConfigurationStore

    def execute(self) -> CliConfiguration:
        configuration = self.store.load()
        if configuration is None:
            raise CliConfigurationNotFoundError(
                "CLI configuration was not found. Run 'agente-impressao-3d config init'."
            )
        return configuration


@dataclass(frozen=True, slots=True)
class InitializeCliConfiguration:
    store: CliConfigurationStore

    def execute(self) -> CliConfiguration:
        configuration = CliConfiguration()
        if not self.store.initialize(configuration):
            raise CliConfigurationAlreadyExistsError(
                "CLI configuration already exists and was not overwritten."
            )
        return configuration


@dataclass(frozen=True, slots=True)
class SetDefaultPrinterProfile:
    store: CliConfigurationStore
    printer_profile_reader: PrinterProfileReader

    def execute(self, profile_id: str) -> CliConfiguration:
        if self.printer_profile_reader.get_profile(profile_id) is None:
            raise UnknownDefaultPrinterProfileError(
                f"unknown printer profile: {profile_id}"
            )
        configuration = self.store.load() or CliConfiguration()
        updated = replace(configuration, default_printer_profile=profile_id)
        self.store.save(updated)
        return updated
