"""Pure interpretation of deterministic analysis results into a recommendation."""

from dataclasses import dataclass

from agente_impressao_3d.domain.models import StlAnalysisResult
from agente_impressao_3d.domain.orientation import (
    OrientationAnalysisResult,
    OrientationCandidateResult,
)
from agente_impressao_3d.domain.print_recommendation import (
    PrintRecommendationConfiguration,
    PrintRecommendationResult,
    PrintRecommendationStatus,
    RecommendationReason,
    RecommendationReasonCode,
    RecommendationWarning,
)


@dataclass(frozen=True, slots=True)
class AnalyzePrintRecommendation:
    """Makes an explicit decision using precomputed results only."""

    def execute(
        self,
        stl_analysis: StlAnalysisResult,
        orientation_analysis: OrientationAnalysisResult,
        configuration: PrintRecommendationConfiguration | None = None,
    ) -> PrintRecommendationResult:
        config = configuration or PrintRecommendationConfiguration()
        warnings = _collect_warnings(stl_analysis, orientation_analysis)
        warning_codes = {item.warning.code for item in warnings}

        if orientation_analysis.facts.total_face_count == 0 or "EMPTY_MESH" in warning_codes:
            return _result(
                stl_analysis,
                PrintRecommendationStatus.NOT_RECOMMENDED,
                config,
                None,
                RecommendationReason(
                    RecommendationReasonCode.EMPTY_MESH,
                    "The mesh has no faces, so a print recommendation is not reliable.",
                ),
                warnings,
            )
        if "ZERO_TOTAL_SURFACE_AREA" in warning_codes:
            return _result(
                stl_analysis,
                PrintRecommendationStatus.NOT_RECOMMENDED,
                config,
                None,
                RecommendationReason(
                    RecommendationReasonCode.ZERO_TOTAL_SURFACE_AREA,
                    "The mesh has no valid surface area, so a print recommendation is not reliable.",
                ),
                warnings,
            )

        selected = _first_ranked_compatible_candidate(orientation_analysis)
        if selected is None:
            if not _has_ranked_candidate(orientation_analysis):
                reason = RecommendationReason(
                    RecommendationReasonCode.NO_VALID_ORIENTATION,
                    "The orientation analysis did not provide a valid ranked candidate.",
                )
                status = PrintRecommendationStatus.NOT_RECOMMENDED
            else:
                reason = RecommendationReason(
                    RecommendationReasonCode.MODEL_DOES_NOT_FIT_BUILD_VOLUME,
                    "None of the ranked orientation candidates fits within the printer build volume.",
                )
                status = PrintRecommendationStatus.NOT_FIT
            return _result(stl_analysis, status, config, None, reason, warnings)

        reasons = [
            RecommendationReason(
                RecommendationReasonCode.MODEL_FITS_BUILD_VOLUME,
                "The selected orientation fits within the printer build volume.",
            ),
            RecommendationReason(
                RecommendationReasonCode.BEST_ORIENTATION_SELECTED,
                "The selected orientation is the first compatible candidate in the deterministic orientation ranking.",
            ),
        ]
        status = PrintRecommendationStatus.RECOMMENDED
        maximum_overhang = config.maximum_recommended_overhang_area_percentage
        percentage = selected.facts.overhang_area_percentage
        if (
            maximum_overhang is not None
            and percentage is not None
            and percentage > maximum_overhang
        ):
            status = PrintRecommendationStatus.PRINTABLE_WITH_WARNINGS
            reasons.append(
                RecommendationReason(
                    RecommendationReasonCode.OVERHANG_EXCEEDS_RECOMMENDED_THRESHOLD,
                    (
                        "The selected orientation has an overhang area percentage of "
                        f"{percentage:g}, exceeding the configured recommendation limit "
                        f"of {maximum_overhang:g}."
                    ),
                )
            )
        return PrintRecommendationResult(
            source_path=stl_analysis.source_path,
            status=status,
            configuration=config,
            recommended_candidate=selected,
            reasons=tuple(reasons),
            warnings=warnings,
        )


def _collect_warnings(
    stl_analysis: StlAnalysisResult, orientation_analysis: OrientationAnalysisResult
) -> tuple[RecommendationWarning, ...]:
    warnings = [
        *(RecommendationWarning("stl_analysis", warning) for warning in stl_analysis.warnings),
        *(
            RecommendationWarning("orientation_analysis", warning)
            for warning in orientation_analysis.warnings
        ),
    ]
    for candidate in orientation_analysis.candidates:
        warnings.extend(
            RecommendationWarning(
                f"orientation_candidate:{candidate.orientation.name}", warning
            )
            for warning in candidate.warnings
        )
    return tuple(warnings)


def _first_ranked_compatible_candidate(
    orientation_analysis: OrientationAnalysisResult,
) -> OrientationCandidateResult | None:
    by_name = {
        candidate.orientation.name: candidate
        for candidate in orientation_analysis.candidates
    }
    for name in orientation_analysis.ordered_orientation_names:
        candidate = by_name.get(name)
        if candidate is not None and candidate.facts.fits:
            return candidate
    return None


def _has_ranked_candidate(orientation_analysis: OrientationAnalysisResult) -> bool:
    candidate_names = {
        candidate.orientation.name for candidate in orientation_analysis.candidates
    }
    return any(
        name in candidate_names for name in orientation_analysis.ordered_orientation_names
    )


def _result(
    stl_analysis: StlAnalysisResult,
    status: PrintRecommendationStatus,
    configuration: PrintRecommendationConfiguration,
    candidate: OrientationCandidateResult | None,
    reason: RecommendationReason,
    warnings: tuple[RecommendationWarning, ...],
) -> PrintRecommendationResult:
    return PrintRecommendationResult(
        source_path=stl_analysis.source_path,
        status=status,
        configuration=configuration,
        recommended_candidate=candidate,
        reasons=(reason,),
        warnings=warnings,
    )
