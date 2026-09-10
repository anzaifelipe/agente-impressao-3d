"""Use case for explicit scale and unit interpretation of STL geometry facts."""

from dataclasses import dataclass

from agente_impressao_3d.domain.models import StlAnalysisResult, Vector3
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
    ScaleAndUnitFacts,
)


@dataclass(frozen=True, slots=True)
class AnalyzeScaleAndUnit:
    """Interprets an existing STL analysis without reading the STL again."""

    def execute(
        self,
        stl_analysis: StlAnalysisResult,
        configuration: ScaleAndUnitConfiguration | None = None,
    ) -> ScaleAndUnitAnalysisResult:
        config = configuration or ScaleAndUnitConfiguration()
        observed_dimensions = stl_analysis.facts.bounding_box.dimensions
        physical_dimensions = Vector3(
            x=observed_dimensions.x * config.scale_factor,
            y=observed_dimensions.y * config.scale_factor,
            z=observed_dimensions.z * config.scale_factor,
        )

        return ScaleAndUnitAnalysisResult(
            source_path=stl_analysis.source_path,
            facts=ScaleAndUnitFacts(
                observed_dimensions=observed_dimensions,
                physical_dimensions=physical_dimensions,
            ),
            configuration=config,
        )
