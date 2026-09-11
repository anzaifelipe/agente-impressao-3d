import pytest

from agente_impressao_3d.application.get_printer_profile import (
    GetPrinterProfile,
    UnknownPrinterProfileError,
)
from agente_impressao_3d.application.list_printer_profiles import ListPrinterProfiles
from agente_impressao_3d.infrastructure.built_in_printer_profiles import (
    BuiltInPrinterProfileReader,
)


def test_gets_built_in_profile_by_stable_identifier() -> None:
    profile = GetPrinterProfile(BuiltInPrinterProfileReader()).execute(
        "bambu-lab-a1-mini"
    )

    assert profile.manufacturer == "Bambu Lab"
    assert profile.model == "A1 Mini"
    assert profile.build_volume.x == 180.0
    assert profile.build_volume.y == 180.0
    assert profile.build_volume.z == 180.0
    assert profile.build_volume_unit == "mm"


def test_unknown_profile_raises_explicit_application_error() -> None:
    with pytest.raises(UnknownPrinterProfileError, match="unknown printer profile"):
        GetPrinterProfile(BuiltInPrinterProfileReader()).execute("missing-printer")


def test_lists_built_in_profiles_in_deterministic_order() -> None:
    entries = ListPrinterProfiles(BuiltInPrinterProfileReader()).execute()

    assert [entry.profile_id for entry in entries] == ["bambu-lab-a1-mini"]
    assert entries[0].profile.model == "A1 Mini"
