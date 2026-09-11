"""Composition use case for the existing complete deterministic print pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agente_impressao_3d.domain.build_volume import BuildVolumeAnalysisResult
from agente_impressao_3d.domain.models import StlAnalysisResult
from agente_impressao_3d.domain.orientation import OrientationAnalysisConfiguration, OrientationAnalysisResult
from agente_impressao_3d.domain.overhang import OverhangAnalysisConfiguration, OverhangAnalysisResult
from agente_impressao_3d.domain.print_plan import PrintPlanAnalysisResult
from agente_impressao_3d.domain.print_recommendation import (
    PrintRecommendationConfiguration,
    PrintRecommendationResult,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
)


class StlRunner(Protocol):
    def execute(self, source_path: Path) -> StlAnalysisResult: ...


class ScaleRunner(Protocol):
    def execute(
        self, stl_analysis: StlAnalysisResult, configuration: ScaleAndUnitConfiguration
    ) -> ScaleAndUnitAnalysisResult: ...


class BuildVolumeRunner(Protocol):
    def execute(
        self, scale_analysis: ScaleAndUnitAnalysisResult, profile: PrinterProfile
    ) -> BuildVolumeAnalysisResult: ...


class OverhangRunner(Protocol):
    def execute(
        self, source_path: Path, configuration: OverhangAnalysisConfiguration
    ) -> OverhangAnalysisResult: ...


class OrientationRunner(Protocol):
    def execute(
        self, source_path: Path, profile: PrinterProfile, configuration: OrientationAnalysisConfiguration
    ) -> OrientationAnalysisResult: ...


class RecommendationRunner(Protocol):
    def execute(
        self,
        stl_analysis: StlAnalysisResult,
        orientation_analysis: OrientationAnalysisResult,
        configuration: PrintRecommendationConfiguration,
    ) -> PrintRecommendationResult: ...


class PrintPlanRunner(Protocol):
    def execute(
        self,
        stl_analysis: StlAnalysisResult,
        scale_analysis: ScaleAndUnitAnalysisResult,
        build_volume_analysis: BuildVolumeAnalysisResult,
        overhang_analysis: OverhangAnalysisResult,
        orientation_analysis: OrientationAnalysisResult,
        recommendation_analysis: PrintRecommendationResult,
    ) -> PrintPlanAnalysisResult: ...


@dataclass(frozen=True, slots=True)
class ExecutePrintPlanAnalysis:
    """Composes existing capabilities; it introduces no geometric policy."""

    analyze_stl: StlRunner
    analyze_scale_and_unit: ScaleRunner
    analyze_build_volume: BuildVolumeRunner
    analyze_overhang: OverhangRunner
    analyze_orientation: OrientationRunner
    analyze_print_recommendation: RecommendationRunner
    analyze_print_plan: PrintPlanRunner

    def execute(
        self,
        source_path: Path,
        printer_profile: PrinterProfile,
        scale_and_unit_configuration: ScaleAndUnitConfiguration,
        overhang_configuration: OverhangAnalysisConfiguration,
        orientation_configuration: OrientationAnalysisConfiguration,
        recommendation_configuration: PrintRecommendationConfiguration,
    ) -> PrintPlanAnalysisResult:
        stl = self.analyze_stl.execute(source_path)
        scale = self.analyze_scale_and_unit.execute(stl, scale_and_unit_configuration)
        build_volume = self.analyze_build_volume.execute(scale, printer_profile)
        overhang = self.analyze_overhang.execute(source_path, overhang_configuration)
        orientation = self.analyze_orientation.execute(
            source_path, printer_profile, orientation_configuration
        )
        recommendation = self.analyze_print_recommendation.execute(
            stl, orientation, recommendation_configuration
        )
        return self.analyze_print_plan.execute(
            stl, scale, build_volume, overhang, orientation, recommendation
        )
