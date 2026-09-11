"""Pure presentation-oriented interpretation of an existing print plan."""

from __future__ import annotations

from dataclasses import dataclass

from agente_impressao_3d.domain.models import AnalysisWarning
from agente_impressao_3d.domain.print_plan import PrintPlanAnalysisResult
from agente_impressao_3d.domain.print_plan_summary import (
    PrintPlanSummaryFacts,
    PrintPlanSummaryResult,
    PrintPlanSummaryWarning,
)


@dataclass(frozen=True, slots=True)
class SummarizePrintPlan:
    """Extracts a compact summary without recalculating or deciding anything."""

    def execute(self, print_plan: PrintPlanAnalysisResult) -> PrintPlanSummaryResult:
        recommendation = print_plan.print_recommendation_analysis
        recommended_orientation = (
            recommendation.recommended_candidate.orientation.name
            if recommendation.recommended_candidate is not None
            else None
        )
        print_height = _print_height_for(
            print_plan, recommended_orientation
        )
        warnings = _collect_warnings(print_plan)

        return PrintPlanSummaryResult(
            source_path=print_plan.stl_analysis.source_path,
            facts=PrintPlanSummaryFacts(
                physical_dimensions=(
                    print_plan.scale_and_unit_analysis.facts.physical_dimensions
                ),
                physical_unit=(
                    print_plan.scale_and_unit_analysis.configuration.physical_unit
                ),
                fits_build_volume=print_plan.build_volume_analysis.facts.fits,
                recommended_orientation=recommended_orientation,
                print_height=print_height,
                overhang_area_percentage=(
                    print_plan.overhang_analysis.facts.overhang_area_percentage
                ),
                recommendation_status=recommendation.status.value,
                warning_count=len(warnings),
            ),
            warnings=warnings,
        )


def _print_height_for(
    print_plan: PrintPlanAnalysisResult, orientation_name: str | None
) -> float | None:
    if orientation_name is None:
        return None
    for candidate in print_plan.orientation_analysis.candidates:
        if candidate.orientation.name == orientation_name:
            return candidate.facts.print_height
    return None


def _summary_warning(
    warning: AnalysisWarning, origin: str
) -> PrintPlanSummaryWarning:
    return PrintPlanSummaryWarning(
        code=warning.code,
        message=warning.message,
        severity=warning.severity.value,
        origin=origin,
    )


def _collect_warnings(
    print_plan: PrintPlanAnalysisResult,
) -> tuple[PrintPlanSummaryWarning, ...]:
    """Keep each result's warning order while using a fixed result order."""
    warnings = [
        *(
            _summary_warning(warning, "stl_analysis")
            for warning in print_plan.stl_analysis.warnings
        ),
        *(
            _summary_warning(warning, "build_volume_analysis")
            for warning in print_plan.build_volume_analysis.warnings
        ),
        *(
            _summary_warning(warning, "orientation_analysis")
            for warning in print_plan.orientation_analysis.warnings
        ),
        *(
            _summary_warning(
                warning, f"orientation_candidate:{candidate.orientation.name}"
            )
            for candidate in print_plan.orientation_analysis.candidates
            for warning in candidate.warnings
        ),
        *(
            _summary_warning(warning, "overhang_analysis")
            for warning in print_plan.overhang_analysis.warnings
        ),
        *(
            _summary_warning(warning.warning, warning.origin)
            for warning in print_plan.print_recommendation_analysis.warnings
        ),
    ]
    return tuple(warnings)
