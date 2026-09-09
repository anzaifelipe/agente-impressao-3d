"""Use case for deterministic STL analysis."""

from dataclasses import dataclass
from pathlib import Path

from agente_impressao_3d.domain.models import (
    AnalysisAssumptions,
    StlAnalysisResult,
)
from agente_impressao_3d.domain.ports import MeshInspector


@dataclass(frozen=True, slots=True)
class AnalyzeStl:
    """Coordinates an inspection while keeping geometry libraries outside the use case."""

    mesh_inspector: MeshInspector

    def execute(
        self,
        source_path: Path,
        assumptions: AnalysisAssumptions | None = None,
    ) -> StlAnalysisResult:
        inspection = self.mesh_inspector.inspect(source_path)
        return StlAnalysisResult(
            source_path=str(source_path),
            facts=inspection.facts,
            assumptions=assumptions or AnalysisAssumptions(),
            warnings=inspection.warnings,
        )
