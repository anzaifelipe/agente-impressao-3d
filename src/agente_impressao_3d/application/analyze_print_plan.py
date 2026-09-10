"""Pure composition of existing deterministic print analysis results."""

from dataclasses import dataclass

from agente_impressao_3d.domain.build_volume import BuildVolumeAnalysisResult
from agente_impressao_3d.domain.models import StlAnalysisResult
from agente_impressao_3d.domain.overhang import OverhangAnalysisResult
from agente_impressao_3d.domain.orientation import OrientationAnalysisResult
from agente_impressao_3d.domain.print_plan import PrintPlanAnalysisResult
from agente_impressao_3d.domain.print_recommendation import PrintRecommendationResult
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitAnalysisResult


@dataclass(frozen=True, slots=True)
class AnalyzePrintPlan:
    """Validates source identity and composes precomputed immutable results."""

    def execute(
        self,
        stl_analysis: StlAnalysisResult,
        scale_and_unit_analysis: ScaleAndUnitAnalysisResult,
        build_volume_analysis: BuildVolumeAnalysisResult,
        overhang_analysis: OverhangAnalysisResult,
        orientation_analysis: OrientationAnalysisResult,
        print_recommendation_analysis: PrintRecommendationResult,
    ) -> PrintPlanAnalysisResult:
        source_paths = {
            stl_analysis.source_path,
            scale_and_unit_analysis.source_path,
            build_volume_analysis.source_path,
            overhang_analysis.source_path,
            orientation_analysis.source_path,
            print_recommendation_analysis.source_path,
        }
        if len(source_paths) != 1:
            raise ValueError("All print-plan analyses must have the same source_path.")
        return PrintPlanAnalysisResult(
            stl_analysis=stl_analysis,
            scale_and_unit_analysis=scale_and_unit_analysis,
            build_volume_analysis=build_volume_analysis,
            overhang_analysis=overhang_analysis,
            orientation_analysis=orientation_analysis,
            print_recommendation_analysis=print_recommendation_analysis,
        )
