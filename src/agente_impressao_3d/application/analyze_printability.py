"""Thin orchestration of deterministic printability analysis capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agente_impressao_3d.domain.build_volume import BuildVolumeAnalysisResult
from agente_impressao_3d.domain.models import StlAnalysisResult
from agente_impressao_3d.domain.overhang import (
    OverhangAnalysisConfiguration,
    OverhangAnalysisResult,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.printability import (
    PrintabilityAnalysisConfiguration,
    PrintabilityAnalysisResult,
)
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
)


class StlAnalysisRunner(Protocol):
    def execute(self, source_path: Path) -> StlAnalysisResult: ...


class ScaleAndUnitAnalysisRunner(Protocol):
    def execute(
        self,
        stl_analysis: StlAnalysisResult,
        configuration: ScaleAndUnitConfiguration,
    ) -> ScaleAndUnitAnalysisResult: ...


class BuildVolumeAnalysisRunner(Protocol):
    def execute(
        self,
        scale_and_unit_analysis: ScaleAndUnitAnalysisResult,
        printer_profile: PrinterProfile,
    ) -> BuildVolumeAnalysisResult: ...


class OverhangAnalysisRunner(Protocol):
    def execute(
        self,
        source_path: Path,
        configuration: OverhangAnalysisConfiguration,
    ) -> OverhangAnalysisResult: ...


@dataclass(frozen=True, slots=True)
class AnalyzePrintability:
    """Composes existing analyzers without recalculating their specialized facts."""

    analyze_stl: StlAnalysisRunner
    analyze_scale_and_unit: ScaleAndUnitAnalysisRunner
    analyze_build_volume: BuildVolumeAnalysisRunner
    analyze_overhang: OverhangAnalysisRunner

    def execute(
        self,
        source_path: Path,
        printer_profile: PrinterProfile,
        configuration: PrintabilityAnalysisConfiguration | None = None,
    ) -> PrintabilityAnalysisResult:
        config = configuration or PrintabilityAnalysisConfiguration()
        stl_analysis = self.analyze_stl.execute(source_path)
        scale_and_unit_analysis = self.analyze_scale_and_unit.execute(
            stl_analysis, config.scale_and_unit
        )
        build_volume_analysis = self.analyze_build_volume.execute(
            scale_and_unit_analysis, printer_profile
        )
        overhang_analysis = self.analyze_overhang.execute(source_path, config.overhang)

        return PrintabilityAnalysisResult(
            source_path=str(source_path),
            configuration=config,
            stl_analysis=stl_analysis,
            scale_and_unit_analysis=scale_and_unit_analysis,
            build_volume_analysis=build_volume_analysis,
            overhang_analysis=overhang_analysis,
        )
