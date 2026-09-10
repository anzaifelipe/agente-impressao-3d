from pathlib import Path

from agente_impressao_3d.application.analyze_overhang import AnalyzeOverhang
from agente_impressao_3d.infrastructure.trimesh_face_metrics_reader import (
    TrimeshFaceMetricsReader,
)

source = Path(
    "/Users/felipeanzai/Downloads/Hi3D_Untitled_allparts_20260821_081332.stl"
)

analyzer = AnalyzeOverhang(
    face_metrics_reader=TrimeshFaceMetricsReader()
)

result = analyzer.execute(source)

print(result.to_dict())
