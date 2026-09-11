import json

import pytest

from agente_impressao_3d.application.cli_configuration import (
    CliConfigurationAlreadyExistsError,
    CliConfigurationNotFoundError,
    GetCliConfiguration,
    InitializeCliConfiguration,
    SetDefaultPrinterProfile,
    UnknownDefaultPrinterProfileError,
)
from agente_impressao_3d.domain.cli_configuration import CliConfiguration
from agente_impressao_3d.infrastructure.built_in_printer_profiles import (
    BuiltInPrinterProfileReader,
)
from agente_impressao_3d.infrastructure.json_cli_configuration_store import (
    JsonCliConfigurationStore,
)


def test_initializes_and_reads_empty_configuration(tmp_path) -> None:
    store = JsonCliConfigurationStore(tmp_path / "config.json")

    initialized = InitializeCliConfiguration(store).execute()

    assert initialized == CliConfiguration()
    assert GetCliConfiguration(store).execute() == CliConfiguration()
    assert json.loads((tmp_path / "config.json").read_text()) == {
        "schema_version": "1.0",
        "default_printer_profile": None,
    }


def test_initialization_does_not_overwrite_existing_configuration(tmp_path) -> None:
    store = JsonCliConfigurationStore(tmp_path / "config.json")
    store.save(CliConfiguration(default_printer_profile="bambu-lab-a1-mini"))

    with pytest.raises(CliConfigurationAlreadyExistsError):
        InitializeCliConfiguration(store).execute()

    assert GetCliConfiguration(store).execute().default_printer_profile == (
        "bambu-lab-a1-mini"
    )


def test_set_default_validates_profile_and_creates_configuration(tmp_path) -> None:
    store = JsonCliConfigurationStore(tmp_path / "config.json")
    set_default = SetDefaultPrinterProfile(store, BuiltInPrinterProfileReader())

    configuration = set_default.execute("bambu-lab-a1-mini")

    assert configuration.default_printer_profile == "bambu-lab-a1-mini"
    assert GetCliConfiguration(store).execute() == configuration


def test_set_default_rejects_unknown_profile_without_creating_configuration(tmp_path) -> None:
    store = JsonCliConfigurationStore(tmp_path / "config.json")

    with pytest.raises(UnknownDefaultPrinterProfileError, match="unknown printer profile"):
        SetDefaultPrinterProfile(store, BuiltInPrinterProfileReader()).execute("missing")

    assert store.load() is None


def test_get_requires_initialization(tmp_path) -> None:
    with pytest.raises(CliConfigurationNotFoundError, match="config init"):
        GetCliConfiguration(JsonCliConfigurationStore(tmp_path / "config.json")).execute()
