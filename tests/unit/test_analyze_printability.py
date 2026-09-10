import json
from pathlib import Path

from agente_impressao_3d.application.analyze_printability import AnalyzePrintability
from agente_impressao_3d.domain.build_volume import (
    BuildVolumeAnalysisAssumptions,
    BuildVolumeAnalysisResult,
    BuildVolumeFacts,
)
from agente_impressao_3d.domain.models import (
    AnalysisAssumptions,
    BoundingBox,
    GeometryFacts,
    StlAnalysisResult,
    Vector3,
    Volume,
)
from agente_impressao_3d.domain.overhang import (
    OverhangAnalysisAssumptions,
    OverhangAnalysisConfiguration,
    OverhangAnalysisResult,
    OverhangFacts,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.printability import PrintabilityAnalysisConfiguration
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
    ScaleAndUnitFacts,
)


def stl_result() -> StlAnalysisResult:
    return StlAnalysisResult(
        source_path="model.stl",
        facts=GeometryFacts(
            triangle_count=12,
            bounding_box=BoundingBox(Vector3(0, 0, 0), Vector3(1, 2, 3)),
            watertight=True,
            volume=Volume(cubic_units=6.0, reliable=True),
        ),
        assumptions=AnalysisAssumptions(),
    )


def scaled_result() -> ScaleAndUnitAnalysisResult:
    return ScaleAndUnitAnalysisResult(
        source_path="model.stl",
        facts=ScaleAndUnitFacts(
            observed_dimensions=Vector3(1, 2, 3),
            physical_dimensions=Vector3(100, 200, 300),
        ),
        configuration=ScaleAndUnitConfiguration(scale_factor=100, physical_unit="mm"),
    )


def profile() -> PrinterProfile:
    return PrinterProfile("Example", "Printer", Vector3(300, 300, 300))


def build_volume_result(printer_profile: PrinterProfile) -> BuildVolumeAnalysisResult:
    return BuildVolumeAnalysisResult(
        source_path="model.stl",
        printer_profile=printer_profile,
        facts=BuildVolumeFacts(
            physical_dimensions=Vector3(100, 200, 300),
            fits=True,
            fits_x=True,
            fits_y=True,
            fits_z=True,
            remaining_space=Vector3(200, 100, 0),
            overflow=Vector3(0, 0, 0),
        ),
        assumptions=BuildVolumeAnalysisAssumptions(),
    )


def overhang_result() -> OverhangAnalysisResult:
    return OverhangAnalysisResult(
        source_path="model.stl",
        facts=OverhangFacts(12, 2, 600.0, 100.0, 100 / 6),
        configuration=OverhangAnalysisConfiguration(),
        assumptions=OverhangAnalysisAssumptions(),
    )


class FakeAnalyzeStl:
    def __init__(self, result: StlAnalysisResult, calls: list[tuple[object, ...]]) -> None:
        self.result = result
        self.calls = calls

    def execute(self, source_path: Path) -> StlAnalysisResult:
        self.calls.append(("stl", source_path))
        return self.result


class FakeAnalyzeScaleAndUnit:
    def __init__(
        self, result: ScaleAndUnitAnalysisResult, calls: list[tuple[object, ...]]
    ) -> None:
        self.result = result
        self.calls = calls

    def execute(
        self, analysis: StlAnalysisResult, configuration: ScaleAndUnitConfiguration
    ) -> ScaleAndUnitAnalysisResult:
        self.calls.append(("scale_and_unit", analysis, configuration))
        return self.result


class FakeAnalyzeBuildVolume:
    def __init__(
        self, result: BuildVolumeAnalysisResult, calls: list[tuple[object, ...]]
    ) -> None:
        self.result = result
        self.calls = calls

    def execute(
        self, analysis: ScaleAndUnitAnalysisResult, printer_profile: PrinterProfile
    ) -> BuildVolumeAnalysisResult:
        self.calls.append(("build_volume", analysis, printer_profile))
        return self.result


class FakeAnalyzeOverhang:
    def __init__(self, result: OverhangAnalysisResult, calls: list[tuple[object, ...]]) -> None:
        self.result = result
        self.calls = calls

    def execute(
        self, source_path: Path, configuration: OverhangAnalysisConfiguration
    ) -> OverhangAnalysisResult:
        self.calls.append(("overhang", source_path, configuration))
        return self.result


def test_orchestrates_existing_results_and_forwards_configuration() -> None:
    source_path = Path("model.stl")
    calls: list[tuple[object, ...]] = []
    stl = stl_result()
    scaled = scaled_result()
    printer = profile()
    build_volume = build_volume_result(printer)
    overhang = overhang_result()
    configuration = PrintabilityAnalysisConfiguration(
        scale_and_unit=ScaleAndUnitConfiguration(scale_factor=100, physical_unit="mm"),
        overhang=OverhangAnalysisConfiguration(threshold_degrees=30, batch_size=10),
    )
    analyzer = AnalyzePrintability(
        FakeAnalyzeStl(stl, calls),
        FakeAnalyzeScaleAndUnit(scaled, calls),
        FakeAnalyzeBuildVolume(build_volume, calls),
        FakeAnalyzeOverhang(overhang, calls),
    )

    result = analyzer.execute(source_path, printer, configuration)

    assert result.stl_analysis is stl
    assert result.scale_and_unit_analysis is scaled
    assert result.build_volume_analysis is build_volume
    assert result.overhang_analysis is overhang
    assert calls == [
        ("stl", source_path),
        ("scale_and_unit", stl, configuration.scale_and_unit),
        ("build_volume", scaled, printer),
        ("overhang", source_path, configuration.overhang),
    ]


def test_uses_default_configuration_and_serializes_composed_results() -> None:
    source_path = Path("model.stl")
    calls: list[tuple[object, ...]] = []
    stl = stl_result()
    scaled = scaled_result()
    printer = profile()
    analyzer = AnalyzePrintability(
        FakeAnalyzeStl(stl, calls),
        FakeAnalyzeScaleAndUnit(scaled, calls),
        FakeAnalyzeBuildVolume(build_volume_result(printer), calls),
        FakeAnalyzeOverhang(overhang_result(), calls),
    )

    result = analyzer.execute(source_path, printer)
    serialized = result.to_dict()

    assert result.configuration == PrintabilityAnalysisConfiguration()
    assert calls[1][2] == result.configuration.scale_and_unit
    assert calls[3][2] == result.configuration.overhang
    assert serialized["source"] == {"path": "model.stl", "format": "stl"}
    assert set(serialized["analyses"]) == {
        "stl",
        "scale_and_unit",
        "build_volume",
        "overhang",
    }
    assert serialized["analyses"]["build_volume"]["printer_profile"]["model"] == "Printer"
    json.dumps(serialized)
